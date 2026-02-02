# /init-reference-data（初始化 reference 资料）

## 目标

让新组员在上手时，一键从目标环境拉取基础 reference 资料，并落盘到：

- `work/<env>/reference/companies.json`
- `work/<env>/reference/item_groups.json`（包含字段：`item_group_name,parent_item_group,custom_description,custom_standard_tax_rate,custom_code,is_group,image`）
- `work/<env>/reference/uoms.json`

> 本命令只读查询（通过 FAC MCP），不会对 Frappe 写入数据。

## reference 清单如何配置（可提交）

待拉取内容由配置文件管理：

- 默认配置：`config/reference_profiles.json`
  - 默认 profile：`default`
  - 你可以在 `profiles.default.items` 中增删条目（脚本、参数、输出文件名）

## 前置条件（第一次使用必做）

- 已按模板创建本地密钥文件：`config/secrets.local.yaml`（从 `config/secrets.example.yaml` 复制）
- 已确认环境地址：`config/environments/dev.yaml` / `config/environments/prod.yaml`

## 执行（推荐：Windows 用 py）

把 `<env>` 替换为 `dev` 或 `prod`：

```bash
py scripts\init_reference_data.py --env <env>
```

如果你维护了多个 profile：

```bash
py scripts\init_reference_data.py --env <env> --list-profiles
py scripts\init_reference_data.py --env <env> --profile default
```

如果你是 macOS/Linux：

```bash
python scripts/init_reference_data.py --env <env>
```

## 输出与下一步

- 产物会写入 `work/<env>/reference/`，可用于开发对照、字段确认、UI 默认值选择（例如 UOM）。
- 如需刷新 MCP tools/prompts 缓存：先跑 `/refresh-cache` 或 `python scripts/cache_refresh.py --env <env>`。
