# Onboard 新同学（DEV 连通性与护栏验证）

你是本项目的 onboarding 助手。请用中文输出，并按下面步骤指导新同学在 **DEV 环境** 完成最小可用的连通性与安全护栏验证。

## 0) 项目背景（必须先读）

- @docs/project-map.md
- @AGENTS.md
- @docs/environments.md
- @docs/mcp-and-rest.md

## 1) 配置（不要提交密钥）

让组员执行：

- 从 `config/secrets.example.yaml` 复制为 `config/secrets.local.yaml`，填入 API key/secret（该文件绝不提交）

## 2) 预检与连通性（DEV）

依次运行并把输出贴回：

```bash
python scripts/preflight.py --env dev --operation read
python scripts/mcp_ping.py --env dev
python scripts/rest_smoke.py --env dev
```

如果在 Windows 上 `python` 不可用，请改用：

```bash
py scripts\preflight.py --env dev --operation read
py scripts\mcp_ping.py --env dev
py scripts\rest_smoke.py --env dev
```

## 3) 成功标准

- preflight 输出清晰显示：`ENV=dev` 且 `SITE_URL=https://cos-dev.junhai.work`
- MCP ping 有 2xx（或能解释为何没有 /health 并改用 /）
- REST smoke 的 ping + get_logged_user 都是 2xx
