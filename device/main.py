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

from .agent import chat  # noqa: E402

WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web"
app = FastAPI(title="CyberBadge", version="0.1.0")
TASKS: dict[str, dict] = {}


@app.get("/api/health")
async def health():
    return {"ok": True, "model": os.environ.get("LLM_MODEL", "demo"), "time": int(time.time())}


@app.post("/api/chat")
async def api_chat(payload: dict):
    messages = payload.get("messages", [])
    text = await chat(messages)
    return {"text": text}


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
            answer = await chat(history, on_event=send)
            history.append({"role": "assistant", "content": answer})
            await send({"type": "assistant", "text": answer})
    except WebSocketDisconnect:
        return


app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
