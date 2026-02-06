---
description: "安全护栏：强制区分 dev/prod，避免误操作生产"
alwaysApply: true
---

## 一句话原则

在本项目里，**“我现在操作的是 dev 还是 prod？”** 必须在任何动作前被明确回答，并且能被脚本验证。

## 必须遵守（最高优先级）

- **任何写操作（高风险）**：创建/更新/删除数据、Patch、权限、迁移、批量修复，都必须先完成：
  - 运行：`python scripts/preflight.py --env <dev|prod> --operation write`
  - 并在输出里确认：`ENV`、`SITE_URL`、`MCP_URL` 与目标一致
- **默认不对生产写入**：
  - 只有在用户明确要求“对 prod 写操作”时才允许继续
  - 即便允许，仍需要双确认护栏（`--confirm-prod` + `I_UNDERSTAND_PROD=YES`）

## 禁止项

- **不要把密钥写进仓库**：任何 API key/secret/token 都必须只放在 `config/secrets.local.yaml`（已被忽略）。
- **不要默认使用 bench CLI**：除非明确处于“已远程连入服务器且 bench 可用”的上下文，否则 bench 不可作为主要方案。

## 输出规范（每次给步骤前先写这段）

- 目标环境：dev / prod
- 目标站点：`site_url`
- 首选通道：MCP（优先）/ REST（兜底）
- 风险等级：read / write / migration
