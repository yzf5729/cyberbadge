# 安全与访问控制

## 1. 令牌（Token）

- 首次启动时自动生成，写在设备 `work/token.txt`（Unix 下人可读、组/其他不可读）；
- 也可用环境变量 `AGENT_TOKEN` 指定（优先级更高，适合部署时统一管理）；
- 手机首次访问：`http://<设备>:8000/?token=<令牌>`，服务端会种下 `cb_token` cookie（HttpOnly、SameSite=Lax、90 天），以后直接开首页即可；
- 换令牌：删除 `work/token.txt` 并重启服务（或改 `AGENT_TOKEN` 后重启）；旧令牌立即失效。

## 2. 哪些接口要鉴权

| 路径 | 是否公开 | 说明 |
|---|---|---|
| `/api/health` | 公开 | 只返回 `ok/model/time`，用于探活 |
| `/api/*` 其他 | 需要 | 无令牌返回 401 |
| `/` 与静态资源 | 需要 | 无令牌返回 401 提示页 |
| `/ws` | 需要 | 用 `?token=` 或 cookie；未通过直接关闭（4401） |

支持三种携带方式：`Authorization: Bearer <token>`、`?token=`、cookie `cb_token`。

## 3. 限流

按 `IP + 类别` 滑动窗口：

- 普通接口：120 次/分钟；
- 严格接口（`/api/chat`、`/api/task`、`/api/reload`）：20 次/分钟；
- 超限返回 429，并写审计日志。

## 4. 审计日志

`work/audit.log`（JSONL，超过 5MB 自动轮转为 `.log.1`）：

- 未授权/限流事件：`ip`、`path`、`event`；
- 工具调用：`event=tool`、`tool`、`ok`、`bytes`（不记录文件内容与参数值）；
- 对话：`event=chat`、`chars`、`session`（不记录正文）。

## 5. 网络暴露面

- 服务默认监听 `0.0.0.0:8000`，但 Windows 防火墙规则 `cyberbadge-8000` 只放行 Tailscale（100.64.0.0/10）与私有网段；
- 公网不可达；建议长期只通过 Tailscale 访问；
- 不要在没有令牌的情况下把端口映射到公网。

## 6. 已知边界

- 令牌以明文存在 `work/token.txt` 与浏览器 localStorage，**能读设备文件的人即可拿到令牌**——这不是多用户系统；
- 没有 HTTPS（内网/Tailscale 场景可接受；公网必须加 TLS 反代）；
- 没有细粒度权限（L0–L3 仍是路线图）；当前所有工具对持有令牌者可用；
- 审计日志本身未做完整性保护（可被设备管理员删改）。
