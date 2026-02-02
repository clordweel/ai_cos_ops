# 源码参考地址（用于“事实确认”）

> 目的：当需要“向源码确认事实逻辑”时，先从这里找到正确的仓库与版本来源。

## 重要限制（必须明确）

- **AI Agent 无法仅凭一个 GitHub URL 就自动读取/检索源码**（除非该仓库内容已在当前工作区、或你把相关文件内容贴到对话/打开为上下文）。
- 当无法访问源码时，Agent 必须明确提示：
  - “当前会话无法从远程仓库 URL 读取源码，无法确认事实；请把仓库 clone 到工作区/提供文件路径/粘贴关键代码片段”。

## 核心仓库

- **cos（二开业务）**：`https://github.com/clordweel/cos`
- **Frappe_Assistant_Core（服务端 MCP）**：`https://github.com/buildswithpaul/Frappe_Assistant_Core`
- **raven（用户端 AI 改造计划）**：`https://github.com/The-Commit-Company/raven`

## 上游基建（v16）

- **Frappe**：`https://github.com/frappe/frappe`
- **ERPNext**：`https://github.com/frappe/erpnext`
- **HRMS**：`https://github.com/frappe/hrms`

## 环境地址（用于“行为验证”，不是源码）

- **DEV**：`https://cos-dev.junhai.work`
- **PROD**：`https://cos.junhai.work`

## 推荐的“源码确认”流程

1. 先说明你要确认的事实是什么（函数/接口/DocType/行为）。
2. 如果仓库不在当前工作区：
   - 让对方把仓库 clone 到本地并在 Cursor 打开；或
   - 让对方把相关文件（或关键片段）贴到对话里；或
   - 让对方提供文件路径 + 关键行范围。
3. Agent 只在看过源码或可复现实验后下结论；否则必须写“未验证/需要源码确认”。
