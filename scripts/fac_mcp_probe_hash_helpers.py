from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Dict, Optional, Tuple

from _lib_config import ConfigError, load_env_config, load_secrets, mask_secret


def _http_json(method: str, url: str, headers: Dict[str, str], body: Optional[dict]) -> Tuple[int, dict]:
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {**headers, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
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


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="探测 run_python_code 环境中可用的 hash/md5 helper（只读）。")
    ap.add_argument("--env", choices=["dev", "prod"], required=True)
    args = ap.parse_args(argv)

    cfg = load_env_config(args.env)
    secrets = load_secrets(required=True)
    auth, auth_label, raw = _auth_from_secrets(secrets)
    mcp_url = cfg.mcp_base_url

    print(f"ENV={cfg.env}  SITE={cfg.site_url}")
    print(f"FAC_MCP_ENDPOINT={mcp_url}")
    print(f"MCP_AUTH={auth_label}  VALUE={mask_secret(raw)}")

    _ = _mcp_call(
        mcp_url,
        auth,
        {"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}}, "id": 1},
    )

    code = r'''
out = {}
out["has_frappe_utils"] = hasattr(frappe, "utils")
out["has_frappe_utils_data"] = hasattr(frappe.utils, "data") if hasattr(frappe, "utils") else False
out["has_frappe_utils_data_md5"] = hasattr(frappe.utils.data, "md5") if out["has_frappe_utils_data"] else False
out["has_frappe_utils_md5"] = hasattr(frappe.utils, "md5") if hasattr(frappe, "utils") else False
out["has_frappe_generate_hash"] = hasattr(frappe, "generate_hash")
print(out)
if out.get("has_frappe_utils_data_md5"):
    print("md5_test=", frappe.utils.data.md5("abc"))
'''

    resp = _mcp_call(
        mcp_url,
        auth,
        {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "run_python_code", "arguments": {"code": code}}, "id": 2},
    )
    print(json.dumps(resp, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except ConfigError as e:
        print(f"CONFIG_ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)

