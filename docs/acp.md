# ACP 远程 agent 接入

CyberBadge 用 [ACP](https://agentclientprotocol.com/)（Agent Client Protocol）连接远程 agent。
协议是 stdio 上的 JSON-RPC，因此需要一个 **bridge** 把 stdio 桥成 WebSocket，供胸牌/网页调用。

## 架构

```
胸牌/浏览器 ── ws ──▶ device/adapters/acp.py ── ws ──▶ acp_bridge.py ──docker exec──▶ hermes-acp
```

## 服务端 bridge（以 Hermes 为例）

`/root/.dsh/im/bridge/acp_bridge.py`：FastAPI + WebSocket `/acp`，每个连接 `docker exec -i hermes-shadow hermes-acp`。

启动：

```bash
# 或直接 systemd（推荐）
sudo cp scripts/cb-acp-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now cb-acp-bridge

# 手动方式
ACP_BRIDGE_TOKEN=$(cat token.txt) \
PYTHONPATH=/root/.dsh/im/bridge/.libs \
  nohup python3 -m uvicorn acp_bridge:app --host 100.117.57.3 --port 8100 --ws websockets
```

## 胸牌侧注册

`work/acp_agents.json`：

```json
[{
  "id": "hermes", "name": "Hermes", "icon": "🐋",
  "acp_url": "ws://100.117.57.3:8100/acp",
  "acp_token": "<bridge token>",
  "cwd": "/root/.hermes",
  "capabilities": ["chat", "memory", "tools", "browser"]
}]
```

注册后：`/api/agents` 会出现 `transport=acp` 的远程 agent，网页头像条彩色/灰色由心跳与可达性决定，对话自动走 ACP。

## 已验证（2026-11-21）

- `initialize` / `session/new` / `session/prompt` / `session/list` / `session/resume` 全部可用；
- 单轮首次约 10s，带记忆的追问约 30s（模型为 Hermes 自带 grok-4.7）；
- 会话映射存 `work/acp_sessions.json`，hub 会话 ID ↔ ACP sessionId 一一对应。

## 已知限制

- bridge 是单进程/单连接模型：一个连接一个 agent 进程；并发多会话需要连接池（后续）；
- 没有做 ACP 的 `session/request_permission` 交互（工具授权目前走 Hermes 自己的策略）；
- bridge 目前手动启动，未做 systemd 守护。
