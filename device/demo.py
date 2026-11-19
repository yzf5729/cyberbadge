"""模拟远程 agent：给 UI 演示用，不接真实模型/网络。"""
from __future__ import annotations

import random

PERSONA = {
    "dsh-demo": {
        "name": "DSH",
        "lines": [
            "（模拟）我是 DSH，跑在服务器上的编码助手。这条是在演示远程接入，不是真的模型回复。",
            "（模拟）如果真接入，我会先读你的文件、再动手改代码，并在这里显示工具调用。",
            "（模拟）远程 agent 的好处是：算力在服务器，胸牌只负责显示和转发。",
        ],
    },
    "hermes-demo": {
        "name": "Hermes",
        "lines": [
            "（模拟）我是 Hermes，住在容器里的助手。这条是模拟回复，别当真。",
            "（模拟）真接入后，我可以帮你记事情、查资料、发飞书。",
            "（模拟）心跳断了头像会变灰，恢复后自动变彩色。",
        ],
    },
}


def demo_reply(agent_id: str, text: str) -> str:
    p = PERSONA.get(agent_id)
    if not p:
        return "（模拟）这个 agent 还没有演示脚本。"
    pick = random.choice(p["lines"])
    echo = (text or "").strip()
    if echo:
        echo = echo[:60]
        return f"{pick}\n\n你刚才说：「{echo}」"
    return pick


def demo_tool_event(agent_id: str) -> dict:
    return {"type": "tool", "name": "context.read", "args": {"agent": agent_id}}
