# MCP 优先、REST 兜底（bench 不可用时的默认路径）

## 总原则

- **优先 MCP**：通过 `Frappe_Assistant_Core` 的 MCP 工具完成服务端动作（查询/诊断/受控写入）。
- **其次 REST**：当 MCP 不覆盖或不可用时，用 Frappe REST API 兜底。
- **默认不使用 bench**：除非明确在服务器上远程会话且 bench 可用。

## MCP（首选）

你需要在 `config/environments/*.yaml` 中配置：

- `mcp_base_url`：FAC MCP Endpoint（通常形如：`https://<site>/api/method/frappe_assistant_core.api.fac_endpoint.handle_mcp`）

你需要在本地 `config/secrets.local.yaml` 中配置（不提交）：

- `mcp_token`：**OAuth 2.0 Bearer access_token**（FAC MCP 需要；不是 Frappe 的 api_key:api_secret）

连通性自检：

```bash
python scripts/mcp_ping.py --env dev
```

若 MCP 没有 `/health`，可以改为：

```bash
python scripts/mcp_ping.py --env dev --path /
```

使用 FAC MCP 获取“当前 token 用户基础数据”（只读，推荐路径）：

```bash
python scripts/fac_mcp_user_info.py --env dev
```

## REST（兜底）

你需要在 `config/environments/*.yaml` 中配置：

- `rest_base_url`：通常与站点同源

你需要在本地 `config/secrets.local.yaml` 中配置（不提交）：

- `rest_api_key`
- `rest_api_secret`

连通性/鉴权自检：

```bash
python scripts/rest_smoke.py --env dev
```

### REST 鉴权格式（常见）

Header：

- `Authorization: token <api_key>:<api_secret>`

### 建议的调用顺序

1. `GET /api/method/frappe.ping`（连通性）
2. `GET /api/method/frappe.auth.get_logged_user`（鉴权验证）
3. 只在必要时执行写入，并遵循 `docs/migration.md` 的安全流程
