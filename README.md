# ai_cos_ops（Cursor AI 协作环境包）

这是一个**可直接提交到仓库**的 Cursor AI 协作环境，用于帮助开发组员快速理解并安全地在以下体系上开展二开与 AI 改造：

- **基建**：Frappe v16 + ERPNext v16 + HRMS v16
- **二开业务**：`cos`（`https://github.com/clordweel/cos`）
- **服务端 MCP**：`Frappe_Assistant_Core`（`https://github.com/buildswithpaul/Frappe_Assistant_Core`）
- **用户端 AI 改造**：`raven`（`https://github.com/The-Commit-Company/raven`）

## 核心原则（非常重要）

- **优先 MCP，其次 REST API**：除非远程连入服务器，否则本地 **`bench` CLI 不可用**。
- **强区分 dev / prod**：开发与生产各自一套系统，数据差异很大；任何写操作都必须走护栏（见 `scripts/preflight.py`）。
- **地址可提交、密钥绝不提交**：地址放在 `config/environments/*.yaml`；密钥放在本地 `config/secrets.local.yaml`（被 `.gitignore` 忽略）。

## 快速开始

1. 复制密钥模板到本地文件（不要提交）：
   - 从 `config/secrets.example.yaml` 复制为 `config/secrets.local.yaml`，填入 API Key / Secret。
2. 填写环境地址（可提交）：
   - `config/environments/dev.yaml`
   - `config/environments/prod.yaml`
3. 连通性与环境确认：
   - `python scripts/preflight.py --env dev --operation read`
   - `python scripts/mcp_ping.py --env dev`
   - `python scripts/rest_smoke.py --env dev`

Windows 如果 `python` 不可用，使用：

- `py scripts/preflight.py --env dev --operation read`
- `py scripts/mcp_ping.py --env dev`
- `py scripts/rest_smoke.py --env dev --user-info`

## Cursor（团队复用）

### Slash Commands（推荐）

在 Cursor 的 Agent Chat 里输入 `/`，你会看到项目内命令（来自 `.cursor/commands/`），例如：

- `/onboard-new-developer`
- `/feature-implementation`
- `/bugfix`
- `/migration-dev-to-prod`
- `/ops-data-operation`
- `/init-reference-data`
- `/fetch-reference-doc`
- `/list-item-groups`
- `/list-uoms`
- `/list-companies`
- `/create-test-ac-contactor`
- `/context-budget`

### Skills（可复用技能包）

项目内 skills 存放在 `.cursor/skills/`，可在 Agent Chat 输入 `/` 后选择调用，例如：

- `/env-safety`
- `/mcp-first`
- `/rest-auth`
- `/migration-safety`
- `/context-budget`

## 文档入口

- `AGENTS.md`：全局 AI 行为约束（环境护栏、MCP-first、迁移规范）
- `docs/README.md`：docs 索引（推荐阅读顺序 + 文档清单 + 常用入口）
- `docs/project-map.md`：项目地图（cos / MCP / raven 的边界与协作）
- `docs/environments.md`：dev/prod 区分与护栏
- `docs/mcp-and-rest.md`：MCP 优先、REST 兜底的调用范式
- `docs/migration.md`：从 dev 到 prod 的迁移流程（极谨慎）
- `docs/source-references.md`：源码参考地址清单（用于“向源码确认事实逻辑”，并说明无法访问远程源码时的提示）
- `docs/session-digest.md`：本次会话成果归档（docs/skills/commands/scripts 清单与推荐使用路径）

## 本地缓存（dev/prod 隔离）

本仓库提供 `cache/<env>/` 作为本地缓存目录（例如缓存 MCP tools、Cursor prompts/skills/rules 的索引与打包）。缓存默认按需更新，用户也可主动强制刷新：

- 查看缓存状态：`python scripts/cache_status.py --env dev`
- 刷新缓存：`python scripts/cache_refresh.py --env dev`
- 强制刷新：`python scripts/cache_refresh.py --env dev --force`

## 上下文占用治理（FAC tools 很多时）

- 在 Chat 的 tools 列表中 **禁用不需要的 MCP tools**：被禁用的工具不会加载到上下文，也不会被 Agent 使用。
- 需要工具/提示词清单时优先使用缓存文件：`cache/<env>/mcp/tools_list.json`、`cache/<env>/mcp/prompts_list.json`
- 可直接用 `/context-budget` 查看建议与命令。
