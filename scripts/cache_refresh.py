from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from _lib_config import ConfigError, load_env_config, load_secrets, repo_root


def _now_ts() -> int:
    return int(time.time())


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_text(s: str) -> str:
    return _sha256_bytes(s.encode("utf-8"))


def _read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def _write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _write_text(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    if not s.endswith("\n"):
        s += "\n"
    p.write_text(s, encoding="utf-8")


def _http_json(method: str, url: str, headers: Dict[str, str], body: Optional[dict]) -> Tuple[int, dict]:
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers = {**headers, "Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
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


def _auth_header_from_local_secrets(secrets) -> Optional[str]:
    """
    Return an Authorization header value WITHOUT leaking token.
    Priority:
      - mcp_token (if contains ':' treat as api_key:api_secret -> token; else Bearer)
      - rest_api_key/rest_api_secret -> token
    """
    raw = secrets.mcp_token.strip()
    if raw:
        if ":" in raw and " " not in raw:
            return f"token {raw}"
        return f"Bearer {raw}"
    if secrets.rest_api_key and secrets.rest_api_secret:
        return f"token {secrets.rest_api_key}:{secrets.rest_api_secret}"
    return None


def _is_stale(p: Path, ttl_seconds: int) -> bool:
    if not p.exists():
        return True
    age = time.time() - p.stat().st_mtime
    return age > ttl_seconds


def _collect_files(root: Path, patterns: List[str]) -> List[Path]:
    out: List[Path] = []
    for pat in patterns:
        out.extend(root.glob(pat))
    # Keep only files
    out = [p for p in out if p.is_file()]
    # Stable order
    out.sort(key=lambda p: str(p).lower())
    return out


def _build_cursor_index() -> dict:
    r = repo_root()
    cmd_files = _collect_files(r, [".cursor/commands/*.md"])
    rule_files = _collect_files(r, [".cursor/rules/*.md", ".cursor/rules/*.mdc"])
    skill_files = _collect_files(r, [".cursor/skills/*/SKILL.md"])

    def entry(p: Path) -> dict:
        rel = p.relative_to(r).as_posix()
        txt = _read_text(p)
        return {
            "path": rel,
            "sha256": _sha256_text(txt),
            "bytes": len(txt.encode("utf-8", errors="replace")),
        }

    return {
        "generated_at": _now_ts(),
        "commands": [entry(p) for p in cmd_files],
        "rules": [entry(p) for p in rule_files],
        "skills": [entry(p) for p in skill_files],
    }


def _build_cursor_bundle() -> str:
    r = repo_root()
    files = _collect_files(
        r,
        [
            ".cursor/commands/*.md",
            ".cursor/skills/*/SKILL.md",
            ".cursor/rules/*.md",
            ".cursor/rules/*.mdc",
        ],
    )
    parts: List[str] = []
    parts.append("# Cursor Context Bundle (generated)\n")
    parts.append("> 注意：这是自动生成的缓存文件，用于快速浏览/检索。\n")
    for p in files:
        rel = p.relative_to(r).as_posix()
        parts.append(f"\n## {rel}\n")
        parts.append("```text\n")
        parts.append(_read_text(p).rstrip("\n"))
        parts.append("\n```\n")
    return "".join(parts)


def refresh_cursor_cache(cache_root: Path, force: bool) -> dict:
    index_path = cache_root / "cursor" / "index.json"
    bundle_path = cache_root / "cursor" / "bundle.md"

    new_index = _build_cursor_index()

    if not force and index_path.exists():
        try:
            old = json.loads(_read_text(index_path))
            if isinstance(old, dict):
                old_sig = {
                    "commands": [e.get("sha256") for e in old.get("commands", []) if isinstance(e, dict)],
                    "rules": [e.get("sha256") for e in old.get("rules", []) if isinstance(e, dict)],
                    "skills": [e.get("sha256") for e in old.get("skills", []) if isinstance(e, dict)],
                }
                new_sig = {
                    "commands": [e.get("sha256") for e in new_index.get("commands", [])],
                    "rules": [e.get("sha256") for e in new_index.get("rules", [])],
                    "skills": [e.get("sha256") for e in new_index.get("skills", [])],
                }
                if old_sig == new_sig:
                    return {"cursor": {"updated": False, "reason": "no changes"}}
        except Exception:
            pass

    _write_json(index_path, new_index)
    _write_text(bundle_path, _build_cursor_bundle())
    return {"cursor": {"updated": True, "index": str(index_path), "bundle": str(bundle_path)}}


def refresh_mcp_tools_cache(cache_root: Path, env: str, ttl_seconds: int, force: bool) -> dict:
    cfg = load_env_config(env)
    secrets = load_secrets(required=True)
    auth = _auth_header_from_local_secrets(secrets)
    if not auth:
        return {"mcp_tools": {"updated": False, "reason": "missing auth (mcp_token or rest_api_key/secret)"}}

    tools_path = cache_root / "mcp" / "tools_list.json"
    init_path = cache_root / "mcp" / "initialize.json"
    meta_path = cache_root / "mcp" / "meta.json"

    if not force and not _is_stale(tools_path, ttl_seconds):
        return {"mcp_tools": {"updated": False, "reason": "fresh (ttl)", "tools_path": str(tools_path)}}

    init = _mcp_call(
        cfg.mcp_base_url,
        auth,
        {"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}}, "id": 1},
    )
    tools = _mcp_call(cfg.mcp_base_url, auth, {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 2})

    _write_json(init_path, init)
    _write_json(tools_path, tools)
    _write_json(
        meta_path,
        {
            "generated_at": _now_ts(),
            "env": env,
            "mcp_endpoint": cfg.mcp_base_url,
            "note": "仅缓存工具元数据（不含 token）",
        },
    )
    return {"mcp_tools": {"updated": True, "tools_path": str(tools_path), "meta_path": str(meta_path)}}


def refresh_mcp_prompts_cache(cache_root: Path, env: str, ttl_seconds: int, force: bool) -> dict:
    """
    Cache FAC MCP prompts, if the server supports MCP prompt methods.

    MCP standard methods typically include:
      - prompts/list
      - prompts/get
    FAC may or may not implement these; if not, write a clear reason.
    """
    cfg = load_env_config(env)
    secrets = load_secrets(required=True)
    auth = _auth_header_from_local_secrets(secrets)
    if not auth:
        return {"mcp_prompts": {"updated": False, "reason": "missing auth (mcp_token or rest_api_key/secret)"}}

    list_path = cache_root / "mcp" / "prompts_list.json"
    meta_path = cache_root / "mcp" / "prompts_meta.json"

    if not force and not _is_stale(list_path, ttl_seconds):
        return {"mcp_prompts": {"updated": False, "reason": "fresh (ttl)", "list_path": str(list_path)}}

    # Try prompts/list; if not supported, capture error payload as the reason.
    try:
        prompts = _mcp_call(cfg.mcp_base_url, auth, {"jsonrpc": "2.0", "method": "prompts/list", "params": {}, "id": 30})
    except Exception as e:
        _write_json(
            meta_path,
            {
                "generated_at": _now_ts(),
                "env": env,
                "mcp_endpoint": cfg.mcp_base_url,
                "updated": False,
                "note": "服务器不支持 prompts/list 或鉴权不允许；无法缓存 prompts。",
                "error": str(e),
            },
        )
        return {"mcp_prompts": {"updated": False, "reason": "prompts/list not supported or unauthorized", "meta_path": str(meta_path)}}

    _write_json(list_path, prompts)
    _write_json(
        meta_path,
        {
            "generated_at": _now_ts(),
            "env": env,
            "mcp_endpoint": cfg.mcp_base_url,
            "updated": True,
            "note": "仅缓存 prompts/list 元数据（不含 token）",
        },
    )
    return {"mcp_prompts": {"updated": True, "list_path": str(list_path), "meta_path": str(meta_path)}}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="刷新本地缓存（按 dev/prod 隔离）：MCP tools + Cursor prompts/skills/rules。")
    ap.add_argument("--env", choices=["dev", "prod"], required=True)
    ap.add_argument("--force", action="store_true", help="强制刷新（忽略 TTL/变更检测）")
    ap.add_argument("--ttl-hours", type=int, default=24, help="MCP tools 缓存 TTL（小时，默认 24）")
    ap.add_argument(
        "--what",
        choices=["all", "mcp_tools", "mcp_prompts", "cursor"],
        default="all",
        help="刷新哪些缓存",
    )
    args = ap.parse_args(argv)

    cache_root = repo_root() / "cache" / args.env
    cache_root.mkdir(parents=True, exist_ok=True)

    out: dict = {"env": args.env, "cache_root": str(cache_root), "generated_at": _now_ts()}
    ttl_seconds = max(1, args.ttl_hours) * 3600

    if args.what in ("all", "cursor"):
        out.update(refresh_cursor_cache(cache_root, force=args.force))
    if args.what in ("all", "mcp_tools"):
        out.update(refresh_mcp_tools_cache(cache_root, env=args.env, ttl_seconds=ttl_seconds, force=args.force))
    if args.what in ("all", "mcp_prompts"):
        out.update(refresh_mcp_prompts_cache(cache_root, env=args.env, ttl_seconds=ttl_seconds, force=args.force))

    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except ConfigError as e:
        print(f"CONFIG_ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)

