---
name: mcp-first
description: MCP 优先（Frappe_Assistant_Core），REST 兜底策略
disable-model-invocation: true
---

# MCP-first（Frappe_Assistant_Core）

## 何时使用

- 需要对 Frappe/ERPNext/HRMS 做查询/诊断/受控操作
- 本地 bench CLI 不可用（默认场景）

## 执行范式

1. 环境预检（建议先只读）：

```bash
python scripts/preflight.py --env dev --operation read
python scripts/mcp_ping.py --env dev
```

1. 能用 MCP 就用 MCP：查询、诊断、产出迁移工件、受控写入。
1. MCP 不支持/不可用时再降级到 REST（先只读验证），并说明原因（能力缺失/服务不可达/权限不足）。

## 失败降级（REST 兜底）

- 先跑：`python scripts/rest_smoke.py --env dev`
- 写入前必须跑：`python scripts/preflight.py --operation write`
- 必须：最小范围 + 可回滚 + 可验证

## 参考

- @docs/mcp-and-rest.md
- @.cursor/skills/rest-auth/SKILL.md
- @scripts/mcp_ping.py
- @scripts/rest_smoke.py
