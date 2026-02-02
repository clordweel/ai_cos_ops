# list-uoms（MCP 优先：计量单位列表）

请指导用户在指定环境用 **FAC MCP** 拉取 `UOM` 列表（仅 name），并保存到 `work/<env>/reference/uoms.json`。

```bash
python scripts/fac_mcp_list_uoms.py --env dev --limit 500
```
