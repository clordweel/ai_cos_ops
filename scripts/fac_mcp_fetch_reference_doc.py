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


def _extract_data_list(obj: Any) -> List[Any]:
    """
    Normalize list_documents output shapes (best effort).
    Common FAC shape: {"success":true,"result":{"data":[...]}}
    """
    if isinstance(obj, list):
        return obj
    if not isinstance(obj, dict):
        return []
    # Sometimes the list is directly under result/data
    r = obj.get("result")
    if isinstance(r, dict):
        data = r.get("data")
        if isinstance(data, list):
            return data
    # Or directly under data
    data = obj.get("data")
    if isinstance(data, list):
        return data
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
    raise ConfigError(
        "缺少 MCP 鉴权信息：\n"
        "- 推荐：config/secrets.local.yaml -> mcp_token（OAuth 2.0 Bearer access_token）\n"
        "- 兼容：填写 rest_api_key/rest_api_secret 后，本脚本会尝试用 Authorization: token 访问 MCP\n"
    )


def _safe_filename(s: str) -> str:
    # Windows 不允许: < > : " / \ | ? *
    bad = '<>:"/\\|?*'
    out = "".join("_" if ch in bad else ch for ch in s.strip())
    out = out.replace(" ", "_")
    out = out.strip("._")
    return out or "doc"


def _doctype_slug(doctype: str) -> str:
    return _safe_filename(doctype).lower()


def _default_out_path(env: str, doctype: str, docname: str) -> Path:
    return repo_root() / "work" / env / "reference" / _doctype_slug(doctype) / f"{_safe_filename(docname)}.json"


def _parse_json_obj(s: str) -> dict:
    try:
        v = json.loads(s)
    except Exception as e:
        raise ConfigError(f"--filters-json 不是合法 JSON：{e}")
    if not isinstance(v, dict):
        raise ConfigError("--filters-json 必须是 JSON 对象（例如 {\"name\":\"电机模板\"}）。")
    return v


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="按需拉取并保存单个 reference 文档（MCP 只读）：先查找，再仅保存命中的那一条。",
    )
    ap.add_argument("--env", choices=["dev", "prod"], required=True)
    ap.add_argument("--doctype", required=True, help='DocType（例如 "Item Parameter Template"）')
    ap.add_argument("--name", default="", help="精确 name（提供后将直接 get_document，不再搜索）")
    ap.add_argument("--query", default="", help="模糊查找关键词（例如 电机模板）")
    ap.add_argument("--search-field", default="name", help="用于搜索的字段名（默认 name）")
    ap.add_argument("--limit", type=int, default=20, help="搜索返回条数上限（默认 20）")
    ap.add_argument("--pick", type=int, default=1, help="当存在多个候选时，选择第 N 个（默认 1）")
    ap.add_argument("--allow-multi", action="store_true", help="当存在多个候选时允许自动 pick（默认会报错要求更精确）")
    ap.add_argument(
        "--fields",
        default="",
        help="可选：get_document 的字段列表（逗号分隔）。不填则不传 fields（尝试获取完整文档）。",
    )
    ap.add_argument(
        "--filters-json",
        default="",
        help='可选：高级过滤器（JSON 对象，原样传给 list_documents.filters），例如 {"name":["like","%%电机%%"]}',
    )
    ap.add_argument("--out", default="", help="保存路径（默认 work/<env>/reference/<doctype>/<name>.json）")
    args = ap.parse_args(argv)

    if not args.name.strip() and not args.query.strip() and not args.filters_json.strip():
        raise ConfigError("必须提供 --name 或 --query 或 --filters-json 之一。")

    cfg = load_env_config(args.env)
    secrets = load_secrets(required=True)
    auth_header_value, auth_label, raw = _auth_from_secrets(secrets)
    mcp_url = cfg.mcp_base_url

    print(f"ENV={cfg.env}  SITE={cfg.site_url}")
    print(f"FAC_MCP_ENDPOINT={mcp_url}")
    print(f"MCP_AUTH={auth_label}  VALUE={mask_secret(raw)}")
    print(f"DOCTYPE={args.doctype}")

    _ = _mcp_call(
        mcp_url,
        auth_header_value,
        {"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}}, "id": 1},
    )

    # 1) Determine target docname
    target_name = args.name.strip()
    if not target_name:
        filters: dict
        if args.filters_json.strip():
            filters = _parse_json_obj(args.filters_json.strip())
        else:
            q = args.query.strip()
            sf = args.search_field.strip() or "name"
            # Try exact match first; then best-effort "like"
            filters_try = [{sf: q}, {sf: ["like", f"%{q}%"]}]
            filters = {}

        candidates: List[Any] = []
        if args.filters_json.strip():
            filters_list = [filters]
        else:
            q = args.query.strip()
            sf = args.search_field.strip() or "name"
            filters_list = [{sf: q}, {sf: ["like", f"%{q}%"]}]

        last_parsed: Any = None
        for f in filters_list:
            resp = _mcp_call(
                mcp_url,
                auth_header_value,
                {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": "list_documents", "arguments": {"doctype": args.doctype, "filters": f, "fields": ["name"], "limit": args.limit}},
                    "id": 2,
                },
            )
            texts = _extract_text_content(resp)
            last_parsed = _best_effort_parse_json_text(texts[0]) if texts else resp
            candidates = _extract_data_list(last_parsed)
            if candidates:
                break

        if not candidates:
            raise ConfigError(f"未找到匹配项（doctype={args.doctype}）。你可以改用 --filters-json 传入更精确过滤器。")

        names: List[str] = []
        for c in candidates:
            if isinstance(c, dict) and isinstance(c.get("name"), str):
                names.append(c["name"])
            elif isinstance(c, str):
                names.append(c)

        if not names:
            raise ConfigError(f"搜索结果无法解析 name 字段：\n{json.dumps(last_parsed, ensure_ascii=False, indent=2, default=str)}")

        if len(names) > 1 and not args.allow_multi:
            preview = "\n".join([f"{i+1}. {n}" for i, n in enumerate(names[:20])])
            raise ConfigError(
                "匹配到多个候选项，为避免误存，已中止。\n"
                "请：\n"
                "- 改用 --name 精确指定；或\n"
                "- 增加过滤条件（--filters-json）；或\n"
                "- 明确允许 pick（加 --allow-multi 并设置 --pick）。\n"
                f"候选（最多显示 20 条）：\n{preview}"
            )

        pick_idx = max(1, int(args.pick)) - 1
        if pick_idx >= len(names):
            raise ConfigError(f"--pick 超出范围：pick={args.pick} 但候选数={len(names)}")
        target_name = names[pick_idx]

    print(f"TARGET_NAME={target_name}")

    # 2) Fetch the full (or partial) document
    get_args: dict = {"doctype": args.doctype, "name": target_name}
    fields = [f.strip() for f in args.fields.split(",") if f.strip()]
    if fields:
        get_args["fields"] = fields

    doc_resp = _mcp_call(
        mcp_url,
        auth_header_value,
        {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "get_document", "arguments": get_args}, "id": 3},
    )
    doc_texts = _extract_text_content(doc_resp)
    doc_parsed = _best_effort_parse_json_text(doc_texts[0]) if doc_texts else doc_resp

    out_path = Path(args.out) if args.out.strip() else _default_out_path(args.env, args.doctype, target_name)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc_parsed, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    print("")
    print("SAVED_TO:")
    print(out_path)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except ConfigError as e:
        print(f"CONFIG_ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)

