# /fetch-reference-doc（按需拉取单条 reference）

## 适用场景

有些 DocType 数据量很大，不适合一次性全量拉取到 `work/<env>/reference/`。多数时候应该**按用量存取**：只把当前需要的那一条（或极少数几条）单据保存为 reference。

本命令通过 FAC MCP（只读）实现：**先搜索 → 再仅保存命中的那一条**。

## 用法（Windows 推荐）

### 1) 直接按 name 精确拉取（最安全）

```bash
py scripts\fac_mcp_fetch_reference_doc.py --env dev --doctype "Item Parameter Template" --name "电机模板"
```

### 2) 按关键词查找后保存

```bash
py scripts\fac_mcp_fetch_reference_doc.py --env dev --doctype "Item Parameter Template" --query "电机模板"
```

若匹配到多个候选，为避免误存默认会中止；你可以：

- 改用 `--name` 精确指定；或
- 传入更精确过滤：`--filters-json`；或
- 明确允许 pick：加 `--allow-multi --pick N`

### 3) 高级过滤（原样传给 list_documents.filters）

```bash
py scripts\fac_mcp_fetch_reference_doc.py --env dev --doctype "Item Parameter Template" --filters-json "{\"name\":[\"like\",\"%电机%\"]}"
```

## 输出位置

默认保存到：

`work/<env>/reference/<doctype>/<name>.json`

例如：

`work/dev/reference/item_parameter_template/电机模板.json`

如需自定义输出路径，使用 `--out <path>`。
