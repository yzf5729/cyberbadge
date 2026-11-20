"""Agent 注册表：本地轻量 agent + 远程 agent（QQ 式在线状态）。

状态由心跳驱动：
- 本地 agent 永远在线；
- 远程 agent 每 15–30 秒 POST /api/agents/{id}/heartbeat，超过 OFFLINE_AFTER_S 无心跳置灰。
"""
from __future__ import annotations

import json
import os
import pathlib
import threading
import time
from dataclasses import dataclass, field

OFFLINE_AFTER_S = 90
WORKDIR = pathlib.Path(os.environ.get("AGENT_WORKDIR", "./work")).resolve()
ACP_AGENTS_FILE = WORKDIR / "acp_agents.json"


@dataclass
class Agent:
    id: str
    name: str
    kind: str = "remote"          # local | remote
    url: str = ""
    icon: str = "🤖"
    capabilities: list[str] = field(default_factory=list)
    last_seen: float = 0.0
    busy: bool = False
    demo: bool = False
    transport: str = "http"       # http | acp
    acp_url: str = ""
    acp_token: str = ""
    cwd: str = "/root/.hermes"

    def status(self) -> str:
        if self.kind == "local" or self.demo:
            return "online"
        if self.busy:
            return "busy"
        return "online" if time.time() - self.last_seen <= OFFLINE_AFTER_S else "offline"

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "demo": self.demo,
            "url": self.url,
            "icon": self.icon,
            "capabilities": self.capabilities,
            "status": self.status(),
            "transport": self.transport,
            "last_seen": int(self.last_seen) if self.last_seen else 0,
        }


class AgentRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._agents: dict[str, Agent] = {}
        self.register(Agent(
            id="builtin",
            name="CyberBadge",
            kind="local",
            icon="🤖",
            capabilities=[
                "files", "docx", "xlsx", "pptx", "pdf", "ocr",
                "image", "convert", "web", "browser",
            ],
        ))
        for item in self._load_remotes():
            self.register(item)
        for item in self._load_acp_agents():
            self.register(item)
        if os.environ.get("AGENT_DEMOS", "1") != "0":
            for item in self._default_demos():
                if item.id == "hermes-demo" and self.get("hermes"):
                    continue
                self.register(item)

    @staticmethod
    def _load_acp_agents() -> list[Agent]:
        try:
            raw = json.loads(ACP_AGENTS_FILE.read_text())
        except (OSError, ValueError):
            return []
        out: list[Agent] = []
        for item in raw if isinstance(raw, list) else []:
            try:
                out.append(Agent(
                    id=item["id"], name=item.get("name", item["id"]),
                    kind="remote", icon=item.get("icon", "🐋"),
                    url=item.get("url", ""), demo=False, transport="acp",
                    acp_url=item.get("acp_url", ""), acp_token=item.get("acp_token", ""),
                    cwd=item.get("cwd", "/root/.hermes"),
                    capabilities=item.get("capabilities", ["chat", "memory", "tools"]),
                    last_seen=time.time(),
                ))
            except (KeyError, TypeError):
                continue
        return out

    @staticmethod
    def _default_demos() -> list[Agent]:
        return [
            Agent(id="dsh-demo", name="DSH", kind="remote", icon="🧠", demo=True,
                  capabilities=["chat", "files", "office", "web"]),
            Agent(id="hermes-demo", name="Hermes", kind="remote", icon="🐋", demo=True,
                  capabilities=["chat", "memory", "image", "browser"]),
        ]

    @staticmethod
    def _load_remotes() -> list[Agent]:
        raw = os.environ.get("AGENT_REMOTES", "").strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        out = []
        for d in data if isinstance(data, list) else []:
            if isinstance(d, dict) and d.get("id") and d.get("name"):
                out.append(Agent(
                    id=str(d["id"]), name=str(d["name"]), kind="remote",
                    url=str(d.get("url", "")), icon=str(d.get("icon", "🤖")),
                    capabilities=list(d.get("capabilities", [])), last_seen=0.0,
                ))
        return out

    def register(self, agent: Agent) -> None:
        with self._lock:
            self._agents[agent.id] = agent

    def heartbeat(self, agent_id: str, busy: bool | None = None) -> Agent | None:
        with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return None
            agent.last_seen = time.time()
            if busy is not None:
                agent.busy = busy
            return agent

    def list(self) -> list[dict]:
        with self._lock:
            return [a.as_dict() for a in self._agents.values()]

    def get(self, agent_id: str) -> Agent | None:
        with self._lock:
            return self._agents.get(agent_id)


REGISTRY = AgentRegistry()
