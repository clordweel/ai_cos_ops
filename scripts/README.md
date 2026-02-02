# scripts

本目录提供“**环境识别 + 护栏**”脚本，保证组员在执行任何高风险动作前，能明确知道自己在操作 **DEV** 还是 **PROD**。

## 预检（强烈建议任何动作前先跑）

```bash
python scripts/preflight.py --env dev --operation read
python scripts/preflight.py --env dev --operation write
```

如果在 Windows 上遇到 `python` 不可用（退出码 9009 / 指向 WindowsApps），请改用：

```bash
py scripts\preflight.py --env dev --operation read
py scripts\preflight.py --env dev --operation write
```

也可以先运行自检脚本：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\python_check.ps1
```

生产写入/迁移会被默认阻止，除非你明确启用双确认护栏：

```bash
set I_UNDERSTAND_PROD=YES
python scripts/preflight.py --env prod --operation write --confirm-prod
```

## MCP / REST 自检

```bash
python scripts/mcp_ping.py --env dev
python scripts/rest_smoke.py --env dev
```

如果已配置 FAC MCP 的 OAuth Bearer token（`config/secrets.local.yaml -> mcp_token`），推荐优先用 MCP 查询当前用户基础数据（只读）：

```bash
python scripts/fac_mcp_user_info.py --env dev
```

使用 FAC MCP 获取 Company 列表（只读）：

```bash
python scripts/fac_mcp_list_companies.py --env dev
```

## 初始化 reference 资料（新组员上手推荐）

一键从目标环境拉取基础 reference 资料，并落盘到 `work/<env>/reference/`：

- `companies.json`
- `item_groups.json`（包含：`item_group_name,parent_item_group,custom_description,custom_standard_tax_rate,custom_code,is_group,image`）
- `uoms.json`

Windows（推荐）：

```bash
py scripts\init_reference_data.py --env dev
```

reference 拉取清单由配置文件管理（可提交）：

- `config/reference_profiles.json`

如需增删 reference（或改 limit/fields/输出文件名），修改该文件的 `profiles.default.items` 即可。

macOS/Linux：

```bash
python scripts/init_reference_data.py --env dev
```

## 模板驱动批量创建（低上下文）

当需要“从物料参数模板创建物料”且要批量处理时，推荐把计算与写入放到服务器端一次完成（`run_python_code`），避免本地反复 MCP 往返和上下文膨胀。

- 配置（可提交）：`config/template_item_profiles.json`
- 批量脚本：`scripts/create_items_from_template.py`
- Cursor 命令：`/create-items-from-template`

建议流程：

1. 先 dry-run（只校验/计算，不写入）
2. 再执行批量创建/更新（默认 upsert，并使用 `custom_unique_item_name` 做幂等键）

## 参数 hash 去重（COS Stock）

为支持“从参数生成唯一 hash、快速判重”，提供：

- 初始化自定义字段：`python scripts/fac_mcp_setup_item_param_hash_field.py --env dev`  
  - 在 `Item` 上创建 `custom_param_hash`（module=`COS Stock`，并开启索引）
- 按 hash 查重：`python scripts/fac_mcp_find_items_by_param_hash.py --env dev --hash <md5>`

如果希望同时查询 token 对应用户的 **User 基础资料**（只读）：

```bash
python scripts/rest_smoke.py --env dev --user-info
```

Windows（推荐）：

```bash
py scripts\mcp_ping.py --env dev
py scripts\rest_smoke.py --env dev --user-info
```
