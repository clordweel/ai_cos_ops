---
description: "MCP 优先：通过 Frappe_Assistant_Core 执行服务端能力"
alwaysApply: true
---

# MCP 优先（FAC）

## MCP-first 策略

- **优先**使用 `Frappe_Assistant_Core` 的 MCP 工具完成：查询、生成迁移产物、执行受控写操作、诊断问题。
- 如果 MCP 不支持某能力，才允许使用 REST API 作为兜底路径（见 `docs/mcp-and-rest.md`）。

## 推荐脚本（只读）

- `python scripts/fac_mcp_user_info.py --env dev`：用 FAC MCP 拉取当前 token 用户基础数据

## MCP 使用要求

- 任何可能触发写入的 MCP 操作前，先跑 `scripts/preflight.py` 并在回复里贴出 preflight 摘要。
- 对生产环境做写入前必须：解释影响面、回滚方式、验证步骤；并要求用户明确授权。

## 失败降级（兜底）

当 MCP 不可用/能力缺失时：

1. 先用 REST 的只读接口做连通性与身份确认（`frappe.ping` / `get_logged_user`）。
2. 再在明确环境与护栏通过的前提下，执行最小范围的写入调用。
