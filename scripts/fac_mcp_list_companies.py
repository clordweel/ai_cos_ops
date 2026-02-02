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
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read(1024 * 256)
            text = raw.decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(text)
            except Exception:
                raise ConfigError(f"非 JSON 响应：HTTP {resp.status}\n{text}")
    except urllib.error.HTTPError as e:
        raw = e.read(1024 * 256)
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
    """
    Returns (auth_header_value, auth_label, raw_for_mask)
    """
    raw = secrets.mcp_token.strip()
    if raw:
        if ":" in raw and " " not in raw:
            return f"token {raw}", "token", raw
        return f"Bearer {raw}", "Bearer", raw

    if secrets.rest_api_key and secrets.rest_api_secret:
        raw = f"{secrets.rest_api_key}:{secrets.rest_api_secret}"
        return f"token {raw}", "token", raw

    raise ConfigError(
        "缺少 MCP 鉴权信息：\n"
        "- 推荐：config/secrets.local.yaml -> mcp_token（OAuth 2.0 Bearer access_token）\n"
        "- 兼容：填写 rest_api_key/rest_api_secret 后，本脚本会尝试用 Authorization: token 访问 MCP\n"
    )


def _default_out_path(env: str) -> Path:
    return repo_root() / "work" / env / "reference" / "companies.json"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="使用 FAC MCP 获取 Company 列表（只读，MCP 优先）。")
    ap.add_argument("--env", choices=["dev", "prod"], required=True)
    ap.add_argument("--limit", type=int, default=50, help="返回条数（默认 50）")
    ap.add_argument(
        "--fields",
        default="name,abbr,default_currency,country",
        help="逗号分隔字段列表（默认：name,abbr,default_currency,country）",
    )
    ap.add_argument(
        "--out",
        default="",
        help="可选：保存结果到文件（默认保存到 work/<env>/reference/companies.json）",
    )
    args = ap.parse_args(argv)

    cfg = load_env_config(args.env)
    secrets = load_secrets(required=True)
    auth_header_value, auth_label, raw = _auth_from_secrets(secrets)

    mcp_url = cfg.mcp_base_url
    fields = [f.strip() for f in args.fields.split(",") if f.strip()]
    if not fields:
        fields = ["name"]

    print(f"ENV={cfg.env}  SITE={cfg.site_url}")
    print(f"FAC_MCP_ENDPOINT={mcp_url}")
    print(f"MCP_AUTH={auth_label}  VALUE={mask_secret(raw)}")

    # 1) initialize（连通性/鉴权）
    init = _mcp_call(
        mcp_url,
        auth_header_value,
        {"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}}, "id": 1},
    )
    srv = (init.get("result") or {}).get("serverInfo") if isinstance(init, dict) else None
    if isinstance(srv, dict):
        print(f"SERVER={srv.get('name','')}  VERSION={srv.get('version','')}")

    # 2) list_documents(Company)
    resp = _mcp_call(
        mcp_url,
        auth_header_value,
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "list_documents", "arguments": {"doctype": "Company", "fields": fields, "limit": args.limit}},
            "id": 2,
        },
    )
    texts = _extract_text_content(resp)
    parsed = _best_effort_parse_json_text(texts[0]) if texts else resp

    print("")
    print("COMPANY_LIST:")
    print(json.dumps(parsed, ensure_ascii=False, indent=2, default=str))

    out_path = Path(args.out) if args.out.strip() else _default_out_path(args.env)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print("")
    print(f"SAVED_TO={out_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except ConfigError as e:
        print(f"CONFIG_ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)

