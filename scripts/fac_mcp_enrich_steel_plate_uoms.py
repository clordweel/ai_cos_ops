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
    ap = argparse.ArgumentParser(description="为钢板物料补齐 uoms 转换（米/张），基于模板公式计算（DEV 推荐）。")
    ap.add_argument("--env", choices=["dev", "prod"], required=True)
    ap.add_argument("--item", required=True, help="Item.name（例如 10110004）")
    ap.add_argument("--thickness", type=float, required=True, help="厚度 mm")
    ap.add_argument("--width", type=int, required=True, help="宽度 mm")
    ap.add_argument("--length", type=int, required=True, help="长度 mm")
    ap.add_argument("--density", type=float, default=7.85, help="密度 g/cm3（默认 7.85）")
    ap.add_argument("--stock-uom", default="千克", help="stock_uom（默认 千克）")
    ap.add_argument("--purchase-uom", default="吨", help="purchase_uom（默认 吨）")
    ap.add_argument("--uom-meter", default="米", help="长度单位 UOM（默认 米）")
    ap.add_argument("--uom-sheet", default="张", help="张/片单位 UOM（默认 张）")
    ap.add_argument("--confirm-prod", action="store_true", help="env=prod 时必须显式确认（仍建议先跑 preflight 双确认）")
    args = ap.parse_args(argv)

    if args.env == "prod" and not args.confirm_prod:
        raise ConfigError("禁止默认在 PROD 更新单据。若确需在 prod，请显式传入 --confirm-prod，并先通过 preflight 双确认。")

    cfg = load_env_config(args.env)
    secrets = load_secrets(required=True)
    auth_header_value, auth_label, raw = _auth_from_secrets(secrets)
    mcp_url = cfg.mcp_base_url

    print(f"ENV={cfg.env}  SITE={cfg.site_url}")
    print(f"FAC_MCP_ENDPOINT={mcp_url}")
    print(f"MCP_AUTH={auth_label}  VALUE={mask_secret(raw)}")
    print(f"ITEM={args.item}")

    _ = _mcp_call(
        mcp_url,
        auth_header_value,
        {"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}}, "id": 1},
    )

    # Compute per-template formulas
    theory_m_weight = round(args.thickness * args.width * args.density / 1000.0, 3)  # kg/m
    theory_sheet_weight = round(theory_m_weight * args.length / 1000.0, 3)  # kg/张
    print(f"theory_m_weight(kg/m)={theory_m_weight}  theory_sheet_weight(kg/张)={theory_sheet_weight}")

    # Fetch current item doc to preserve existing uoms rows (avoid duplicates)
    get_resp = _mcp_call(
        mcp_url,
        auth_header_value,
        {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "get_document", "arguments": {"doctype": "Item", "name": args.item}}, "id": 2},
    )
    texts = _extract_text_content(get_resp)
    parsed = _best_effort_parse_json_text(texts[0]) if texts else get_resp
    doc = _unwrap_doc(parsed)
    if not isinstance(doc, dict):
        raise ConfigError("无法解析 Item 文档。")

    existing_rows = doc.get("uoms") or []
    by_uom: Dict[str, dict] = {}
    for r in existing_rows:
        if isinstance(r, dict) and isinstance(r.get("uom"), str):
            by_uom[r["uom"]] = r

    desired: List[Tuple[str, float]] = [
        (args.stock_uom, 1.0),
        (args.purchase_uom, 1000.0),
        (args.uom_meter, float(theory_m_weight)),
        (args.uom_sheet, float(theory_sheet_weight)),
    ]

    new_uoms: List[dict] = []
    for uom, cf in desired:
        row = by_uom.get(uom, {})
        payload = {
            "doctype": "UOM Conversion Detail",
            # include row name if exists (to update instead of create)
            **({"name": row.get("name")} if isinstance(row, dict) and row.get("name") else {}),
            "uom": uom,
            "conversion_factor": cf,
        }
        new_uoms.append(payload)

    update_resp = _mcp_call(
        mcp_url,
        auth_header_value,
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "update_document", "arguments": {"doctype": "Item", "name": args.item, "data": {"uoms": new_uoms}}},
            "id": 3,
        },
    )
    utexts = _extract_text_content(update_resp)
    uparsed = _best_effort_parse_json_text(utexts[0]) if utexts else update_resp

    print("")
    print("UPDATED_UOMS:")
    print(json.dumps(uparsed, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except ConfigError as e:
        print(f"CONFIG_ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)

