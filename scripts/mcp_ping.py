from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from _lib_config import ConfigError, load_env_config, load_secrets


def _post_json(url: str, auth_header: str | None, body: dict) -> tuple[int, str]:
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if auth_header:
        headers["Authorization"] = auth_header
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read(4096)
            text = raw.decode("utf-8", errors="replace")
            try:
                return resp.status, json.dumps(json.loads(text), ensure_ascii=False)
            except Exception:
                return resp.status, text
    except urllib.error.HTTPError as e:
        raw = e.read(4096)
        return int(e.code), raw.decode("utf-8", errors="replace")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="MCP 连通性探测（不做写入）。对 FAC MCP 将执行 JSON-RPC initialize。")
    ap.add_argument("--env", choices=["dev", "prod"], required=True)
    ap.add_argument(
        "--auth",
        choices=["auto", "bearer", "token", "none"],
        default="auto",
        help="鉴权方式：auto 优先使用 mcp_token（Bearer），否则用 rest_api_key/secret（token）",
    )
    args = ap.parse_args(argv)

    cfg = load_env_config(args.env)
    secrets = load_secrets(required=False)

    url = cfg.mcp_base_url
    auth_header: str | None = None
    if args.auth == "none":
        auth_header = None
    elif args.auth == "bearer":
        if secrets.mcp_token:
            auth_header = f"Bearer {secrets.mcp_token}"
        else:
            auth_header = None
    elif args.auth == "token":
        if secrets.rest_api_key and secrets.rest_api_secret:
            auth_header = f"token {secrets.rest_api_key}:{secrets.rest_api_secret}"
        else:
            auth_header = None
    else:
        # auto
        if secrets.mcp_token:
            raw = secrets.mcp_token.strip()
            # Some environments accept Frappe API key:secret in Authorization: token
            if ":" in raw and " " not in raw:
                auth_header = f"token {raw}"
            else:
                auth_header = f"Bearer {raw}"
        elif secrets.rest_api_key and secrets.rest_api_secret:
            auth_header = f"token {secrets.rest_api_key}:{secrets.rest_api_secret}"

    payload = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
        "id": 1,
    }

    status, text = _post_json(url, auth_header=auth_header, body=payload)
    print(f"ENV={cfg.env}  MCP_ENDPOINT={url}")
    print(f"POST {url}")
    print(f"STATUS={status}")
    if text:
        print("BODY:")
        print(text)

    return 0 if (200 <= status < 300) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except ConfigError as e:
        print(f"CONFIG_ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)

