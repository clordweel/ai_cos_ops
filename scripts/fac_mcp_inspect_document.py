from __future__ import annotations

import argparse
import json
import sys
import urllib.error
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
    raise ConfigError("缺少 MCP 鉴权信息（需要 mcp_token 或 rest_api_key/rest_api_secret）。")


def _unwrap_doc(obj: Any) -> Any:
    """
    Best-effort unwrap for FAC get_document output:
    - sometimes doc is directly returned
    - sometimes wrapped in {"result": {"data": ...}} or {"result": {"doc": ...}}
    """
    if isinstance(obj, dict):
        r = obj.get("result")
        if isinstance(r, dict):
            for k in ("doc", "data", "message"):
                v = r.get(k)
                if v is not None:
                    return v
        for k in ("message", "data"):
            v = obj.get(k)
            if v is not None:
                return v
    return obj


def _summarize(doc: Any, max_list_items: int) -> dict:
    if not isinstance(doc, dict):
        return {"type": type(doc).__name__, "value_preview": str(doc)[:200]}

    summary: dict = {"keys": sorted([k for k in doc.keys() if isinstance(k, str)])}
    # Include some common fields if present
    for k in (
        "name",
        "doctype",
        "item_code",
        "item_name",
        "item_group",
        "stock_uom",
        "purchase_uom",
        "custom_body_material",
        "custom_source_type",
        "custom_specification",
        "custom_param_hash",
        "custom_unique_item_name",
        "is_stock_item",
        "is_group",
        "disabled",
        "owner",
        "creation",
        "modified",
    ):
        if k in doc:
            summary[k] = doc.get(k)

    list_fields: List[dict] = []
    for k, v in doc.items():
        if isinstance(k, str) and isinstance(v, list):
            sample = v[:max_list_items]
            list_fields.append(
                {
                    "field": k,
                    "len": len(v),
                    "sample_keys": sorted(list({kk for row in sample if isinstance(row, dict) for kk in row.keys() if isinstance(kk, str)})),
                    "sample": sample,
                }
            )
    if list_fields:
        summary["list_fields"] = list_fields
    return summary


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="使用 FAC MCP 拉取并概要分析单个单据（只读）。")
    ap.add_argument("--env", choices=["dev", "prod"], required=True)
    ap.add_argument("--doctype", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--max-list-items", type=int, default=5, help="子表/列表字段展示样本数量（默认 5）")
    args = ap.parse_args(argv)

    cfg = load_env_config(args.env)
    secrets = load_secrets(required=True)
    auth_header_value, auth_label, raw = _auth_from_secrets(secrets)

    mcp_url = cfg.mcp_base_url
    print(f"ENV={cfg.env}  SITE={cfg.site_url}")
    print(f"FAC_MCP_ENDPOINT={mcp_url}")
    print(f"MCP_AUTH={auth_label}  VALUE={mask_secret(raw)}")
    print(f"DOCTYPE={args.doctype}")
    print(f"NAME={args.name}")

    _ = _mcp_call(
        mcp_url,
        auth_header_value,
        {"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}}, "id": 1},
    )

    resp = _mcp_call(
        mcp_url,
        auth_header_value,
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "get_document", "arguments": {"doctype": args.doctype, "name": args.name}},
            "id": 2,
        },
    )
    texts = _extract_text_content(resp)
    parsed = _best_effort_parse_json_text(texts[0]) if texts else resp
    doc = _unwrap_doc(parsed)
    summary = _summarize(doc, args.max_list_items)

    print("")
    print("SUMMARY:")
    # Windows console may not support some characters; keep output ASCII-safe.
    print(json.dumps(summary, ensure_ascii=True, indent=2, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except ConfigError as e:
        print(f"CONFIG_ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)

