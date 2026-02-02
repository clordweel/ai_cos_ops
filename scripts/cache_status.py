from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

from _lib_config import ConfigError, repo_root


def _stat_file(p: Path) -> dict:
    if not p.exists():
        return {"exists": False}
    st = p.stat()
    return {
        "exists": True,
        "bytes": st.st_size,
        "mtime": int(st.st_mtime),
        "age_seconds": int(time.time() - st.st_mtime),
    }


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="查看本地缓存状态（按 dev/prod 隔离）。")
    ap.add_argument("--env", choices=["dev", "prod"], required=True)
    args = ap.parse_args(argv)

    root = repo_root() / "cache" / args.env
    out: Dict[str, Any] = {"env": args.env, "cache_root": str(root)}

    out["cursor"] = {
        "index": _stat_file(root / "cursor" / "index.json"),
        "bundle": _stat_file(root / "cursor" / "bundle.md"),
    }
    out["mcp"] = {
        "initialize": _stat_file(root / "mcp" / "initialize.json"),
        "tools_list": _stat_file(root / "mcp" / "tools_list.json"),
        "meta": _stat_file(root / "mcp" / "meta.json"),
        "prompts_list": _stat_file(root / "mcp" / "prompts_list.json"),
        "prompts_meta": _stat_file(root / "mcp" / "prompts_meta.json"),
    }

    print(json.dumps(out, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except ConfigError as e:
        print(f"CONFIG_ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)

