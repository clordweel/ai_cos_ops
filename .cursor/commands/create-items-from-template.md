# /create-items-from-template（模板驱动批量创建物料）

## 目标

把“从物料参数模板创建物料”变成**通用 + 批量 + 低上下文**的流程：

- 本地只提交一份小 spec（参数集列表）
- 服务器端 `run_python_code` 一次完成：读模板 → 校验 → 渲染 Jinja → 创建/更新（含子表）
- 输出仅保留摘要；完整结果写入 `work/<env>/operations/batches/`

## 配置（可提交）

模板 profile 配置：`config/template_item_profiles.json`

当前已内置示例：

- `steel_plate_standard`：基于 `标准模板 - 钢板`

## 批量输入（spec）

`--spec` 或 `--items-json` 里 items 是一个数组，每个元素形如：

```json
{
  "params": {
    "材质": "Q235B",
    "厚度": 5,
    "宽度": 1500,
    "长度": 6000,
    "密度": 7.85
  }
}
```

说明：

- `params` 的 key 必须匹配模板的 `parameter_name`（例如 钢板模板里的：材质/厚度/宽度/长度/密度）
- 其它字段（如 `item_name/description/stock_uom/uoms`）会按模板绑定/公式自动生成

## 执行（推荐：先 dry-run）

### 1) dry-run（只计算/校验，不写入）

```bash
py scripts\create_items_from_template.py --env dev --profile steel_plate_standard --dry-run --items-json "[{\"params\":{\"材质\":\"Q235B\",\"厚度\":5,\"宽度\":1500,\"长度\":6000,\"密度\":7.85}}]"
```

### 2) 批量创建/更新（upsert）

```bash
py scripts\create_items_from_template.py --env dev --profile steel_plate_standard --items-json "[{\"params\":{\"材质\":\"Q235B\",\"厚度\":5,\"宽度\":1500,\"长度\":6000,\"密度\":7.85}}]"
```

默认 `mode=upsert`（由 profile 控制）。可用 `--mode create_only|skip_existing|upsert` 覆盖。

## 输出与留痕

结果会保存到：

`work/<env>/operations/batches/<timestamp>_create_items_from_template_<profile>.json`

如果你需要降低上下文占用，优先看该文件，而不是把大 JSON 贴到对话里。
