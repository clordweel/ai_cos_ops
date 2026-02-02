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


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="输出 Item Parameter Template 的参数/绑定字段/uom 清单（只读）。")
    ap.add_argument("--env", choices=["dev", "prod"], required=True)
    ap.add_argument("--name", required=True, help="模板 name（例如 标准模板 - 钢板）")
    args = ap.parse_args(argv)

    cfg = load_env_config(args.env)
    secrets = load_secrets(required=True)
    auth_header_value, auth_label, raw = _auth_from_secrets(secrets)
    mcp_url = cfg.mcp_base_url

    print(f"ENV={cfg.env}  SITE={cfg.site_url}")
    print(f"FAC_MCP_ENDPOINT={mcp_url}")
    print(f"MCP_AUTH={auth_label}  VALUE={mask_secret(raw)}")
    print(f"TEMPLATE_NAME={args.name}")

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
            "params": {"name": "get_document", "arguments": {"doctype": "Item Parameter Template", "name": args.name}},
            "id": 2,
        },
    )
    texts = _extract_text_content(resp)
    parsed = _best_effort_parse_json_text(texts[0]) if texts else resp
    doc = _unwrap_doc(parsed)
    if not isinstance(doc, dict):
        raise ConfigError(f"无法解析模板文档结构：{type(doc).__name__}")

    print("")
    print(f"ITEM_GROUP={doc.get('item_group')}")
    print("")
    print("UOMS:")
    for row in doc.get("uoms") or []:
        if isinstance(row, dict):
            uom = row.get("uom")
            cf = row.get("conversion_factor")
            print(f"- {uom}  conversion_factor={cf}")

    print("")
    print("PARAMETERS:")
    for row in doc.get("parameters") or []:
        if not isinstance(row, dict):
            continue
        idx = row.get("idx")
        pname = row.get("parameter_name")
        ctype = row.get("constraint_type")
        default = row.get("parameter_default_value")
        readonly = row.get("readonly_value")
        optional = row.get("optional")
        join_hash = row.get("join_to_hash")
        binding = row.get("binding_field")
        target = row.get("target_field")
        doctype_sel = row.get("doctype_selector")
        value_doctype = row.get("value_doctype")
        value_int = row.get("value_integer")
        value_float = row.get("value_float")
        value_fmt = row.get("value_format")

        # keep output short-ish but complete
        extra = []
        if doctype_sel:
            extra.append(f"doctype_selector={doctype_sel}")
        if value_doctype:
            extra.append(f"value_doctype={value_doctype}")
        if value_int not in (None, 0):
            extra.append(f"value_integer={value_int}")
        if value_float not in (None, 0.0):
            extra.append(f"value_float={value_float}")
        if value_fmt:
            extra.append("value_format=<...>")

        extra_s = ("  " + "  ".join(extra)) if extra else ""
        print(
            f"- [{idx}] {pname}  type={ctype}  default={default!r}  optional={optional}  readonly={readonly}  join_to_hash={join_hash}  binding={binding}  target={target}{extra_s}"
        )

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except ConfigError as e:
        print(f"CONFIG_ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)

