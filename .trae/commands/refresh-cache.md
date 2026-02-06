# refresh-cache（刷新缓存）

请指导用户刷新本仓库的本地缓存（按 dev/prod 隔离），并强调：缓存文件不应包含密钥。

## 推荐（按需刷新）

```bash
python scripts/cache_refresh.py --env dev
```

## 强制刷新（用户主动指令）

```bash
python scripts/cache_refresh.py --env dev --force
```

## 只刷新 MCP tools（例如工具列表变更时）

```bash
python scripts/cache_refresh.py --env dev --what mcp_tools --force
```

## 只刷新 Cursor prompts/skills/rules 索引与 bundle

```bash
python scripts/cache_refresh.py --env dev --what cursor --force
```
