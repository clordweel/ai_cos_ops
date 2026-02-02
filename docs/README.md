# docs 索引（ai_cos_ops）

本目录存放“可提交到仓库”的项目说明文档，目标是让新组员可以在最短时间内掌握：**环境护栏、MCP-first 工作方式、迁移规范、源码事实确认方法**。

## 推荐阅读顺序（新组员 30 分钟）

1. `docs/session-digest.md`：本次会话成果归档（你最需要先看的一篇）
2. `AGENTS.md`：AI 全局约束（尤其是 dev/prod 写入与迁移护栏）
3. `docs/environments.md`：环境配置与环境确认流程
4. `docs/mcp-and-rest.md`：MCP 优先、REST 兜底
5. `docs/project-map.md`：项目地图（cos / FAC / raven 的边界）
6. `docs/source-references.md`：源码参考地址与“无法访问远程源码”的处理方式
7. `docs/migration.md`：dev -> prod 迁移 checklist（非常谨慎）

## 文档清单

| 文档 | 解决什么问题 | 什么时候读 |
| --- | --- | --- |
| `docs/session-digest.md` | 会话成果总览：rules/skills/commands/scripts、cache/work、推荐流程 | 第一次打开仓库就读 |
| `docs/project-map.md` | 组件边界：Frappe/ERPNext/HRMS、cos 二开、FAC MCP、raven | 不清楚“谁负责什么”时 |
| `docs/environments.md` | dev/prod 配置位置、密钥策略、执行前环境确认 | 任何脚本/操作之前 |
| `docs/mcp-and-rest.md` | 统一调用范式：MCP-first、REST fallback | MCP 不通/能力不够时 |
| `docs/source-references.md` | 源码仓库清单 + 事实确认流程（避免臆测） | 需要“向源码确认”时 |
| `docs/migration.md` | dev -> prod 迁移前提与 checklist | 准备上线/迁移时 |

## 常用入口（给组员的“怎么用”）

### Cursor 入口

- **Slash Commands**：`.cursor/commands/`（在 Cursor Chat 输入 `/` 选择）  
  - 常用：`/onboard-new-developer`、`/init-reference-data`、`/fetch-reference-doc`、`/list-item-groups`、`/refresh-cache`、`/migration-dev-to-prod`
- **Skills**：`.cursor/skills/`（需要时显式调用，默认不占用上下文）  
  - 常用：`/env-safety`、`/mcp-first`、`/migration-safety`、`/context-budget`

### CLI 入口（确定性 + 可复现）

脚本目录：`scripts/`（总览见 `scripts/README.md`）

- 预检（推荐任何动作前先跑）：`python scripts/preflight.py --env dev --operation read`
- 初始化 reference（新组员上手）：`python scripts/init_reference_data.py --env dev`
- MCP 连通：`python scripts/mcp_ping.py --env dev`
- REST 自检：`python scripts/rest_smoke.py --env dev`
- 缓存：`python scripts/cache_status.py --env dev` / `python scripts/cache_refresh.py --env dev`

### 密钥模板（不要提交）

- 模板：`config/secrets.example.yaml`
- 本地文件：`config/secrets.local.yaml`（已被 `.gitignore` 忽略，绝不提交）
