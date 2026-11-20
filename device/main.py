"""CyberBadge 设备端：WebSocket 对话 + 后台任务 + PWA 静态页。"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib
import time
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from .agent import chat, reload_config  # noqa: E402
from .registry import REGISTRY  # noqa: E402
from . import store  # noqa: E402
from . import skills as skills_mod  # noqa: E402
from .demo import demo_reply, demo_tool_event  # noqa: E402
from .security import guard, needs_cookie, token, audit, extract_token  # noqa: E402

WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web"
app = FastAPI(title="CyberBadge", version="0.2.0")
TASKS: dict[str, dict] = {}
store.init()
token()  # 启动即生成/加载令牌，写 work/token.txt


@app.middleware("http")
async def auth_middleware(request, call_next):
    denied = await guard(request)
    if denied is not None:
        return denied
    response = await call_next(request)
    ck = needs_cookie(request)
    if ck:
        response.set_cookie("cb_token", ck, max_age=90 * 24 * 3600, httponly=True, samesite="lax")
    return response


@app.get("/api/sessions")
async def sessions_list():
    return {"sessions": store.list_sessions()}


@app.post("/api/sessions")
async def sessions_create(payload: dict | None = None):
    return store.create_session((payload or {}).get("title") or "新对话")


@app.delete("/api/sessions/{sid}")
async def sessions_delete(sid: str):
    return {"ok": store.delete_session(sid)}


@app.patch("/api/sessions/{sid}")
async def sessions_rename(sid: str, payload: dict):
    title = (payload.get("title") or "").strip()
    if not title:
        return JSONResponse({"error": "title 不能为空"}, status_code=400)
    return {"ok": store.rename_session(sid, title)}


@app.get("/api/sessions/{sid}/messages")
async def sessions_messages(sid: str):
    return {"messages": store.get_messages(sid)}


@app.get("/api/skills")
async def skills_list():
    known = {r["name"]: bool(r["enabled"]) for r in store.list_skills()}
    return {"skills": [{**s, "enabled": known.get(s["name"], True)} for s in skills_mod.scan()]}


@app.post("/api/skills/{name}/toggle")
async def skills_toggle(name: str, payload: dict):
    store.set_skill(name, bool(payload.get("enabled", True)))
    return {"ok": True, "name": name, "enabled": bool(payload.get("enabled", True))}


@app.post("/api/reload")
async def reload_env():
    """改完 .env 后调用：不用重启进程即可生效。"""
    return {"ok": True, **reload_config()}


@app.get("/api/agents")
async def list_agents():
    """顶部头像条：本地 + 远程 agent 及其在线状态。"""
    return {"agents": REGISTRY.list()}


@app.post("/api/agents/{agent_id}/heartbeat")
async def heartbeat(agent_id: str, payload: dict | None = None):
    busy = (payload or {}).get("busy")
    agent = REGISTRY.heartbeat(agent_id, busy)
    if not agent:
        return JSONResponse({"error": "unknown agent"}, status_code=404)
    return {"ok": True, "status": agent.status()}


@app.get("/api/health")
async def health():
    return {"ok": True, "model": os.environ.get("LLM_MODEL", "demo"), "time": int(time.time())}


@app.post("/api/chat")
async def api_chat(payload: dict):
    messages = payload.get("messages", [])
    agent_id = payload.get("agent") or "builtin"
    agent = REGISTRY.get(agent_id)
    if agent and agent.demo:
        last = messages[-1]["content"] if messages else ""
        return {"text": demo_reply(agent_id, last), "agent": agent_id, "demo": True}
    sid = payload.get("session_id")
    text = messages[-1]["content"] if messages else ""
    history = store.get_messages(sid) if sid else messages[:-1]
    if sid:
        store.add_message(sid, "user", text)
    audit({"event": "chat", "agent": "builtin", "chars": len(text), "session": sid})
    answer = await chat(history + [{"role": "user", "content": text}], effort=payload.get("effort"))
    if sid:
        store.add_message(sid, "assistant", answer)
    return {"text": answer, "agent": "builtin", "session_id": sid}


@app.post("/api/task")
async def create_task(payload: dict):
    prompt = (payload.get("prompt") or "").strip()
    if not prompt:
        return JSONResponse({"error": "prompt 不能为空"}, status_code=400)
    task_id = uuid.uuid4().hex[:8]
    TASKS[task_id] = {"id": task_id, "status": "running", "prompt": prompt, "result": "", "created": time.time()}

    async def runner():
        try:
            TASKS[task_id]["result"] = await chat([{"role": "user", "content": prompt}])
            TASKS[task_id]["status"] = "done"
        except Exception as exc:  # noqa: BLE001
            TASKS[task_id].update(status="error", result=str(exc))

    asyncio.create_task(runner())
    return {"id": task_id, "status": "running"}


@app.get("/api/task/{task_id}")
async def get_task(task_id: str):
    task = TASKS.get(task_id)
    if not task:
        return JSONResponse({"error": "not found"}, status_code=404)
    return task


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    given = ws.query_params.get("token", "") or ws.cookies.get("cb_token", "")
    if not given or given != token():
        await ws.accept()
        await ws.close(code=4401)
        return
    await ws.accept()
    history: list[dict] = []

    async def send(event: dict):
        await ws.send_text(json.dumps(event, ensure_ascii=False))

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            user_text = (data.get("text") or "").strip()
            if not user_text:
                continue
            history.append({"role": "user", "content": user_text})
            await send({"type": "user", "text": user_text})
            agent_id = data.get("agent") or "builtin"
            agent = REGISTRY.get(agent_id)
            sid = data.get("session_id")
            effort = data.get("effort")
            if agent and agent.demo:
                await send({"type": "tool", "name": "context.read", "args": {"agent": agent_id}})
                await asyncio.sleep(0.6)
                answer = demo_reply(agent_id, user_text)
                await send({"type": "tool_result", "name": "context.read", "text": "（模拟）已读取上下文"})
            else:
                if sid:
                    base = store.get_messages(sid)
                    store.add_message(sid, "user", user_text)
                    answer = await chat(base + [{"role": "user", "content": user_text}],
                                        on_event=send, effort=effort)
                    store.add_message(sid, "assistant", answer)
                else:
                    answer = await chat(history, on_event=send, effort=effort)
            history.append({"role": "assistant", "content": answer})
            await send({"type": "assistant", "text": answer})
    except WebSocketDisconnect:
        return


app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
