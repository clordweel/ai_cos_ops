from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from _lib_config import ConfigError, load_env_config, load_secrets, mask_secret, repo_root


def _http_json(method: str, url: str, headers: Dict[str, str], body: Optional[dict]) -> Tuple[int, dict]:
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {**headers, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read(1024 * 1024)
            text = raw.decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(text)
            except Exception:
                raise ConfigError(f"非 JSON 响应：HTTP {resp.status}\n{text}")
    except urllib.error.HTTPError as e:
        raw = e.read(1024 * 1024)
        text = raw.decode("utf-8", errors="replace")
        try:
            return int(e.code), json.loads(text)
        except Exception:
            raise ConfigError(f"HTTP {e.code}\n{text}")


def _mcp_call(mcp_url: str, auth_header_value: str, req_body: dict) -> dict:
    status, obj = _http_json(
        "POST",
        mcp_url,
        headers={"Authorization": auth_header_value, "Accept": "application/json"},
        body=req_body,
    )
    if not (200 <= status < 300):
        raise ConfigError(f"MCP HTTP 状态异常：{status}\n{json.dumps(obj, ensure_ascii=False, indent=2)}")
    return obj


def _extract_text_content(mcp_result: dict) -> List[str]:
    result = mcp_result.get("result") if isinstance(mcp_result, dict) else None
    if not isinstance(result, dict):
        return []
    content = result.get("content")
    if not isinstance(content, list):
        return []
    out: List[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
            out.append(item["text"])
    return out


def _best_effort_parse_json_text(text: str) -> Any:
    t = text.strip()
    if not t:
        return None
    try:
        return json.loads(t)
    except Exception:
        return t


def _extract_data_list(obj: Any) -> List[Any]:
    if isinstance(obj, list):
        return obj
    if not isinstance(obj, dict):
        return []
    r = obj.get("result")
    if isinstance(r, dict) and isinstance(r.get("data"), list):
        return r["data"]
    if isinstance(obj.get("data"), list):
        return obj["data"]
    return []


def _auth_from_secrets(secrets) -> tuple[str, str, str]:
    raw = secrets.mcp_token.strip()
    if raw:
        if ":" in raw and " " not in raw:
            return f"token {raw}", "token", raw
        return f"Bearer {raw}", "Bearer", raw
    if secrets.rest_api_key and secrets.rest_api_secret:
        raw = f"{secrets.rest_api_key}:{secrets.rest_api_secret}"
        return f"token {raw}", "token", raw
    raise ConfigError("缺少 MCP 鉴权信息（需要 mcp_token 或 rest_api_key/rest_api_secret）。")


def _tools_call(mcp_url: str, auth: str, name: str, arguments: dict, rpc_id: int) -> Any:
    resp = _mcp_call(
        mcp_url,
        auth,
        {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": name, "arguments": arguments}, "id": rpc_id},
    )
    texts = _extract_text_content(resp)
    return _best_effort_parse_json_text(texts[0]) if texts else resp


def _run_preflight(env: str, confirm_prod: bool) -> None:
    py = sys.executable
    cmd = [py, str(repo_root() / "scripts" / "preflight.py"), "--env", env, "--operation", "write"]
    if env == "prod" and confirm_prod:
        cmd.append("--confirm-prod")
    subprocess.run(cmd, check=True)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="为 Item 创建参数 hash 自定义字段（module= COS Stock，带索引）。")
    ap.add_argument("--env", choices=["dev", "prod"], required=True)
    ap.add_argument("--confirm-prod", action="store_true")
    ap.add_argument("--skip-preflight", action="store_true")
    ap.add_argument("--module", default="COS Stock", help="导出模块名（默认 COS Stock）")
    ap.add_argument("--app-name", default="cos", help="Module Def.app_name（默认 cos）")
    ap.add_argument("--dt", default="Item", help="目标 DocType（默认 Item）")
    ap.add_argument("--fieldname", default="custom_param_hash", help="字段名（默认 custom_param_hash）")
    ap.add_argument("--label", default="参数Hash", help="字段标签（默认 参数Hash）")
    ap.add_argument("--insert-after", default="custom_unique_item_name", help="插入位置字段（默认 custom_unique_item_name）")
    ap.add_argument("--length", type=int, default=64, help="Data 长度（默认 64）")
    ap.add_argument("--unique", action="store_true", help="是否创建唯一约束（默认 false）")
    ap.add_argument("--no-search-index", action="store_true", help="禁用数据库索引（默认启用）")
    ap.add_argument("--no-read-only", action="store_true", help="禁用只读（默认启用）")
    ap.add_argument("--no-no-copy", action="store_true", help="禁用 no_copy（默认启用）")
    args = ap.parse_args(argv)

    if args.env == "prod" and not args.confirm_prod:
        raise ConfigError("禁止默认在 PROD 创建/修改自定义字段。若确需在 prod，请显式传入 --confirm-prod，并先通过 preflight 双确认。")

    cfg = load_env_config(args.env)
    secrets = load_secrets(required=True)
    auth, auth_label, raw = _auth_from_secrets(secrets)
    mcp_url = cfg.mcp_base_url

    print(f"ENV={cfg.env}  SITE={cfg.site_url}")
    print(f"FAC_MCP_ENDPOINT={mcp_url}")
    print(f"MCP_AUTH={auth_label}  VALUE={mask_secret(raw)}")

    if not args.skip_preflight:
        _run_preflight(args.env, confirm_prod=args.confirm_prod)

    _ = _mcp_call(
        mcp_url,
        auth,
        {"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}}, "id": 1},
    )

    # 1) Ensure Module Def exists
    mod_rows = _tools_call(
        mcp_url,
        auth,
        "list_documents",
        {"doctype": "Module Def", "filters": {"module_name": args.module}, "fields": ["name", "module_name", "app_name", "custom"], "limit": 1},
        rpc_id=2,
    )
    mod_data = _extract_data_list(mod_rows)
    if mod_data:
        print(f"MODULE_DEF: exists ({args.module})")
    else:
        print(f"MODULE_DEF: creating ({args.module})")
        _ = _tools_call(
            mcp_url,
            auth,
            "create_document",
            {"doctype": "Module Def", "data": {"module_name": args.module, "app_name": args.app_name, "custom": 1}, "submit": False},
            rpc_id=3,
        )

    # 2) Ensure Custom Field exists (dt+fieldname)
    cf_rows = _tools_call(
        mcp_url,
        auth,
        "list_documents",
        {"doctype": "Custom Field", "filters": {"dt": args.dt, "fieldname": args.fieldname}, "fields": ["name", "dt", "fieldname", "module", "fieldtype", "label", "search_index", "unique"], "limit": 1},
        rpc_id=4,
    )
    cf_data = _extract_data_list(cf_rows)

    want_search_index = 0 if args.no_search_index else 1
    want_unique = 1 if args.unique else 0
    want_read_only = 0 if args.no_read_only else 1
    want_no_copy = 0 if args.no_no_copy else 1

    if cf_data:
        cf_name = cf_data[0].get("name") if isinstance(cf_data[0], dict) else None
        if not isinstance(cf_name, str) or not cf_name:
            raise ConfigError("Custom Field 查询结果缺少 name，无法更新。")
        print(f"CUSTOM_FIELD: exists ({cf_name}) -> updating settings")
        _ = _tools_call(
            mcp_url,
            auth,
            "update_document",
            {
                "doctype": "Custom Field",
                "name": cf_name,
                "data": {
                    "module": args.module,
                    "label": args.label,
                    "fieldtype": "Data",
                    "length": args.length,
                    "read_only": want_read_only,
                    "no_copy": want_no_copy,
                    "unique": want_unique,
                    "search_index": want_search_index,
                },
            },
            rpc_id=5,
        )
    else:
        print("CUSTOM_FIELD: creating")
        _ = _tools_call(
            mcp_url,
            auth,
            "create_document",
            {
                "doctype": "Custom Field",
                "data": {
                    "dt": args.dt,
                    "fieldname": args.fieldname,
                    "label": args.label,
                    "fieldtype": "Data",
                    "insert_after": args.insert_after,
                    "length": args.length,
                    "module": args.module,
                    "read_only": want_read_only,
                    "no_copy": want_no_copy,
                    "unique": want_unique,
                    "search_index": want_search_index,
                    "description": "从参数模板生成的唯一 hash，用于幂等/去重与重复物料快速判定。",
                },
                "submit": False,
            },
            rpc_id=6,
        )

    # 3) Verify field appears in doctype meta
    meta = _tools_call(mcp_url, auth, "get_doctype_info", {"doctype": args.dt}, rpc_id=7)
    ok = False
    try:
        # tool result may be wrapped; handle common shapes
        if isinstance(meta, dict) and isinstance(meta.get("result"), dict):
            meta2 = meta.get("result")
        else:
            meta2 = meta
        fields = meta2.get("fields") if isinstance(meta2, dict) else None
        if isinstance(fields, list):
            ok = any(isinstance(f, dict) and f.get("fieldname") == args.fieldname for f in fields)
    except Exception:
        ok = False
    print(f"VERIFY: field_in_meta={ok}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except subprocess.CalledProcessError as e:
        print(f"SUBPROCESS_ERROR: exit={e.returncode}", file=sys.stderr)
        raise SystemExit(int(e.returncode) if e.returncode else 2)
    except ConfigError as e:
        print(f"CONFIG_ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)

