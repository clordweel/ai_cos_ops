from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
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
        with urllib.request.urlopen(req, timeout=60) as resp:
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


def _profiles_path() -> Path:
    return repo_root() / "config" / "template_item_profiles.json"


def _load_json(path: Path) -> Any:
    if not path.exists():
        raise ConfigError(f"配置文件不存在：{path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ConfigError(f"配置文件不是合法 JSON：{path}\n{e}")


def _timestamp_slug() -> str:
    return time.strftime("%Y%m%d_%H%M%S")


def _default_out_path(env: str, profile: str) -> Path:
    return repo_root() / "work" / env / "operations" / "batches" / f"{_timestamp_slug()}_create_items_from_template_{profile}.json"


def _run_preflight(env: str, confirm_prod: bool) -> None:
    py = sys.executable
    cmd = [py, str(repo_root() / "scripts" / "preflight.py"), "--env", env, "--operation", "write"]
    if env == "prod" and confirm_prod:
        cmd.append("--confirm-prod")
    subprocess.run(cmd, check=True)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="按 Item Parameter Template 批量创建/更新 Item（低上下文：run_python_code 一次完成）。"
    )
    ap.add_argument("--env", choices=["dev", "prod"], required=True)
    ap.add_argument("--profile", required=True, help="使用哪个 profile（见 config/template_item_profiles.json）")
    ap.add_argument("--mode", choices=["create_only", "skip_existing", "upsert"], default="", help="覆盖 profile 默认 mode")
    ap.add_argument("--dry-run", action="store_true", help="只计算/校验，不写入")
    ap.add_argument("--confirm-prod", action="store_true", help="env=prod 时必须显式确认（仍需 preflight 双确认）")
    ap.add_argument("--skip-preflight", action="store_true", help="跳过 preflight（不推荐）")
    ap.add_argument("--spec", default="", help="批量 spec JSON 文件路径（items 数组）")
    ap.add_argument("--items-json", default="", help="直接传 items JSON 数组（少量时使用）")
    ap.add_argument("--out", default="", help="保存执行结果到文件（默认 work/<env>/operations/batches/...json）")
    args = ap.parse_args(argv)

    if args.env == "prod" and not args.confirm_prod:
        raise ConfigError("禁止默认对 PROD 执行批量创建/更新。若确需在 prod，请显式传入 --confirm-prod，并先通过 preflight 双确认。")

    profile_cfg = _load_json(_profiles_path())
    profiles = profile_cfg.get("profiles")
    if not isinstance(profiles, dict) or args.profile not in profiles or not isinstance(profiles[args.profile], dict):
        avail = ", ".join(sorted([k for k in profiles.keys() if isinstance(k, str)])) if isinstance(profiles, dict) else ""
        raise ConfigError(f"未找到 profile={args.profile}。可用：{avail}")
    profile = profiles[args.profile]

    # Load items
    items: Any = None
    if args.spec.strip():
        items = _load_json(Path(args.spec.strip()))
    elif args.items_json.strip():
        try:
            items = json.loads(args.items_json)
        except Exception as e:
            raise ConfigError(f"--items-json 不是合法 JSON：{e}")
    else:
        raise ConfigError("必须提供 --spec 或 --items-json。")
    if not isinstance(items, list) or not items:
        raise ConfigError("items 必须是非空数组。")

    mode = args.mode.strip() or str(profile.get("mode_default") or "upsert")
    if mode not in ("create_only", "skip_existing", "upsert"):
        raise ConfigError(f"mode 不合法：{mode}")

    cfg = load_env_config(args.env)
    secrets = load_secrets(required=True)
    auth_header_value, auth_label, raw = _auth_from_secrets(secrets)
    mcp_url = cfg.mcp_base_url

    print(f"ENV={cfg.env}  SITE={cfg.site_url}")
    print(f"FAC_MCP_ENDPOINT={mcp_url}")
    print(f"MCP_AUTH={auth_label}  VALUE={mask_secret(raw)}")
    print(f"PROFILE={args.profile}  MODE={mode}  DRY_RUN={args.dry_run}")
    print(f"ITEMS={len(items)}")

    if not args.dry_run and not args.skip_preflight:
        _run_preflight(args.env, confirm_prod=args.confirm_prod)

    _ = _mcp_call(
        mcp_url,
        auth_header_value,
        {"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}}, "id": 1},
    )

    # Server-side execution spec (keep it small; data stays server-side).
    exec_spec = {
        "profile": args.profile,
        "mode": mode,
        "dry_run": bool(args.dry_run),
        "template_doctype": profile.get("template_doctype", "Item Parameter Template"),
        "template_name": profile.get("template_name"),
        "target_doctype": profile.get("target_doctype", "Item"),
        "id_field": profile.get("id_field", "custom_unique_item_name"),
        "hash_field": profile.get("hash_field", ""),
        "id_format": profile.get("id_format", ""),
        "uom_rules": profile.get("uom_rules") or [],
        "items": items,
    }

    # NOTE: run_python_code forbids import statements; use frappe + json already available.
    code = f"""
spec = {exec_spec!r}
profile = spec.get("profile")
mode = spec.get("mode", "upsert")
dry_run = bool(spec.get("dry_run"))
template_doctype = spec.get("template_doctype") or "Item Parameter Template"
template_name = spec.get("template_name")
target_doctype = spec.get("target_doctype") or "Item"
id_field = spec.get("id_field") or "custom_unique_item_name"
hash_field = spec.get("hash_field") or ""
id_format = spec.get("id_format") or ""
uom_rules = spec.get("uom_rules") or []
items = spec.get("items") or []

def md5_hex(s: str) -> str:
    # Avoid python imports (restricted by run_python_code security).
    # Use database MD5() for deterministic hash.
    s = "" if s is None else str(s)
    return frappe.db.sql("select md5(%s)", (s,), pluck=True)[0]

def render(s, ctx):
    if s is None:
        return ""
    s = str(s)
    if not s:
        return ""
    return frappe.render_template(s, ctx)

def to_float(v):
    if v in (None, ""):
        return None
    try:
        return float(v)
    except Exception:
        return None

def to_int(v):
    if v in (None, ""):
        return None
    try:
        return int(float(v))
    except Exception:
        return None

def canonical_float(v):
    v = to_float(v)
    if v is None:
        return ""
    if float(v).is_integer():
        return str(int(v))
    s = ("%.6f" % float(v)).rstrip("0").rstrip(".")
    return s

tpl = frappe.get_doc(template_doctype, template_name)
param_defs = list(tpl.get("parameters") or [])

def build_context(user_params):
    ctx = {{}}
    # 1) seed with user input
    for k, v in (user_params or {{}}).items():
        ctx[str(k)] = v
    # 2) fill / compute in idx order
    for row in sorted(param_defs, key=lambda r: r.get("idx") or 0):
        pname = row.get("parameter_name")
        if not pname:
            continue
        pname = str(pname)
        ctype = row.get("constraint_type") or ""
        default_raw = row.get("parameter_default_value")
        if pname not in ctx or ctx.get(pname) in (None, ""):
            # default may be format using other params
            if default_raw not in (None, ""):
                ctx[pname] = render(default_raw, ctx)
        # coerce types
        if ctype == "Float":
            # Store as canonical string to avoid "5.0" vs "5" drift in IDs / names.
            ctx[pname] = canonical_float(ctx.get(pname))
        elif ctype == "Integer":
            i = to_int(ctx.get(pname))
            ctx[pname] = i if i is not None else ctx.get(pname)
        elif ctype == "Format":
            # For format fields, render template using current ctx
            ctx[pname] = render(default_raw, ctx)
        elif ctype == "Doctype":
            # keep as string
            if ctx.get(pname) is not None:
                ctx[pname] = str(ctx.get(pname))
    return ctx

def validate_ctx(ctx):
    errs = []
    for row in param_defs:
        pname = row.get("parameter_name")
        if not pname:
            continue
        pname = str(pname)
        optional = int(row.get("optional") or 0)
        if optional == 0:
            if ctx.get(pname) in (None, ""):
                errs.append("missing required param: " + pname)
        ctype = row.get("constraint_type") or ""
        if ctype == "Doctype":
            dt = row.get("doctype_selector")
            v = ctx.get(pname)
            if dt and v not in (None, ""):
                if not frappe.db.exists(str(dt), str(v)):
                    errs.append("invalid doctype value: " + pname + "=" + str(v) + " (doctype=" + str(dt) + ")")
    return errs

def compute_id(ctx):
    if id_format:
        return render(id_format, ctx)
    # fallback: join_to_hash params
    parts = []
    for row in param_defs:
        if int(row.get("join_to_hash") or 0) == 1:
            pname = row.get("parameter_name")
            if pname:
                parts.append(str(pname) + "=" + str(ctx.get(str(pname))))
    return "ITEM-" + frappe.generate_hash(length=12) if not parts else "ITEM-" + md5_hex("|".join(parts))

def compute_hash(ctx):
    parts = []
    for row in sorted(param_defs, key=lambda r: r.get("idx") or 0):
        if int(row.get("join_to_hash") or 0) == 1:
            pname = row.get("parameter_name")
            if pname:
                parts.append(str(pname) + "=" + str(ctx.get(str(pname))))
    return md5_hex("|".join(parts)) if parts else ""

def build_item_data(ctx, unique_id):
    data = {{}}
    data["item_group"] = tpl.get("item_group") or ""
    # bind fields to Item
    for row in param_defs:
        if int(row.get("binding_field") or 0) != 1:
            continue
        target = row.get("target_field")
        pname = row.get("parameter_name")
        if target and pname:
            data[str(target)] = ctx.get(str(pname))
    # stable id (naming may override item_code)
    data[id_field] = unique_id
    if hash_field:
        data[hash_field] = compute_hash(ctx)
    return data

def build_uoms(ctx):
    out = []
    # Apply uom_rules (allows dynamic conversion factors)
    for r in uom_rules:
        if not isinstance(r, dict):
            continue
        u = r.get("uom")
        if not u:
            continue
        if "conversion_factor_expr" in r and r.get("conversion_factor_expr"):
            cf = render(r.get("conversion_factor_expr"), ctx)
            try:
                cf = float(cf)
            except Exception:
                cf = 0.0
        else:
            cf = r.get("conversion_factor", 0)
            try:
                cf = float(cf)
            except Exception:
                cf = 0.0
        out.append({{"uom": str(u), "conversion_factor": cf}})
    return out

results = []
for idx, it in enumerate(items, start=1):
    user_params = it.get("params") if isinstance(it, dict) else None
    ctx = build_context(user_params)
    errs = validate_ctx(ctx)
    unique_id = compute_id(ctx)
    param_hash = compute_hash(ctx) if hash_field else ""
    if errs:
        results.append({{"idx": idx, "status": "error", "id": unique_id, "hash": param_hash, "errors": errs}})
        continue

    existing_name = None
    if hash_field and param_hash:
        existing_name = frappe.db.get_value(target_doctype, {{hash_field: param_hash}}, "name")
    if not existing_name and unique_id:
        existing_name = frappe.db.get_value(target_doctype, {{id_field: unique_id}}, "name")
    if existing_name and mode in ("create_only", "skip_existing"):
        results.append({{"idx": idx, "status": "exists", "id": unique_id, "hash": param_hash, "name": existing_name}})
        continue

    data = build_item_data(ctx, unique_id)
    uoms = build_uoms(ctx)
    if uoms:
        data["uoms"] = uoms

    if dry_run:
        # keep only small preview
        results.append({{"idx": idx, "status": "dry_run", "id": unique_id, "hash": param_hash, "data_keys": sorted(list(data.keys()))}})
        continue

    if existing_name and mode == "upsert":
        doc = frappe.get_doc(target_doctype, existing_name)
        for k, v in data.items():
            if k == "uoms":
                continue
            doc.set(k, v)
        doc.save()
        # child table: use direct document API (stable)
        if uoms:
            by_uom = {{row.uom: row for row in doc.uoms}}
            for r in uoms:
                uom = r.get("uom")
                cf = float(r.get("conversion_factor") or 0)
                if uom in by_uom:
                    by_uom[uom].conversion_factor = cf
                else:
                    doc.append("uoms", {{"uom": uom, "conversion_factor": cf}})
            doc.save()
        results.append({{"idx": idx, "status": "updated", "id": unique_id, "hash": param_hash, "name": doc.name}})
        continue

    doc = frappe.new_doc(target_doctype)
    for k, v in data.items():
        if k == "uoms":
            continue
        doc.set(k, v)
    # insert first so we have parent, then append children
    doc.insert()
    if uoms:
        for r in uoms:
            doc.append("uoms", {{"uom": r.get("uom"), "conversion_factor": float(r.get("conversion_factor") or 0)}})
        doc.save()
    results.append({{"idx": idx, "status": "created", "id": unique_id, "hash": param_hash, "name": doc.name}})

summary = {{
  "profile": profile,
  "mode": mode,
  "dry_run": dry_run,
  "count": len(results),
  "ok": len([r for r in results if r.get("status") in ("created","updated","exists","dry_run")]),
  "errors": len([r for r in results if r.get("status") == "error"]),
}}
print(summary)
"""

    resp = _mcp_call(
        mcp_url,
        auth_header_value,
        {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "run_python_code", "arguments": {"code": code}}, "id": 2},
    )
    texts = _extract_text_content(resp)
    text0 = texts[0] if texts else ""
    parsed = _best_effort_parse_json_text(text0) if text0 else resp

    out_path = Path(args.out) if args.out.strip() else _default_out_path(args.env, args.profile)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"request": exec_spec, "response": parsed}, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    ok = False
    try:
        if isinstance(parsed, dict) and parsed.get("success") is True:
            r = parsed.get("result")
            if isinstance(r, dict) and r.get("success") is True:
                ok = True
    except Exception:
        ok = False

    print("")
    print("DONE.")
    print(f"RESULT_SAVED_TO={out_path}")
    if not ok:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except subprocess.CalledProcessError as e:
        print(f"SUBPROCESS_ERROR: exit={e.returncode}", file=sys.stderr)
        raise SystemExit(int(e.returncode) if e.returncode else 2)
    except ConfigError as e:
        print(f"CONFIG_ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)

