---
name: env-safety
description: 环境识别与生产护栏（DEV / PROD）
disable-model-invocation: true
---

# 环境识别与生产护栏（DEV / PROD）

## 何时使用

- 你准备执行任何可能影响数据/配置/权限的操作前
- 你不确定自己连到的是 dev 还是 prod
- 你要执行迁移（DEV -> PROD）或生产变更前

## 指令（务必遵守）

1. 明确声明环境：`ENV=dev` 或 `ENV=prod`
2. 运行预检脚本并粘贴摘要：

```bash
python scripts/preflight.py --env <dev|prod> --operation <read|write|migration>
```

3. 若 `ENV=prod` 且为写入/迁移：
   - 必须用户明确授权
   - 必须启用双确认护栏：

```bash
set I_UNDERSTAND_PROD=YES
python scripts/preflight.py --env prod --operation write --confirm-prod
```

## 参考

- @AGENTS.md
- @docs/environments.md
- @scripts/preflight.py

