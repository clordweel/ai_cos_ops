# 迁移规范（从 DEV 到 PROD）

> 适用场景：功能完成后，将二开/配置变更从开发环境迁移到生产环境。由于 dev/prod 数据差异很大，本流程以“极谨慎”为默认。

## 迁移前提（必须满足）

- 已在 dev 完成演练，步骤可复现（含请求/结果/截图或日志摘要）。
- 变更可以被 **代码 review**（例如 patch/脚本/fixtures/配置变更记录）。
- 已明确：影响面、回滚方案、验证步骤。

## 强制护栏

任何与迁移相关的动作，先跑：

```bash
python scripts/preflight.py --env dev --operation migration
```

生产迁移必须启用双确认护栏：

```bash
set I_UNDERSTAND_PROD=YES
python scripts/preflight.py --env prod --operation migration --confirm-prod
```

## Checklist（建议直接复制到 PR / 工单）

- [ ] **目标环境确认**：dev/prod 的 `site_url`、`mcp_base_url` 已在 preflight 输出中确认
- [ ] **变更清单**：涉及哪些 DocType / 配置项 / 脚本 / patch
- [ ] **影响面评估**：哪些业务流程、哪些角色权限、哪些报表会受影响
- [ ] **回滚方案**：如何撤销；撤销是否会丢数据；回滚时间窗
- [ ] **验证步骤**：至少包含 1 条关键业务流程 + 关键报表/关键权限校验
- [ ] **只读预检**：先在 prod 运行只读连通性与身份校验（MCP/REST）
- [ ] **最小化写入**：生产操作必须最小范围、分步骤、可中断

## 建议的执行顺序（高层）

1. **在 dev 生成迁移工件**（尽量：patch/fixtures/脚本，而非“人工点 UI 记不住”）。
2. 进行 code review，确认可回滚。
3. 在 prod 做只读预检（连通性/鉴权/环境识别）。
4. 启用双确认护栏后，执行最小化写入步骤。
5. 按验证步骤验收，并记录变更与结果。

