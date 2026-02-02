from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigError(RuntimeError):
    pass


def _strip_inline_comment(s: str) -> str:
    # Very small YAML subset: treat `#` as comment if preceded by whitespace.
    in_quotes = False
    quote_char = ""
    for i, ch in enumerate(s):
        if ch in ("'", '"'):
            if not in_quotes:
                in_quotes = True
                quote_char = ch
            elif quote_char == ch:
                in_quotes = False
                quote_char = ""
        if ch == "#" and not in_quotes:
            if i == 0 or s[i - 1].isspace():
                return s[:i].rstrip()
    return s.strip()


def parse_simple_yaml(path: Path) -> Dict[str, Any]:
    """
    Parse a very small subset of YAML:
    - top-level `key: value` pairs
    - ignores blank lines and comments
    - values are treated as strings, with surrounding quotes stripped

    This is intentional to avoid extra dependencies for this repo.
    """
    if not path.exists():
        raise ConfigError(f"配置文件不存在：{path}")

    data: Dict[str, Any] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ConfigError(f"不支持的 YAML 行（仅支持 key: value）：{path} :: {raw_line}")
        key, rest = line.split(":", 1)
        key = key.strip()
        value = _strip_inline_comment(rest.strip())
        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        data[key] = value
    return data


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class EnvConfig:
    env: str
    label: str
    site_url: str
    rest_base_url: str
    mcp_base_url: str
    expected_host_contains: str = ""
    server_host: str = ""
    description: str = ""


@dataclass(frozen=True)
class Secrets:
    rest_api_key: str = ""
    rest_api_secret: str = ""
    mcp_token: str = ""


def load_env_config(env: str) -> EnvConfig:
    p = repo_root() / "config" / "environments" / f"{env}.yaml"
    d = parse_simple_yaml(p)

    def req(k: str) -> str:
        v = str(d.get(k, "")).strip()
        if not v:
            raise ConfigError(f"环境配置缺少必填字段 `{k}`：{p}")
        return v

    cfg = EnvConfig(
        env=req("env"),
        label=str(d.get("label", "")).strip() or env.upper(),
        description=str(d.get("description", "")).strip(),
        site_url=req("site_url"),
        rest_base_url=req("rest_base_url"),
        mcp_base_url=req("mcp_base_url"),
        expected_host_contains=str(d.get("expected_host_contains", "")).strip(),
        server_host=str(d.get("server_host", "")).strip(),
    )
    if cfg.env != env:
        raise ConfigError(f"环境文件 env 不匹配：期望 {env}，实际 {cfg.env}（{p}）")
    return cfg


def load_secrets(required: bool) -> Secrets:
    p = repo_root() / "config" / "secrets.local.yaml"
    if not p.exists():
        if required:
            raise ConfigError(
                "缺少本地密钥文件：config/secrets.local.yaml\n"
                "请从 config/secrets.example.yaml 复制并填写，然后重试。"
            )
        return Secrets()

    d = parse_simple_yaml(p)
    return Secrets(
        rest_api_key=str(d.get("rest_api_key", "")).strip(),
        rest_api_secret=str(d.get("rest_api_secret", "")).strip(),
        mcp_token=str(d.get("mcp_token", "")).strip(),
    )


def mask_secret(s: str, keep: int = 4) -> str:
    s = s.strip()
    if not s:
        return ""
    if len(s) <= keep:
        return "*" * len(s)
    return "*" * (len(s) - keep) + s[-keep:]

