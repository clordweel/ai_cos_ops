# work（组员调试/开发工作目录）

本目录用于开发组员保存临时调试数据、导出结果、实验脚本输出等。

## 规则

- **默认不提交**：该目录已在仓库根 `.gitignore` 中忽略（避免污染版本库）。
- **按环境隔离**：建议使用 `work/dev/` 与 `work/prod/` 分开存放，避免把生产数据混入开发。
- **禁止存放密钥**：不要在这里保存任何 token、密码、私钥等敏感信息。

## 推荐目录结构（避免扁平堆文件）

在每个环境目录下，按“引用数据 / 操作记录”拆分：

```text
work/
  dev/
    reference/          # 引用数据（只读拉取，用于开发/对照）
      item_groups.json
      uoms.json
      companies.json
    operations/         # 操作记录（创建/更新/删除的返回、审计）
      items/
        created_item_<code>.json
  prod/
    reference/
    operations/
```

## 初始化 reference（推荐）

新组员上手时，建议先从目标环境拉取一份基础 reference 资料：

- Cursor：`/init-reference-data`
- CLI：`py scripts\init_reference_data.py --env dev`

## 建议内容

- MCP/REST 查询结果的 JSON（只读）
- 数据清洗/对账的中间产物
- 临时 SQL/脚本输出（脱敏后）
