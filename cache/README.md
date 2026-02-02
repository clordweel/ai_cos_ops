# cache（按环境隔离的本地缓存）

本目录用于缓存“**只读、可再生**”的数据，以提升日常开发与 AI Agent 工作效率，并避免频繁请求 MCP/REST。

## 目录结构

- `cache/dev/`：开发环境缓存
- `cache/prod/`：生产环境缓存

> 约定：任何缓存文件都不应包含密钥/token。必要时仅写入脱敏信息或工具元数据。

## 缓存内容（计划）

- **MCP tools**：`tools/list` 的结果（工具名、描述、schema），便于本地快速检索可用能力
- **Cursor prompts/skills**：把 `.cursor/commands`、`.cursor/skills`、`.cursor/rules` 做成索引/打包，便于快速浏览与引用

## 更新策略

- **默认按需更新**：当缓存缺失或过期（TTL）或源文件发生变化时才刷新
- **强制更新**：当你主动指令刷新时（例如运行 refresh 脚本的 `--force`）
