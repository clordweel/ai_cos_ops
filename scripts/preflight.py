from __future__ import annotations

import argparse
import os
import sys
from textwrap import dedent

from _lib_config import ConfigError, load_env_config, load_secrets, mask_secret


def _banner(title: str) -> str:
    pad = 4
    w = max(60, len(title) + pad * 2)
    top = "=" * w
    mid = title.center(w)
    return f"{top}\n{mid}\n{top}"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description="环境预检（dev/prod）：输出醒目标识，并在高风险操作前加护栏。",
    )
    ap.add_argument("--env", choices=["dev", "prod"], required=True, help="目标环境")
    ap.add_argument(
        "--operation",
        choices=["read", "write", "migration"],
        default="read",
        help="风险等级（写入/迁移会触发更严格护栏）",
    )
    ap.add_argument(
        "--confirm-prod",
        action="store_true",
        help="当 env=prod 且 operation=write/migration 时必须显式确认",
    )
    args = ap.parse_args(argv)

    cfg = load_env_config(args.env)
    secrets_required = args.operation in ("write", "migration")
    secrets = load_secrets(required=secrets_required)

    title = f"[{cfg.label}]  ENV={cfg.env}   OP={args.operation}"
    out = [_banner(title), ""]

    out.append(f"ENV           : {cfg.env}")
    out.append(f"LABEL         : {cfg.label}")
    if cfg.description:
        out.append(f"DESCRIPTION   : {cfg.description}")
    out.append(f"SITE_URL      : {cfg.site_url}")
    out.append(f"REST_BASE_URL : {cfg.rest_base_url}")
    out.append(f"MCP_BASE_URL  : {cfg.mcp_base_url}")
    if cfg.server_host:
        out.append(f"SERVER_HOST   : {cfg.server_host}")

    if cfg.expected_host_contains:
        ok = cfg.expected_host_contains in cfg.site_url and cfg.expected_host_contains in cfg.rest_base_url
        out.append(f"EXPECTED_HOST : contains '{cfg.expected_host_contains}' -> {'OK' if ok else 'MISMATCH'}")
        if not ok:
            out.append("")
            out.append("ERROR: 站点地址疑似填错环境（expected_host_contains 不匹配）。请立即停止。")
            print("\n".join(out))
            return 2

    if secrets.rest_api_key or secrets.rest_api_secret:
        out.append(f"REST_API_KEY  : {mask_secret(secrets.rest_api_key)}")
        out.append(f"REST_API_SEC  : {mask_secret(secrets.rest_api_secret)}")
    else:
        out.append("REST_API_KEY  : (empty)")
        out.append("REST_API_SEC  : (empty)")
        if secrets_required:
            out.append("ERROR: 写入/迁移操作要求本地密钥文件存在并填写。")
            print("\n".join(out))
            return 2

    if cfg.env == "prod" and args.operation in ("write", "migration"):
        env_ok = os.getenv("I_UNDERSTAND_PROD", "") == "YES"
        flag_ok = bool(args.confirm_prod)
        out.append("")
        out.append("DANGER: 你正在对 PROD 执行高风险操作（write/migration）。")
        out.append("        需要双确认：I_UNDERSTAND_PROD=YES 且 --confirm-prod")
        out.append(f"I_UNDERSTAND_PROD=YES : {'OK' if env_ok else 'MISSING'}")
        out.append(f"--confirm-prod        : {'OK' if flag_ok else 'MISSING'}")
        if not (env_ok and flag_ok):
            out.append("")
            out.append("BLOCKED: 未满足生产双确认护栏，本次操作已阻止。")
            print("\n".join(out))
            return 3

    out.append("")
    out.append(
        dedent(
            """\
            NEXT:
            - 优先走 MCP；如需 REST 兜底，先跑 scripts/rest_smoke.py 进行连通与鉴权验证。
            - 任何写操作都必须最小化影响面，并提供回滚与验证步骤。
            """
        ).rstrip()
    )
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except ConfigError as e:
        print(f"CONFIG_ERROR: {e}", file=sys.stderr)
        raise SystemExit(2)

