"""CyberBadge 设备端：WebSocket 对话 + 后台任务 + PWA 静态页。"""
from __future__ import annotations

import asyncio
import json
import os
import pathlib
import re
import secrets
import time
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from .agent import chat, reload_config  # noqa: E402
from .registry import REGISTRY  # noqa: E402
from . import store  # noqa: E402
from . import skills as skills_mod  # noqa: E402
from .demo import demo_reply, demo_tool_event  # noqa: E402
from .security import guard, needs_cookie, token, audit, extract_token  # noqa: E402
from .adapters.acp import acp_chat, acp_ping  # noqa: E402

WEB_DIR = pathlib.Path(__file__).resolve().parent.parent / "web"
WORKDIR = pathlib.Path(os.environ.get("AGENT_WORKDIR", "./work")).resolve()
UPLOAD_DIR = WORKDIR / "uploads"
SETTINGS_FILE = WORKDIR / "settings.json"
MAX_UPLOAD = 32 * 1024 * 1024
app = FastAPI(title="CyberBadge", version="0.3.0")
TASKS: dict[str, dict] = {}
store.init()
token()  # 启动即生成/加载令牌，写 work/token.txt


def load_settings() -> dict:
    default = {"model": "", "effort": ""}
    try:
        data = json.loads(SETTINGS_FILE.read_text())
        return {**default, **(data if isinstance(data, dict) else {})}
    except (OSError, ValueError):
        return default


def save_settings(patch: dict) -> dict:
    cur = load_settings()
    for k in ("model", "effort"):
        if k in patch and isinstance(patch[k], str):
            cur[k] = patch[k].strip()
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(cur, ensure_ascii=False, indent=2))
    return cur


SETTINGS = load_settings()
ACP_STATE = WORKDIR / "acp_sessions.json"


def safe_name(name: str) -> str:
    name = re.sub(r"[^0-9A-Za-z.\-_一-鿿]+", "_", name or "").strip("_")
    return name[-80:] or "file"


def attachment_block(atts: list[dict]) -> str:
    if not atts:
        return ""
    lines = [f"- {a.get('name', 'file')}: {a.get('path', '')}" for a in atts if a.get("path")]
    if not lines:
        return ""
    return "\n\n[附件，可用工具读取]\n" + "\n".join(lines)


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


@app.get("/api/settings")
async def get_settings():
    t = token()
    return {
        "model": SETTINGS.get("model") or os.environ.get("LLM_MODEL", "deepseek-chat"),
        "model_is_default": not SETTINGS.get("model"),
        "effort": SETTINGS.get("effort", ""),
        "key_set": bool(os.environ.get("LLM_API_KEY", "").strip()),
        "workdir": str(WORKDIR),
        "token_masked": (t[:4] + "…" + t[-4:]) if len(t) > 12 else "…",
    }


@app.post("/api/settings")
async def post_settings(payload: dict):
    global SETTINGS
    SETTINGS = save_settings(payload)
    return {"ok": True, **SETTINGS}


@app.post("/api/settings/token/rotate")
async def rotate_token():
    """生成新令牌并写入 work/token.txt；返回新令牌一次（前端需重新保存）。"""
    from .security import TOKEN_FILE
    new = secrets.token_urlsafe(24)
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(new)
    try:
        TOKEN_FILE.chmod(0o600)
    except OSError:
        pass
    audit({"event": "token_rotate"})
    return {"ok": True, "token": new}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), session_id: str = Form("")):
    sid = safe_name(session_id or "common") if session_id else "common"
    name = safe_name(file.filename or "file.bin")
    dest_dir = UPLOAD_DIR / sid
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{int(time.time() * 1000)}-{name}"
    size = 0
    with dest.open("wb") as fh:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD:
                fh.close()
                dest.unlink(missing_ok=True)
                return JSONResponse({"error": "文件超过 32MB 限制"}, status_code=413)
            fh.write(chunk)
    kind = "image" if (file.content_type or "").startswith("image/") else "file"
    audit({"event": "upload", "name": name, "bytes": size, "kind": kind})
    return {"ok": True, "name": name, "path": str(dest), "size": size, "kind": kind,
            "url": f"/api/uploads/{sid}/{dest.name}"}


@app.get("/api/uploads/{sid}/{name}")
async def get_upload(sid: str, name: str):
    sid, name = safe_name(sid), safe_name(name)
    if sid != name and "/" in name or ".." in name:
        return JSONResponse({"error": "bad path"}, status_code=400)
    path = UPLOAD_DIR / sid / name
    if not path.is_file():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(path)


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
    global SETTINGS
    cfg = reload_config()
    SETTINGS = load_settings()
    return {"ok": True, **cfg, **SETTINGS}


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
    if agent and agent.transport == "acp":
        sid = payload.get("session_id") or "default"
        atts = payload.get("attachments") or []
        text = (messages[-1]["content"] if messages else "") + attachment_block(atts)
        if payload.get("session_id"):
            store.add_message(sid, "user", text, {"attachments": atts})
        audit({"event": "chat", "agent": agent.id, "chars": len(text), "session": sid})
        answer = await acp_chat(agent, sid, text, ACP_STATE)
        if payload.get("session_id"):
            store.add_message(sid, "assistant", answer)
        return {"text": answer, "agent": agent.id, "session_id": sid}
    sid = payload.get("session_id")
    atts = payload.get("attachments") or []
    text = messages[-1]["content"] if messages else ""
    full = text + attachment_block(atts)
    history = store.get_messages(sid) if sid else messages[:-1]
    if sid:
        store.add_message(sid, "user", full, {"attachments": atts})
    audit({"event": "chat", "agent": "builtin", "chars": len(text), "session": sid, "files": len(atts)})
    answer = await chat(history + [{"role": "user", "content": full}],
                        effort=payload.get("effort") or SETTINGS.get("effort") or None,
                        model=SETTINGS.get("model") or None)
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
            atts = data.get("attachments") or []
            if not user_text and not atts:
                continue
            full = user_text + attachment_block(atts)
            history.append({"role": "user", "content": full})
            await send({"type": "user", "text": user_text, "attachments": atts})
            agent_id = data.get("agent") or "builtin"
            agent = REGISTRY.get(agent_id)
            sid = data.get("session_id")
            effort = data.get("effort") or SETTINGS.get("effort") or None
            use_model = SETTINGS.get("model") or None
            if agent and agent.demo:
                await send({"type": "tool", "name": "context.read", "args": {"agent": agent_id}})
                await asyncio.sleep(0.6)
                answer = demo_reply(agent_id, user_text)
                await send({"type": "tool_result", "name": "context.read", "text": "（模拟）已读取上下文"})
            elif agent and agent.transport == "acp":
                if sid:
                    store.add_message(sid, "user", full, {"attachments": atts})

                async def acp_event(ev: dict):
                    upd = ev.get("update") or {}
                    if ev.get("acp") in ("tool_call", "tool_call_update"):
                        await send({"type": "tool", "name": upd.get("title") or "tool", "args": {}})
                    elif ev.get("acp") == "agent_thought_chunk":
                        piece = (upd.get("content") or {}).get("text") or ""
                        if piece:
                            await send({"type": "thought", "text": piece})

                answer = await acp_chat(agent, sid or "default", full, ACP_STATE,
                                        on_event=acp_event)
                if sid:
                    store.add_message(sid, "assistant", answer)
            else:
                if sid:
                    base = store.get_messages(sid)
                    store.add_message(sid, "user", full, {"attachments": atts})
                    answer = await chat(base + [{"role": "user", "content": full}],
                                        on_event=send, effort=effort, model=use_model)
                    store.add_message(sid, "assistant", answer)
                else:
                    answer = await chat(history, on_event=send, effort=effort, model=use_model)
            history.append({"role": "assistant", "content": answer})
            await send({"type": "assistant", "text": answer})
    except WebSocketDisconnect:
        return


app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
