from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

from _lib_config import ConfigError, repo_root


def _run(cmd: list[str]) -> None:
    print("")
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def _default_ref_dir(env: str) -> Path:
    return repo_root() / "work" / env / "reference"


def _default_profiles_path() -> Path:
    return repo_root() / "config" / "reference_profiles.json"


def _load_profiles(path: Path) -> dict:
    if not path.exists():
        raise ConfigError(f"reference 配置文件不存在：{path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ConfigError(f"reference 配置文件不是合法 JSON：{path}\n{e}")


def _select_profile(cfg: dict, profile: str) -> Tuple[str, List[dict]]:
    profiles = cfg.get("profiles")
    if not isinstance(profiles, dict):
        raise ConfigError("reference 配置缺少 profiles（应为对象）。")
    p = profiles.get(profile)
    if not isinstance(p, dict):
        names = ", ".join(sorted([k for k in profiles.keys() if isinstance(k, str)]))
        raise ConfigError(f"未找到 profile={profile}。可用 profiles：{names}")
    items = p.get("items")
    if not isinstance(items, list) or not items:
        raise ConfigError(f"profile={profile} 缺少 items（应为非空数组）。")
    desc = p.get("description")
    return (str(desc or "").strip(), items)


def _kv_to_cli_args(d: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for k, v in d.items():
        if not isinstance(k, str) or not k.strip():
            continue
        flag = f"--{k.strip()}"
        if isinstance(v, bool):
            if v:
                out.append(flag)
            continue
        if v is None:
            continue
        out.extend([flag, str(v)])
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="初始化 work/<env>/reference：按配置从目标环境拉取 reference 资料（MCP 优先，只读）。",
    )
    ap.add_argument("--env", choices=["dev", "prod"], required=True, help="目标环境")
    ap.add_argument(
        "--config",
        default="",
        help="可选：reference 配置文件路径（默认 config/reference_profiles.json）",
    )
    ap.add_argument(
        "--profile",
        default="default",
        help="使用哪个 reference profile（默认 default）",
    )
    ap.add_argument(
        "--list-profiles",
        action="store_true",
        help="列出可用 profiles 并退出",
    )
    ap.add_argument(
        "--ref-dir",
        default="",
        help="可选：自定义 reference 输出目录（默认 work/<env>/reference）",
    )
    ap.add_argument(
        "--skip-preflight",
        action="store_true",
        help="跳过 preflight（不推荐；默认会先跑 preflight --operation read）",
    )
    args = ap.parse_args(argv)

    env = args.env
    ref_dir = Path(args.ref_dir) if args.ref_dir.strip() else _default_ref_dir(env)
    ref_dir.mkdir(parents=True, exist_ok=True)

    py = sys.executable

    cfg_path = Path(args.config) if args.config.strip() else _default_profiles_path()
    cfg = _load_profiles(cfg_path)
    profiles = cfg.get("profiles")
    if args.list_profiles:
        if not isinstance(profiles, dict):
            raise ConfigError(f"配置文件缺少 profiles：{cfg_path}")
        print(f"CONFIG={cfg_path}")
        print("PROFILES:")
        for name in sorted([k for k in profiles.keys() if isinstance(k, str)]):
            obj = profiles.get(name, {})
            desc = str(obj.get("description", "")).strip() if isinstance(obj, dict) else ""
            suffix = f" - {desc}" if desc else ""
            print(f"- {name}{suffix}")
        return 0

    profile_desc, items = _select_profile(cfg, args.profile)
    print(f"ENV={env}")
    print(f"CONFIG={cfg_path}")
    print(f"PROFILE={args.profile}" + (f"  ({profile_desc})" if profile_desc else ""))
    if not args.skip_preflight:
        _run([py, str(repo_root() / "scripts" / "preflight.py"), "--env", env, "--operation", "read"])

    saved: List[Path] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            raise ConfigError(f"profile items[{idx}] 不是对象：{item!r}")
        script = item.get("script")
        out_name = item.get("out")
        args_obj = item.get("args") or {}

        if not isinstance(script, str) or not script.strip():
            raise ConfigError(f"profile items[{idx}] 缺少 script（必须是字符串）。")
        if not isinstance(out_name, str) or not out_name.strip():
            raise ConfigError(f"profile items[{idx}] 缺少 out（必须是字符串文件名）。")
        if not isinstance(args_obj, dict):
            raise ConfigError(f"profile items[{idx}].args 必须是对象（key->value）。")

        script_path = repo_root() / script
        out_path = ref_dir / out_name
        out_path.parent.mkdir(parents=True, exist_ok=True)

        cli_args = _kv_to_cli_args({k: v for k, v in args_obj.items()})
        _run([py, str(script_path), "--env", env, *cli_args, "--out", str(out_path)])
        saved.append(out_path)

    print("")
    print("DONE. Saved reference files:")
    for p in saved:
        print(f"- {p}")
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

