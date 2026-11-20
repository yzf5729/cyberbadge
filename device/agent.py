"""最小 agent 循环：OpenAI 兼容 chat + 工具调用。"""
from __future__ import annotations

import json
import os
from typing import Awaitable, Callable

import httpx
from dotenv import load_dotenv

from .tools import TOOLS, execute
from .store import list_skills
from .skills import prompt_section

BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
API_KEY = os.environ.get("LLM_API_KEY", "").strip()
MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")
MAX_STEPS = int(os.environ.get("AGENT_MAX_STEPS", "6"))

BASE_PROMPT = (
    "你是运行在口袋设备 CyberBadge 上的桌面 agent。你可以读写工作区文件、处理文档、OCR、转换格式、抓取网页。"
    "优先调用工具完成任务，最后用简洁中文总结结果。不要编造工具没有返回的内容。"
)

EventFn = Callable[[dict], Awaitable[None]] | None


def reload_config() -> dict:
    """重新读取 .env（覆盖内存中的配置），返回脱敏后的当前配置。"""
    global BASE_URL, API_KEY, MODEL, MAX_STEPS
    load_dotenv(override=True)
    BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.deepseek.com/v1").rstrip("/")
    API_KEY = os.environ.get("LLM_API_KEY", "").strip()
    MODEL = os.environ.get("LLM_MODEL", "deepseek-chat")
    MAX_STEPS = int(os.environ.get("AGENT_MAX_STEPS", "6"))
    return {
        "base_url": BASE_URL,
        "model": MODEL,
        "key_set": bool(API_KEY),
        "key_len": len(API_KEY),
        "max_steps": MAX_STEPS,
    }


def system_prompt() -> str:
    enabled = {r["name"]: bool(r["enabled"]) for r in list_skills()}
    section = prompt_section(enabled)
    return BASE_PROMPT + ("\n\n可用技能（按需遵循）：\n" + section if section else "")


EFFORT_MAP = {"off": None, "low": "low", "medium": "medium", "high": "high"}


async def chat(messages: list[dict], on_event: EventFn = None,
               effort: str | None = None, model: str | None = None) -> str:
    if not API_KEY:
        return (
            "演示模式：还没有配置 LLM_API_KEY。\n"
            "在 .env 里填入任意 OpenAI 兼容接口的 Key（LLM_BASE_URL / LLM_MODEL），重启即可对话。"
        )

    convo = [{"role": "system", "content": system_prompt()}, *messages]
    use_model = (model or MODEL).strip() or MODEL
    reasoning = EFFORT_MAP.get((effort or "").lower())
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        for _ in range(MAX_STEPS):
            body = {"model": use_model, "messages": convo, "tools": TOOLS, "tool_choice": "auto"}
            if reasoning:
                body["reasoning_effort"] = reasoning
            resp = await client.post(
                f"{BASE_URL}/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                json=body,
            )
            if resp.status_code == 400 and reasoning:
                body.pop("reasoning_effort", None)
                resp = await client.post(
                    f"{BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
                    json=body,
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
