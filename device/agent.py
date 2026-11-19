"""最小 agent 循环：OpenAI 兼容 chat + 工具调用。"""
from __future__ import annotations

import json
import os
from typing import Awaitable, Callable

import httpx

from .tools import TOOLS, execute

BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
API_KEY = os.environ.get("LLM_API_KEY", "").strip()
MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")
MAX_STEPS = int(os.environ.get("AGENT_MAX_STEPS", "6"))

SYSTEM_PROMPT = (
    "你是运行在口袋设备 Agent Box 上的桌面 agent。你可以读写工作区文件、抓取网页。"
    "优先调用工具完成任务，最后用简洁中文总结结果。不要编造工具没有返回的内容。"
)

EventFn = Callable[[dict], Awaitable[None]] | None


async def chat(messages: list[dict], on_event: EventFn = None) -> str:
    if not API_KEY:
        return (
            "演示模式：还没有配置 LLM_API_KEY。\n"
            "在 .env 里填入任意 OpenAI 兼容接口的 Key（LLM_BASE_URL / LLM_MODEL），重启即可对话。"
        )

    convo = [{"role": "system", "content": SYSTEM_PROMPT}, *messages]
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        for _ in range(MAX_STEPS):
            resp = await client.post(
                f"{BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json={"model": MODEL, "messages": convo, "tools": TOOLS, "tool_choice": "auto"},
            )
            if resp.status_code != 200:
                return f"模型调用失败（HTTP {resp.status_code}）：{resp.text[:300]}"
            msg = resp.json()["choices"][0]["message"]

            if msg.get("tool_calls"):
                convo.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": msg["tool_calls"]})
                for call in msg["tool_calls"]:
                    name = call["function"]["name"]
                    try:
                        args = json.loads(call["function"].get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    if on_event:
                        await on_event({"type": "tool", "name": name, "args": args})
                    result = execute(name, args)
                    if on_event:
                        await on_event({"type": "tool_result", "name": name, "text": result[:500]})
                    convo.append({"role": "tool", "tool_call_id": call["id"], "content": result[:4000]})
                continue

            return msg.get("content") or "（模型没有返回内容）"

    return "已达到最大步数，请把任务拆小一点再试。"
