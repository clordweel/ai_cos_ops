---
description: "REST 兜底规范：Frappe API 调用、鉴权与最小化写入"
globs:
  - "scripts/**"
  - "docs/**"
alwaysApply: false
---

## REST 使用前提

- REST 仅作为 **MCP 不可用/不覆盖能力** 时的兜底。
- 任何写操作先跑：`python scripts/preflight.py --env <dev|prod> --operation write`

## 鉴权（Frappe 常见 token 方式）

- 使用 Header：
  - `Authorization: token <api_key>:<api_secret>`
- `api_key` / `api_secret` 从本地 `config/secrets.local.yaml` 读取（不要写死到代码/文档）。

## 调用顺序（建议）

1. `GET /api/method/frappe.ping`（连通性）
2. `GET /api/method/frappe.auth.get_logged_user`（鉴权验证）
3. 只在必要时执行写入，并限制影响面、附带回滚与验证步骤。
