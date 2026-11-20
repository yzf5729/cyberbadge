"""ACP 适配器：通过 WebSocket bridge 与远程 agent（Hermes/DSH）对话。

协议：ACP (Agent Client Protocol) JSON-RPC over stdio；
bridge 服务把 stdio 桥成 WebSocket（每连接一个 agent 进程）。
"""
from __future__ import annotations

import asyncio
import json
import pathlib
import itertools

import websockets

INIT_TIMEOUT = 120
PROMPT_TIMEOUT = 300


class AcpError(RuntimeError):
    pass


class AcpSession:
    def __init__(self, url: str, token: str = "", cwd: str = "/root/.hermes"):
        self.url = url + (("?token=" + token) if token else "")
        self.cwd = cwd
        self._ws = None
        self._ids = itertools.count(1)

    async def __aenter__(self):
        self._ws = await websockets.connect(self.url, max_size=None, open_timeout=20,
                                            ping_interval=None)
        await self._request("initialize", {
            "protocolVersion": 1,
            "clientCapabilities": {"fs": {"readTextFile": True, "writeTextFile": True},
                                    "terminal": True},
            "clientInfo": {"name": "cyberbadge", "version": "0.3"},
        }, timeout=INIT_TIMEOUT)
        return self

    async def __aexit__(self, *exc):
        if self._ws is not None:
            await self._ws.close()

    async def _request(self, method: str, params: dict, timeout: float = PROMPT_TIMEOUT,
                       on_event=None) -> dict:
        rid = next(self._ids)
        await self._ws.send(json.dumps({"jsonrpc": "2.0", "id": rid, "method": method,
                                        "params": params}))
        while True:
            raw = await asyncio.wait_for(self._ws.recv(), timeout)
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            if msg.get("method") == "session/update":
                if on_event:
                    await on_event(msg.get("params") or {})
                continue
            if msg.get("id") != rid:
                continue
            if "error" in msg:
                raise AcpError(str(msg["error"])[:400])
            return msg.get("result") or {}

    async def new_session(self) -> str:
        res = await self._request("session/new", {"cwd": self.cwd, "mcpServers": []})
        sid = res.get("sessionId")
        if not sid:
            raise AcpError("session/new 未返回 sessionId")
        return sid

    async def resume(self, session_id: str) -> str:
        res = await self._request("session/resume", {"sessionId": session_id,
                                                     "cwd": self.cwd, "mcpServers": []})
        return res.get("sessionId") or session_id

    async def prompt(self, session_id: str, text: str, on_event=None) -> str:
        chunks: list[str] = []

        async def handler(params: dict):
            upd = params.get("update") or {}
            kind = upd.get("sessionUpdate")
            if kind == "agent_message_chunk":
                piece = (upd.get("content") or {}).get("text") or ""
                if piece:
                    chunks.append(piece)
            if on_event:
                await on_event({"acp": kind, "update": upd})

        res = await self._request("session/prompt", {
            "sessionId": session_id,
            "prompt": [{"type": "text", "text": text}],
        }, on_event=handler)
        return "".join(chunks).strip() or f"（{res.get('stopReason', 'end')}）"


def load_session_map(path: pathlib.Path) -> dict:
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_session_map(path: pathlib.Path, mapping: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, ensure_ascii=False, indent=2))


async def acp_chat(agent, hub_sid: str, text: str, state_path: pathlib.Path, on_event=None) -> str:
    """对远程 ACP agent 发一轮对话；hub_sid 用于映射远程会话，保持记忆。"""
    mapping = load_session_map(state_path)
    async with AcpSession(agent.acp_url, agent.acp_token, agent.cwd) as sess:
        remote_sid = mapping.get(hub_sid) or mapping.get(agent.id)
        if remote_sid:
            try:
                await sess.resume(remote_sid)
            except AcpError:
                remote_sid = None
        if not remote_sid:
            remote_sid = await sess.new_session()
        answer = await sess.prompt(remote_sid, text, on_event=on_event)
        mapping[hub_sid] = remote_sid
        mapping[agent.id] = remote_sid
        save_session_map(state_path, mapping)
        return answer


async def acp_ping(url: str, token: str = "", timeout: float = 8) -> bool:
    """轻量探测：能连上并完成 initialize 即认为在线。"""
    try:
        async with AcpSession(url, token) as _s:
            pass
        return True
    except Exception:
        return False
