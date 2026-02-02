from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

from _lib_config import ConfigError, load_env_config, load_secrets


def _get(url: str, auth_header: str | None) -> tuple[int, str]:
    headers = {}
    if auth_header:
        headers["Authorization"] = auth_header
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read(4096)
            ct = resp.headers.get("content-type", "")
            if "application/json" in ct:
                try:
                    return resp.status, json.dumps(json.loads(body.decode("utf-8", errors="replace")), ensure_ascii=False)
                except Exception:
                    return resp.status, body.decode("utf-8", errors="replace")
            return resp.status, body.decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return int(e.code), e.read(4096).decode("utf-8", errors="replace")


def _json_loads_maybe(s: str) -> dict | None:
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Frappe REST 连通性/鉴权自检（不做写入）。")
    ap.add_argument("--env", choices=["dev", "prod"], required=True)
    ap.add_argument(
        "--user-info",
        action="store_true",
        help="在 get_logged_user 成功后，额外查询 User 的基础字段（只读）",
    )
    args = ap.parse_args(argv)

    cfg = load_env_config(args.env)
    secrets = load_secrets(required=True)
    if not (secrets.rest_api_key and secrets.rest_api_secret):
        raise ConfigError(
            "本地密钥未填写：config/secrets.local.yaml\n"
            "请把 token 按 <api_key>:<api_secret> 拆分后分别写入：\n"
            "- rest_api_key\n"
            "- rest_api_secret\n"
        )

    base = cfg.rest_base_url.rstrip("/")
    ping_url = f"{base}/api/method/frappe.ping"
    user_url = f"{base}/api/method/frappe.auth.get_logged_user"

    print(f"ENV={cfg.env}  REST={base}")
    print(f"GET {ping_url}")
    s1, b1 = _get(ping_url, auth_header=None)
    print(f"STATUS={s1}")
    if b1:
        print("BODY:")
        print(b1)

    print("")
    auth = f"token {secrets.rest_api_key}:{secrets.rest_api_secret}"
    print(f"GET {user_url}")
    s2, b2 = _get(user_url, auth_header=auth)
    print(f"STATUS={s2}")
    if b2:
        print("BODY:")
        print(b2)

    if args.user_info and (200 <= s2 < 300):
        data = _json_loads_maybe(b2) or {}
        user_id = (data.get("message") or "").strip()
        if user_id:
            fields = ["name", "email", "full_name", "enabled", "user_type", "last_login"]
            q = urllib.parse.urlencode(
                {
                    "doctype": "User",
                    "filters": json.dumps({"name": user_id}, ensure_ascii=False),
                    "fieldname": json.dumps(fields, ensure_ascii=False),
                }
            )
            info_url = f"{base}/api/method/frappe.client.get_value?{q}"
            print("")
            print(f"GET {info_url}")
            s3, b3 = _get(info_url, auth_header=auth)
            print(f"STATUS={s3}")
            if b3:
                print("BODY:")
                print(b3)
        else:
            print("")
            print("提示：get_logged_user 未返回可解析的用户标识（message 字段为空），跳过 user-info 查询。")

    ok = (200 <= s1 < 300) and (200 <= s2 < 300)
    if not ok:
        print("")
        print("提示：")
        print("- 如果 ping 失败：检查 rest_base_url 是否正确、站点是否可达。")
        print("- 如果 get_logged_user 失败：检查 API key/secret 是否有效、是否具备权限。")
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except ConfigError as e:
        print(f"CONFIG_ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)

