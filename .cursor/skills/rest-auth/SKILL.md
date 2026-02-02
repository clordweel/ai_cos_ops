---
name: rest-auth
description: Frappe REST 鉴权与只读自检（API key + secret）
disable-model-invocation: true
---

# Frappe REST 鉴权与只读自检

## 何时使用

- MCP 不可用/不覆盖能力，需要 REST 兜底
- 你要先确认 REST 连通性与 token 是否有效

## 鉴权方式（API key + secret）

Header：

- `Authorization: token <api_key>:<api_secret>`

密钥来源：

- 本地 `config/secrets.local.yaml`（不要提交）

## 自检脚本（只读）

```bash
python scripts/rest_smoke.py --env dev
```

脚本会依次调用：

1. `GET /api/method/frappe.ping`
2. `GET /api/method/frappe.auth.get_logged_user`（带 token）

## 安全约束

- 写操作前必须跑 `scripts/preflight.py --operation write`
- 生产写入必须启用双确认护栏（见 `scripts/preflight.py`）

## 参考

- @docs/mcp-and-rest.md
- @scripts/rest_smoke.py

