from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from _lib_config import ConfigError, load_env_config, load_secrets, mask_secret, repo_root


def _http_json(method: str, url: str, headers: Dict[str, str], body: Optional[dict]) -> Tuple[int, dict]:
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {**headers, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            raw = resp.read(1024 * 512)
            text = raw.decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(text)
            except Exception:
                raise ConfigError(f"非 JSON 响应：HTTP {resp.status}\n{text}")
    except urllib.error.HTTPError as e:
        raw = e.read(1024 * 512)
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


def _auth_from_secrets(secrets) -> tuple[str, str, str]:
    raw = secrets.mcp_token.strip()
    if raw:
        if ":" in raw and " " not in raw:
            return f"token {raw}", "token", raw
        return f"Bearer {raw}", "Bearer", raw
    if secrets.rest_api_key and secrets.rest_api_secret:
        raw = f"{secrets.rest_api_key}:{secrets.rest_api_secret}"
        return f"token {raw}", "token", raw
    raise ConfigError(
        "缺少 MCP 鉴权信息（需要 mcp_token 或 rest_api_key/rest_api_secret）。\n"
        "提示：你当前 FAC 环境已支持 Authorization: token api_key:api_secret 访问 MCP。"
    )


def _default_out_path(env: str, item_code: str) -> Path:
    safe = item_code.replace("/", "_").replace("\\", "_").replace(" ", "_")
    return repo_root() / "work" / env / "operations" / "items" / f"created_item_{safe}.json"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="在指定物料组创建测试物料：交流接触器（DEV 推荐）。")
    ap.add_argument("--env", choices=["dev", "prod"], required=True)
    ap.add_argument("--item-group", default="电气元件", help="物料组（默认：电气元件）")
    ap.add_argument("--item-code", default="TEST-AC-CONTACTOR", help="物料编码（默认：TEST-AC-CONTACTOR）")
    ap.add_argument("--item-name", default="测试交流接触器", help="物料名称（默认：测试交流接触器）")
    ap.add_argument("--stock-uom", default="个", help="库存单位（默认：个）")
    ap.add_argument("--dry-run", action="store_true", help="只做存在性检查，不创建")
    ap.add_argument("--out", default="", help="保存结果到文件（默认保存到 work/<env>/operations/items/created_item_<code>.json）")
    ap.add_argument("--confirm-prod", action="store_true", help="env=prod 时必须显式确认（仍需满足 preflight 双确认）")
    args = ap.parse_args(argv)

    if args.env == "prod" and not args.confirm_prod:
        raise ConfigError("禁止默认在 PROD 创建测试物料。若确需在 prod，请显式传入 --confirm-prod，并先通过 preflight 双确认。")

    cfg = load_env_config(args.env)
    secrets = load_secrets(required=True)
    auth_header_value, auth_label, raw = _auth_from_secrets(secrets)

    mcp_url = cfg.mcp_base_url
    print(f"ENV={cfg.env}  SITE={cfg.site_url}")
    print(f"FAC_MCP_ENDPOINT={mcp_url}")
    print(f"MCP_AUTH={auth_label}  VALUE={mask_secret(raw)}")

    # 0) initialize
    _ = _mcp_call(
        mcp_url,
        auth_header_value,
        {"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}}, "id": 1},
    )

    # 1) existence check
    exists_resp = _mcp_call(
        mcp_url,
        auth_header_value,
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "list_documents",
                "arguments": {"doctype": "Item", "filters": {"item_code": args.item_code}, "fields": ["name", "item_code", "item_name", "item_group"], "limit": 1},
            },
            "id": 2,
        },
    )
    texts = _extract_text_content(exists_resp)
    parsed = _best_effort_parse_json_text(texts[0]) if texts else exists_resp

    # FAC list_documents often returns {"success":true,"result":{"data":[...]}}
    existing = None
    try:
        data = parsed.get("result", {}).get("data") if isinstance(parsed, dict) else None
        if isinstance(data, list) and data:
            existing = data[0]
    except Exception:
        existing = None

    if existing is not None:
        print("")
        print("ALREADY_EXISTS:")
        print(json.dumps(existing, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.dry_run:
        print("")
        print("DRY_RUN: not creating (not found).")
        return 0

    # 2) create document
    create_args = {
        "doctype": "Item",
        "data": {
            "item_code": args.item_code,
            "item_name": args.item_name,
            "item_group": args.item_group,
            "stock_uom": args.stock_uom,
        },
        "submit": False,
    }
    create_resp = _mcp_call(
        mcp_url,
        auth_header_value,
        {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "create_document", "arguments": create_args}, "id": 3},
    )
    create_texts = _extract_text_content(create_resp)
    create_parsed = _best_effort_parse_json_text(create_texts[0]) if create_texts else create_resp

    print("")
    print("CREATED_ITEM:")
    print(json.dumps(create_parsed, ensure_ascii=False, indent=2, default=str))

    out_path = Path(args.out) if args.out.strip() else _default_out_path(args.env, args.item_code)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(create_parsed, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"SAVED_TO={out_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except ConfigError as e:
        print(f"CONFIG_ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)

