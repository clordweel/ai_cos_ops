---
description: "上下文预算：避免 MCP tools/大 prompt 导致上下文膨胀"
alwaysApply: true
---

# 上下文预算（Context Budget）

## 原则

- 不要在每个会话里把 FAC MCP 的 tools/prompts “全集”塞进上下文。
- 需要确认工具能力时，优先读取本地缓存（`cache/<env>/mcp/tools_list.json`、`cache/<env>/mcp/prompts_list.json`）。

## 具体要求

- 除非用户明确要求，否则不要执行“列出全部 tools / 打印全部 schema / 展示全部 prompts 内容”。
- 当工具很多且影响上下文时，必须提示用户在 Chat 的 tools 列表里禁用不需要的 MCP tools。
