from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from _lib_config import ConfigError, load_env_config, load_secrets, mask_secret


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
    headers = {"Authorization": auth_header_value, "Accept": "application/json"}
    status, obj = _http_json("POST", mcp_url, headers=headers, body=req_body)
    if not (200 <= status < 300):
        raise ConfigError(f"MCP HTTP 状态异常：{status}\n{json.dumps(obj, ensure_ascii=False, indent=2)}")
    return obj


def _mcp_initialize(mcp_url: str, auth_header_value: str) -> dict:
    return _mcp_call(
        mcp_url,
        auth_header_value,
        {
            "jsonrpc": "2.0",
            "method": "initialize",
            "params": {"protocolVersion": "2025-03-26", "capabilities": {}},
            "id": 1,
        },
    )


def _mcp_tools_list(mcp_url: str, auth_header_value: str) -> dict:
    return _mcp_call(
        mcp_url,
        auth_header_value,
        {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2},
    )


def _mcp_tools_call(mcp_url: str, auth_header_value: str, name: str, arguments: dict, rpc_id: int) -> dict:
    return _mcp_call(
        mcp_url,
        auth_header_value,
        {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": name, "arguments": arguments}, "id": rpc_id},
    )


def _extract_text_content(mcp_result: dict) -> List[str]:
    """
    FAC MCP returns:
      {"result":{"content":[{"type":"text","text":"..."}],"isError":false}}
    """
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


def _oidc_userinfo(site_url: str, bearer_token: str) -> dict:
    url = site_url.rstrip("/") + "/api/method/frappe.integrations.oauth2.openid_profile"
    status, obj = _http_json(
        "GET",
        url,
        headers={"Authorization": f"Bearer {bearer_token}", "Accept": "application/json"},
        body=None,
    )
    if not (200 <= status < 300):
        raise ConfigError(f"OIDC userinfo 失败：HTTP {status}\n{json.dumps(obj, ensure_ascii=False, indent=2)}")
    return obj


def _guess_user_keys(userinfo: dict) -> List[str]:
    # Common keys across OIDC providers / Frappe implementations
    msg = userinfo.get("message") if isinstance(userinfo, dict) else None
    if not isinstance(msg, dict):
        return []
    candidates: List[str] = []
    for k in ("name", "preferred_username", "email", "sub", "user"):
        v = msg.get(k)
        if isinstance(v, str) and v.strip():
            candidates.append(v.strip())
    # de-dup
    seen = set()
    out: List[str] = []
    for c in candidates:
        if c not in seen:
            out.append(c)
            seen.add(c)
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="使用 Frappe_Assistant_Core（FAC）MCP 优先获取当前用户基础数据（只读）。")
    ap.add_argument("--env", choices=["dev", "prod"], required=True)
    ap.add_argument(
        "--user",
        default="",
        help="可选：指定 User.name 或 email；不填则尝试用 OIDC userinfo 从 Bearer token 推断",
    )
    args = ap.parse_args(argv)

    cfg = load_env_config(args.env)
    secrets = load_secrets(required=True)

    mcp_url = cfg.mcp_base_url
    raw = secrets.mcp_token.strip()

    # Auth selection:
    # - FAC MCP 官方推荐：Authorization: Bearer <oauth_access_token>
    # - 某些环境可能会允许 Frappe REST token（Authorization: token api_key:api_secret），这里做兼容尝试。
    if raw:
        if ":" in raw and " " not in raw:
            # User likely pasted api_key:api_secret into mcp_token.
            auth_header_value = f"token {raw}"
            auth_label = "token"
        else:
            auth_header_value = f"Bearer {raw}"
            auth_label = "Bearer"
    elif secrets.rest_api_key and secrets.rest_api_secret:
        # Fall back to REST token header if user did not provide mcp_token.
        auth_header_value = f"token {secrets.rest_api_key}:{secrets.rest_api_secret}"
        auth_label = "token"
        raw = f"{secrets.rest_api_key}:{secrets.rest_api_secret}"
    else:
        raise ConfigError(
            "缺少 MCP 鉴权信息：\n"
            "- 推荐：config/secrets.local.yaml -> mcp_token（OAuth 2.0 Bearer access_token）\n"
            "- 兼容：填写 rest_api_key/rest_api_secret 后，本脚本会尝试用 Authorization: token 访问 MCP\n"
        )

    print(f"ENV={cfg.env}  SITE={cfg.site_url}")
    print(f"FAC_MCP_ENDPOINT={mcp_url}")
    print(f"MCP_AUTH={auth_label}  VALUE={mask_secret(raw)}")

    # 1) MCP handshake + tools discovery
    init = _mcp_initialize(mcp_url, auth_header_value)
    print("")
    print("MCP initialize: OK")
    # Keep output small; show serverInfo if present
    srv = (init.get("result") or {}).get("serverInfo") if isinstance(init, dict) else None
    if isinstance(srv, dict):
        print(f"SERVER={srv.get('name','')}  VERSION={srv.get('version','')}")

    tools = _mcp_tools_list(mcp_url, auth_header_value)
    tool_list = ((tools.get("result") or {}).get("tools") if isinstance(tools, dict) else None) or []
    tool_names = {t.get("name") for t in tool_list if isinstance(t, dict)}
    print(f"TOOLS={len(tool_names)}")

    # 2) Figure out who the bearer token is for (best effort)
    user_candidates: List[str] = []
    if args.user.strip():
        user_candidates = [args.user.strip()]
    else:
        try:
            # OIDC userinfo requires Bearer token; only try when we actually have Bearer.
            if auth_label == "Bearer":
                ui = _oidc_userinfo(cfg.site_url, raw)
            else:
                raise RuntimeError("not bearer")
            cand = _guess_user_keys(ui)
            user_candidates.extend(cand)
            if cand:
                print("")
                print(f"OIDC userinfo: OK  candidates={cand}")
        except Exception as e:
            # Don't fail hard: allow manual user
            print("")
            print("OIDC userinfo: SKIP/FAIL (可忽略，改用 --user 指定用户)")

    if not user_candidates:
        raise ConfigError("无法推断 token 对应用户。请用 --user 指定（例如 Administrator 或 user@example.com）。")

    # 3) Use MCP tool to fetch User base fields
    base_fields = ["name", "email", "full_name", "enabled", "user_type", "last_login"]
    if "list_documents" not in tool_names and "get_document" not in tool_names:
        raise ConfigError("MCP 工具集中缺少 list_documents/get_document，无法通过 MCP 拉取 User 数据。请检查 FAC 插件/权限。")

    print("")
    print("USER_LOOKUP:")

    # Try multiple strategies to locate the user.
    def try_list(filters: dict) -> Optional[Any]:
        r = _mcp_tools_call(
            mcp_url,
            auth_header_value,
            "list_documents",
            {"doctype": "User", "filters": filters, "fields": base_fields, "limit": 1},
            rpc_id=10,
        )
        texts = _extract_text_content(r)
        if not texts:
            return None
        parsed = _best_effort_parse_json_text(texts[0])
        return parsed

    def try_get(name: str) -> Optional[Any]:
        r = _mcp_tools_call(
            mcp_url,
            auth_header_value,
            "get_document",
            {"doctype": "User", "name": name, "fields": base_fields},
            rpc_id=11,
        )
        texts = _extract_text_content(r)
        if not texts:
            return None
        return _best_effort_parse_json_text(texts[0])

    found: Optional[Any] = None
    for cand in user_candidates:
        # First: treat candidate as User.name
        if "list_documents" in tool_names:
            found = try_list({"name": cand})
            if found:
                print(f"- matched by name={cand}")
                break
            # If looks like email, also try by email field
            if "@" in cand:
                found = try_list({"email": cand})
                if found:
                    print(f"- matched by email={cand}")
                    break
        if "get_document" in tool_names:
            found = try_get(cand)
            if found:
                print(f"- got by get_document name={cand}")
                break

    if found is None:
        raise ConfigError(
            "通过 MCP 未找到用户基础数据。可能原因：\n"
            "- token 对应用户不在候选列表；\n"
            "- 权限不足（无权读取 User）；\n"
            "- FAC 返回格式变化。\n"
            "你可以改用：--user Administrator 或 --user <email> 重试。"
        )

    print("RESULT:")
    print(json.dumps(found, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except ConfigError as e:
        print(f"CONFIG_ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)

