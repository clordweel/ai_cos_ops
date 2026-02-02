# 环境说明与护栏（DEV / PROD）

## 为什么必须强区分

开发服务器与生产服务器分别运行一套系统，两者数据差异很大。**最危险的错误**是把写操作/修复脚本/迁移误打到生产，造成不可逆数据影响。

本仓库通过以下机制强制提醒与拦截：

- Cursor Project Rules：`.cursor/rules/00-safety.mdc`
- 全局约束：`AGENTS.md`
- 脚本护栏：`scripts/preflight.py`

## 配置文件位置

### 可提交（不含密钥）

- `config/environments/dev.yaml`
- `config/environments/prod.yaml`

建议把站点域名、MCP 服务地址、服务器主机名都写清楚，便于组员一眼识别环境。

### 绝不提交（含密钥）

- `config/secrets.local.yaml`
  - 从 `config/secrets.example.yaml` 复制生成
  - 本文件已被 `.gitignore` 忽略

## 执行任何动作前的“环境确认”流程

### 只读操作（安全）

```bash
python scripts/preflight.py --env dev --operation read
python scripts/mcp_ping.py --env dev
python scripts/rest_smoke.py --env dev
```

### 写入/迁移（高风险）

```bash
python scripts/preflight.py --env dev --operation write
```

对 **prod** 的写入/迁移默认会被阻止，除非你显式启用双确认护栏：

```bash
set I_UNDERSTAND_PROD=YES
python scripts/preflight.py --env prod --operation write --confirm-prod
```

## 推荐的“环境标识约定”

为了减少误操作，建议团队在 `config/environments/*.yaml` 里配置 `expected_host_contains`：

- dev：`expected_host_contains: "dev"`
- prod：`expected_host_contains: "prod"`

`scripts/preflight.py` 会校验 `site_url/rest_base_url` 是否包含该字符串；不匹配则直接阻止。
