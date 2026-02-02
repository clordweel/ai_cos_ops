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


def _extract_data_list(obj: Any) -> List[Any]:
    if isinstance(obj, list):
        return obj
    if not isinstance(obj, dict):
        return []
    r = obj.get("result")
    if isinstance(r, dict) and isinstance(r.get("data"), list):
        return r["data"]
    if isinstance(obj.get("data"), list):
        return obj["data"]
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
        "缺少 MCP 鉴权信息（需要 mcp_token 或 rest_api_key/rest_api_secret）。\n"
        "提示：你当前 FAC 环境已支持 Authorization: token api_key:api_secret 访问 MCP。"
    )


def _default_out_path(env: str, item_code: str) -> Path:
    safe = item_code.replace("/", "_").replace("\\", "_").replace(" ", "_")
    return repo_root() / "work" / env / "operations" / "items" / f"created_item_{safe}.json"


def _list_one(mcp_url: str, auth: str, doctype: str, filters: dict, fields: List[str]) -> Optional[dict]:
    resp = _mcp_call(
        mcp_url,
        auth,
        {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": "list_documents", "arguments": {"doctype": doctype, "filters": filters, "fields": fields, "limit": 1}},
            "id": 10,
        },
    )
    texts = _extract_text_content(resp)
    parsed = _best_effort_parse_json_text(texts[0]) if texts else resp
    data = _extract_data_list(parsed)
    if data and isinstance(data[0], dict):
        return data[0]
    return None


def _get_doc(mcp_url: str, auth: str, doctype: str, name: str) -> Any:
    resp = _mcp_call(
        mcp_url,
        auth,
        {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "get_document", "arguments": {"doctype": doctype, "name": name}}, "id": 11},
    )
    texts = _extract_text_content(resp)
    return _best_effort_parse_json_text(texts[0]) if texts else resp


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
    ap = argparse.ArgumentParser(description="基于“标准模板 - 钢板”创建 5mm 标准碳钢钢板（DEV 冒烟测试）。")
    ap.add_argument("--env", choices=["dev", "prod"], required=True)
    ap.add_argument("--template", default="标准模板 - 钢板", help="Item Parameter Template name（默认：标准模板 - 钢板）")
    ap.add_argument("--material", default="Q235B", help="材质（默认 Q235B）")
    ap.add_argument("--thickness", type=float, default=5.0, help="厚度 mm（默认 5）")
    ap.add_argument("--width", type=int, default=1500, help="宽度 mm（默认 1500）")
    ap.add_argument("--length", type=int, default=6000, help="长度 mm（默认 6000）")
    ap.add_argument("--density", type=float, default=7.85, help="密度 g/cm3（默认 7.85）")
    ap.add_argument("--source-type", default="采购", help="供应类型（默认 采购）")
    ap.add_argument("--stock-uom", default="千克", help="库存单位（默认 千克）")
    ap.add_argument("--purchase-uom", default="吨", help="采购单位（默认 吨）")
    ap.add_argument("--item-code", default="", help="物料编码（不填则自动生成）")
    ap.add_argument("--dry-run", action="store_true", help="只做检查与计算，不创建")
    ap.add_argument("--out", default="", help="保存结果到文件（默认 work/<env>/operations/items/created_item_<code>.json）")
    ap.add_argument("--confirm-prod", action="store_true", help="env=prod 时必须显式确认（仍建议先跑 preflight 双确认）")
    args = ap.parse_args(argv)

    if args.env == "prod" and not args.confirm_prod:
        raise ConfigError("禁止默认在 PROD 创建物料。若确需在 prod，请显式传入 --confirm-prod，并先通过 preflight 双确认。")

    cfg = load_env_config(args.env)
    secrets = load_secrets(required=True)
    auth_header_value, auth_label, raw = _auth_from_secrets(secrets)
    mcp_url = cfg.mcp_base_url

    print(f"ENV={cfg.env}  SITE={cfg.site_url}")
    print(f"FAC_MCP_ENDPOINT={mcp_url}")
    print(f"MCP_AUTH={auth_label}  VALUE={mask_secret(raw)}")

    _ = _mcp_call(
        mcp_url,
        auth_header_value,
        {"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}}, "id": 1},
    )

    # 1) Fetch template for constraints/default item_group
    tpl_raw = _get_doc(mcp_url, auth_header_value, "Item Parameter Template", args.template)
    tpl = _unwrap_doc(tpl_raw)
    if not isinstance(tpl, dict):
        raise ConfigError("无法解析 Item Parameter Template 文档。")
    item_group = tpl.get("item_group") or "板材"

    # 2) Validate referenced values exist (best effort)
    checks = [
        ("Item Group", "item_group_name", item_group),
        ("UOM", "name", args.stock_uom),
        ("UOM", "name", args.purchase_uom),
        ("Item Material", "name", args.material),
        ("Source Type", "name", args.source_type),
    ]
    for dt, field, value in checks:
        found = _list_one(mcp_url, auth_header_value, dt, {field: value}, ["name"])
        if not found:
            print(f"WARNING: 未找到 {dt} 记录：{field}={value!r}（创建可能失败或需调整默认值）")

    # 3) Compute fields according to template formats (simplified)
    thickness = args.thickness
    width = args.width
    length = args.length
    density = args.density

    # template formulas (as observed in the template)
    theory_m_weight = round(thickness * width * density / 1000.0, 3)  # kg/m
    theory_sheet_weight = round(theory_m_weight * length / 1000.0, 3)  # kg/张
    item_name = f"{args.material} 钢板 T{thickness:g}"
    specification = f"{thickness:g} * {width} * {length}"
    description = (
        f"规格: {specification} | 材质: {args.material} || 参考数据: "
        f"[米重: {theory_m_weight} kg/m] | [单重: {theory_sheet_weight} kg/张] || 供应: {args.source_type}"
    )

    # 4) Determine item_code
    if args.item_code.strip():
        item_code = args.item_code.strip()
    else:
        # Keep it ERPNext-friendly: ASCII + hyphen, unique enough for BOM use
        item_code = f"PLATE-{args.material}-T{thickness:g}-{width}x{length}"

    print("")
    print("PLAN:")
    print(f"- TEMPLATE={args.template}")
    print(f"- ITEM_GROUP={item_group}")
    print(f"- ITEM_CODE={item_code}")
    print(f"- ITEM_NAME={item_name}")
    print(f"- STOCK_UOM={args.stock_uom}  PURCHASE_UOM={args.purchase_uom}")
    print(f"- custom_body_material={args.material}")
    print(f"- custom_source_type={args.source_type}")
    print(f"- custom_specification={specification}")
    print(f"- theory_m_weight(kg/m)={theory_m_weight}  theory_sheet_weight(kg/张)={theory_sheet_weight}")

    # existence check
    existing = _list_one(mcp_url, auth_header_value, "Item", {"item_code": item_code}, ["name", "item_code", "item_name", "item_group"])
    if existing:
        print("")
        print("ALREADY_EXISTS:")
        print(json.dumps(existing, ensure_ascii=False, indent=2, default=str))
        return 0

    if args.dry_run:
        print("")
        print("DRY_RUN: not creating.")
        return 0

    # 5) Create Item
    data: dict = {
        "item_code": item_code,
        "item_name": item_name,
        "item_group": item_group,
        "stock_uom": args.stock_uom,
        "purchase_uom": args.purchase_uom,
        "is_stock_item": 1,
        "description": description,
        # Template binding fields (as per template)
        "custom_body_material": args.material,
        "custom_source_type": args.source_type,
        "custom_specification": specification,
        # Naming series may override item_code; keep a stable human-readable identifier.
        "custom_unique_item_name": item_code,
        # UOM conversions relative to stock_uom (千克):
        # - 吨: 1000 kg
        # - 米: kg/m (depends on thickness/width/density)
        # - 张: kg/张 (depends on thickness/width/length/density)
        "uoms": [
            {"uom": args.purchase_uom, "conversion_factor": 1000},
            {"uom": "米", "conversion_factor": float(theory_m_weight)},
            {"uom": "张", "conversion_factor": float(theory_sheet_weight)},
        ],
    }

    create_resp = _mcp_call(
        mcp_url,
        auth_header_value,
        {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "create_document", "arguments": {"doctype": "Item", "data": data, "submit": False}}, "id": 20},
    )
    texts = _extract_text_content(create_resp)
    parsed = _best_effort_parse_json_text(texts[0]) if texts else create_resp

    print("")
    print("CREATED_ITEM:")
    print(json.dumps(parsed, ensure_ascii=False, indent=2, default=str))

    out_path = Path(args.out) if args.out.strip() else _default_out_path(args.env, item_code)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"SAVED_TO={out_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except ConfigError as e:
        print(f"CONFIG_ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)

