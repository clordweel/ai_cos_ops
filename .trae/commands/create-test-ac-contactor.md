# create-test-ac-contactor（DEV：创建测试物料）

请指导用户在 **DEV** 环境使用 **FAC MCP** 创建测试物料“测试交流接触器”，物料组为“电气元件”。
**强制护栏**：创建前必须跑 `preflight`，并确认 ENV=dev。
```bash
python scripts/preflight.py --env dev --operation write
python scripts/fac_mcp_create_test_item_ac_contactor.py --env dev
```

说明：
- 脚本会先检查 `TEST-AC-CONTACTOR` 是否已存在，存在则不重复创建
- 创建结果会写入：`work/dev/operations/items/created_item_TEST-AC-CONTACTOR.json`
