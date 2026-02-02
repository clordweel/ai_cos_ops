---
name: migration-safety
description: 迁移安全（DEV -> PROD）流程与 checklist
disable-model-invocation: true
---

# 迁移安全（DEV -> PROD）

## 何时使用

- 功能完成后，需要把二开/配置变更从 dev 迁移到 prod
- 任何涉及 patch/fixtures/权限/流程变更的上线

## 必备产物（必须先准备）

- 迁移清单：涉及 DocType/配置/脚本/patch
- 回滚方案：怎么撤销、撤销是否丢数据
- 验证步骤：关键流程 + 权限/报表/边界场景

## 标准流程（高层）

1. dev 演练并记录完整步骤
2. 产出可迁移工件（尽量 code 化、可 review）
3. prod 只读预检（连通性、鉴权、环境识别）
4. 启用双确认护栏后执行最小化写入
5. 验证并记录结果

## 预检命令

```bash
python scripts/preflight.py --env dev --operation migration
set I_UNDERSTAND_PROD=YES
python scripts/preflight.py --env prod --operation migration --confirm-prod
```

## 参考

- @docs/migration.md
- @docs/environments.md
- @scripts/preflight.py

