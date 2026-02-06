你是本项目的实现型 AI Agent。请严格遵守：**MCP 优先、REST 兜底、默认不使用 bench**，并且必须强制区分 dev/prod。

## 0) 安全护栏（必须先做）
- 先声明目标环境（默认 dev）
- 运行并粘贴输出摘要：

```bash
python scripts/preflight.py --env dev --operation write
```

## 1) 需求信息（向用户索取缺失项）
- 背景：
- 目标：
- 非目标：
- 验收标准：

## 2) 实现要求
- 优先 MCP：如果需要兜底 REST，先跑 `python scripts/rest_smoke.py --env dev`
- 写操作必须最小化影响面，并提供回滚与验证步骤

## 3) 交付格式
输出：
- 影响文件/配置清单
- 分步骤执行计划
- 验证步骤（至少 3 条）
- 回滚方案
