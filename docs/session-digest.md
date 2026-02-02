# 会话成果归档（ai_cos_ops）

本文档用于把本次会话落地的“项目 AI 协作环境”做一次结构化归纳，便于新组员快速理解并复用。

## 0. 项目背景（高层）

- **基建**：Frappe v16 + ERPNext v16 + HRMS v16
- **二开业务**：`cos`（`https://github.com/clordweel/cos`）
- **服务端 MCP**：Frappe Assistant Core（FAC，`https://github.com/buildswithpaul/Frappe_Assistant_Core`）
- **用户端 AI 改造计划**：`raven`（`https://github.com/The-Commit-Company/raven`）

核心约束：**优先 MCP，其次 REST；bench CLI 默认不可用（除非远程连接到服务器）。**

## 1. 环境与鉴权（dev / prod）

### 1.1 环境地址

- DEV：`https://cos-dev.junhai.work`
- PROD：`https://cos.junhai.work`

环境文件：

- `config/environments/dev.yaml`
- `config/environments/prod.yaml`

### 1.2 鉴权方式（当前落地）

- **REST（Frappe）**：`Authorization: token <api_key>:<api_secret>`
  - 用于 `scripts/rest_smoke.py` 等 REST 兜底路径
- **FAC MCP（本环境兼容）**：实测可用 `Authorization: token <api_key>:<api_secret>` 访问 FAC MCP Endpoint（JSON-RPC）
  - FAC 官方文档通常描述 OAuth Bearer；但你们当前环境已可用 token 方式走 MCP

密钥文件 `config/secrets.local.yaml` 属于本地文件，**绝不提交**（已被 `.gitignore` 忽略）。

密钥模板文件（可提交）：`config/secrets.example.yaml`

## 2. 安全护栏（强制）

全局约束入口：

- `AGENTS.md`

关键护栏：

- **任何写操作**先跑：`python scripts/preflight.py --env <dev|prod> --operation write`
- **生产写入默认阻止**：需要 `I_UNDERSTAND_PROD=YES` + `--confirm-prod`
- **源码事实确认**：无法直接从远程仓库 URL 读源码时必须明确提示（见 `.cursor/rules/40-source-verification.mdc`）

## 3. Cursor 侧复用资产（rules / skills / commands）

### 3.1 Rules（强制约束）

目录：`.cursor/rules/`

- `00-safety.mdc`：dev/prod 安全护栏（最高优先级）
- `10-mcp-first.mdc`：MCP 优先，REST 兜底
- `20-rest-api.mdc`：REST 兜底规范
- `30-migration.mdc`：迁移规范（dev -> prod）
- `40-source-verification.mdc`：源码事实确认与“无法访问远程源码”的强提示
- `60-context-budget.mdc`：上下文预算（避免 tools/prompts 全集导致上下文膨胀）

### 3.2 Skills（可复用技能包）

目录：`.cursor/skills/`（建议都保持 `disable-model-invocation: true`，需要时手动 `/skill-name` 调用）

- `env-safety`：环境识别与生产护栏
- `mcp-first`：MCP-first 策略与降级
- `rest-auth`：REST 鉴权与只读自检
- `migration-safety`：迁移安全流程
- `source-lookup`：源码事实确认流程
- `context-budget`：控制上下文占用（工具开关 + 缓存优先）

### 3.3 Slash Commands（组员一键入口）

目录：`.cursor/commands/`

需求/迁移类：

- `/feature-implementation`
- `/bugfix`
- `/migration-dev-to-prod`
- `/ops-data-operation`

环境/缓存/治理：

- `/onboard-new-developer`
- `/source-references`
- `/cache-status`
- `/refresh-cache`
- `/context-budget`

数据拉取/测试：

- `/list-companies`
- `/list-item-groups`
- `/list-uoms`
- `/create-test-ac-contactor`
- `/create-items-from-template`

## 4. Scripts（确定性执行 + 可复现）

目录：`scripts/`

### 4.1 安全与连通性

- `preflight.py`：环境预检与 prod 双确认护栏
- `python_check.ps1`：Windows Python 环境自检
- `mcp_ping.py`：MCP initialize 探测（JSON-RPC）
- `rest_smoke.py`：REST 连通性 + `get_logged_user` +（可选）User 基础字段

### 4.2 FAC MCP（只读与写入示例）

- `fac_mcp_user_info.py`：用 FAC MCP 拉取当前用户基础数据（兼容 token/bearer）
- `fac_mcp_list_companies.py`：Company 列表
- `fac_mcp_list_item_groups.py`：Item Group 指定字段拉取（默认写入 `work/<env>/reference/item_groups.json`）
- `fac_mcp_list_uoms.py`：UOM 列表（默认写入 `work/<env>/reference/uoms.json`）
- `fac_mcp_create_test_item_ac_contactor.py`：创建测试物料（交流接触器；带存在性检查）
- `create_items_from_template.py`：模板驱动批量创建/更新 Item（低上下文：run_python_code 一次完成）

### 4.3 缓存（dev/prod 隔离）

- `cache_status.py`：查看缓存状态
- `cache_refresh.py`：刷新缓存（Cursor bundle、MCP tools、MCP prompts）

缓存目录（不提交）：`cache/<env>/`

## 5. work 目录（组员调试数据，默认不提交）

目录：`work/`（已在 `.gitignore` 忽略）

推荐结构（按 env + 用途拆分）：

```text
work/
  dev/
    reference/
    operations/
      items/
  prod/
    reference/
    operations/
```

本次会话示例产物：

- `work/dev/reference/item_groups.json`：物料组引用数据（只读拉取）
- `work/dev/reference/uoms.json`：UOM 引用数据（只读拉取）
- `work/dev/operations/items/created_item_TEST-AC-CONTACTOR.json`：创建测试物料的操作记录

## 6. 常用流程（推荐路径）

### 6.1 只读查数据（首选 MCP）

1. `python scripts/preflight.py --env dev --operation read`
2. `python scripts/mcp_ping.py --env dev`
3. 使用 FAC MCP 脚本（例如 `fac_mcp_list_companies.py` / `fac_mcp_list_item_groups.py`）

### 6.1.1 大单据/大数据 DocType：按需拉取（推荐）

当某些 DocType 数据量巨大时，不建议一次性全量拉取。推荐改为“按用量存取”：只把当前需要的那一条（或极少数几条）保存为 reference。

- Cursor：`/fetch-reference-doc`
- CLI：`python scripts/fac_mcp_fetch_reference_doc.py --env dev --doctype "<DocType>" --name "<name>"`

示例（只保存 `Item Parameter Template` 的“电机模板”）：

- Windows：`py scripts\fac_mcp_fetch_reference_doc.py --env dev --doctype "Item Parameter Template" --name "电机模板"`
- macOS/Linux：`python scripts/fac_mcp_fetch_reference_doc.py --env dev --doctype "Item Parameter Template" --name "电机模板"`

### 6.2 写操作（必须护栏）

1. `python scripts/preflight.py --env dev --operation write`
2. 用 FAC MCP `create_document/update_document`（通过脚本或在 Cursor Agent 中执行）
3. 将结果写入 `work/<env>/operations/` 留痕

补充：某些 **子表/明细字段**（例如 `Item.uoms`）在部分 FAC 环境中可能无法通过 `update_document` 稳定更新；此时可改用 `run_python_code` 做受控更新（仍应限制在 DEV，并保留操作留痕）。

### 6.3 控制上下文占用（FAC tools 多时）

- 在 Chat 的 tools 列表里禁用不需要的 MCP tools（禁用后不会加载到上下文）。
- 优先阅读缓存：`cache/<env>/mcp/tools_list.json`、`cache/<env>/mcp/prompts_list.json`
- 需要时运行：`python scripts/cache_refresh.py --env dev --force`
