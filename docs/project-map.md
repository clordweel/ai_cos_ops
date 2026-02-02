# 项目地图（Frappe/ERPNext/HRMS v16 + cos 二开 + MCP + Raven）

## 基建与二开范围

- **Frappe v16**：框架底座（DocType、权限、REST API、后台任务等）
- **ERPNext v16 / HRMS v16**：业务应用（财务/进销存/人资等）
- **cos（二开）**：在以上基建之上实现的定制化需求  
  - 仓库：`https://github.com/clordweel/cos`

## AI 相关组件

- **Frappe_Assistant_Core（服务端 MCP）**：为 Frappe 系统提供 MCP 工具层，供 AI Agent 调用  
  - 仓库：`https://github.com/buildswithpaul/Frappe_Assistant_Core`
  - 原则：在本项目中 **优先 MCP** 完成查询/诊断/受控操作
- **raven（用户端 AI 改造）**：计划用于 AI 改造的用户端/前端项目  
  - 仓库：`https://github.com/The-Commit-Company/raven`

## 运维与部署

- 框架服务使用 **bench** 工具部署/运维。
- **重要限制**：除非远程连接入服务器，否则本地环境通常 **无法使用 bench CLI**。因此团队协作中默认路径为：
  - **首选：MCP**（`Frappe_Assistant_Core`）
  - **其次：REST API**（Frappe `/api/method/...`）

## 开发环境与生产环境（强区分）

- **dev** 与 **prod** 各自运行一套系统，且数据差异很大。
- 任何写操作/迁移必须遵循：
  - `AGENTS.md`（全局约束）
  - `docs/environments.md`（环境护栏）
  - `docs/migration.md`（迁移流程）
  - `scripts/preflight.py`（强制预检）
