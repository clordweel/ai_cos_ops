# AI Agent 全局约束（Cos / Frappe v16 系）

本文件对本仓库内的 AI Agent（Cursor Chat / Agent / Cmd-K）提供**全局行为约束**。如果你在子目录看到更具体的 `AGENTS.md`，以更具体者优先。

## 最高优先级：环境安全（dev / prod）

- **任何涉及写操作**（创建/更新/删除 DocType、数据修复脚本、Patch、权限变更、迁移）都必须：
  - **先明确声明目标环境**：`ENV=dev` 或 `ENV=prod`（不要含糊其辞）。
  - 先运行 `python scripts/preflight.py --env <dev|prod> --operation write`，并把输出贴回（至少包含 ENV / SITE_URL / MCP_URL）。
- **默认禁止对生产做写操作**：
  - 只有在用户明确要求“对 prod 写入”时才允许继续。
  - 即便允许，也必须使用脚本的双确认护栏（见 `scripts/preflight.py` 的 `--confirm-prod` 和 `I_UNDERSTAND_PROD=YES`）。

## 接入原则：MCP 优先，REST 兜底

- **优先**通过 `Frappe_Assistant_Core` 的 MCP 执行服务端操作/查询。
- 如果 MCP 不支持某能力，才允许使用 **Frappe REST API** 兜底，并且必须：
  - 使用 `Authorization: token <api_key>:<api_secret>`（从本地 `config/secrets.local.yaml` 读取）
  - 优先调用只读接口进行验证（例如 `frappe.ping`、`get_logged_user`）
- **禁止建议本地 bench**：除非明确是“已远程连接到服务器并可用”的场景，否则不要给出 bench 命令作为主要路径。

## 迁移与数据差异（极谨慎）

- dev/prod 数据差异很大；功能完成后迁移必须按照 `docs/migration.md` 的 checklist 执行。
- 任何“从 dev 带数据到 prod”的建议都必须附带：
  - 影响面（哪些 DocType/哪些表）
  - 回滚方案（如何撤销）
  - 验证步骤（如何确认成功与无副作用）

## 输出规范（便于团队协作）

- 在给出执行步骤前，先用 3-6 行列出：
  - 目标环境（dev/prod）
  - 目标站点 URL（`site_url`）
  - 首选通道（MCP / REST）
  - 风险级别（读/写/迁移）

## 源码事实确认（避免“臆测”）

- 当结论依赖“源码事实”（函数/接口/默认值/边界逻辑）时：\n
  - 必须基于当前工作区可读取的源码、或用户提供的代码片段、或可复现实验。\n
- 如果当前会话无法从远程仓库 URL 直接读取/检索源码：\n
  - 必须明确提示无法验证，并指导用户把仓库 clone 到工作区/提供文件路径/粘贴关键片段。\n
- 源码参考地址清单：`docs/source-references.md`

