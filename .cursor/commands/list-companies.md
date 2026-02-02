# list-companies（MCP 优先：公司列表）

请指导用户在指定环境用 **FAC MCP** 获取 Company 列表，并把结果保存到 `work/<env>/reference/` 便于后续调试引用。

```bash
python scripts/fac_mcp_list_companies.py --env dev --limit 200
```

说明：
- 输出文件（默认）：`work/dev/reference/companies.json`（如脚本未支持该路径，可提示用户用 `--out` 指定）
- 如 MCP 鉴权失败：先确认 `config/secrets.local.yaml` 已配置可用于 MCP 的 token

