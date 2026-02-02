---
name: context-budget
description: 控制上下文占用（避免 MCP tools/prompts 膨胀）
disable-model-invocation: true
---

# 控制上下文占用（Context Budget）

## 何时使用

- 你发现对话变慢、上下文变大、Agent 在工具说明上“打转”
- FAC MCP 工具/Schema 很多，影响任务质量与成本

## 操作建议（按收益排序）

1. 在 Chat 的 tools 列表里，禁用不需要的 MCP tools。
   - 禁用的工具不会被加载到上下文，也不会被 Agent 使用。
2. 需要“工具清单/提示词清单”时，优先查看缓存文件：
   - `cache/<env>/mcp/tools_list.json`
   - `cache/<env>/mcp/prompts_list.json`
3. 避免让 Agent 在对话中反复输出完整 schema。

## 缓存命令

```bash
python scripts/cache_status.py --env dev
python scripts/cache_refresh.py --env dev --what mcp_tools --force
python scripts/cache_refresh.py --env dev --what mcp_prompts --force
```
