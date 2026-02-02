# context-budget（控制上下文占用）

请指导用户控制 Cursor 会话上下文占用，避免 FAC MCP 工具/元数据导致上下文膨胀。

## 关键操作（最有效）

- 在 Chat 的 **tools 列表**里，把不需要的 MCP tools **关掉**。
  - 被关闭的工具 **不会被加载到上下文**，也不会被 Agent 使用。

## 推荐策略

- 日常只保留最小工具集：`list_documents / get_document / create_document / update_document`（按需再开）
- 需要“工具全集/提示词全集”时，优先看本地缓存文件：
  - `cache/<env>/mcp/tools_list.json`
  - `cache/<env>/mcp/prompts_list.json`
- 避免在对话里反复让 Agent “列出全部 tools / 打印全部 schema”，这会显著占用上下文。

## 一键查看/刷新缓存

```bash
python scripts/cache_status.py --env dev
python scripts/cache_refresh.py --env dev --what mcp_tools --force
python scripts/cache_refresh.py --env dev --what mcp_prompts --force
```
