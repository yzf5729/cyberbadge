"""访问控制：token 鉴权、Cookie/查询参数兼容、简单限流、审计。"""
from __future__ import annotations

import os
import pathlib
import secrets
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse, PlainTextResponse

WORKDIR = pathlib.Path(os.environ.get("AGENT_WORKDIR", "./work")).resolve()
TOKEN_FILE = WORKDIR / "token.txt"
AUDIT_FILE = WORKDIR / "audit.log"
PUBLIC_PATHS = {"/api/health"}
AUTH_COOKIE = "cb_token"


def token() -> str:
    env = os.environ.get("AGENT_TOKEN", "").strip()
    if env:
        return env
    if TOKEN_FILE.exists():
        t = TOKEN_FILE.read_text().strip()
        if t:
            return t
    t = secrets.token_urlsafe(24)
    WORKDIR.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(t)
    try:
        TOKEN_FILE.chmod(0o600)
    except OSError:
        pass
    return t


class RateLimiter:
    """滑动窗口：默认 120 次/分钟；chat 类接口 20 次/分钟。"""

    def __init__(self) -> None:
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.strict = ("/api/chat", "/api/task", "/api/reload")

    def hit(self, ip: str, path: str) -> bool:
        cls = "strict" if path.startswith(self.strict) else "normal"
        limit = 20 if cls == "strict" else 120
        key = f"{ip}:{cls}"
        now = time.time()
        q = self.hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def audit(record: dict) -> None:
    WORKDIR.mkdir(parents=True, exist_ok=True)
    try:
        if AUDIT_FILE.exists() and AUDIT_FILE.stat().st_size > 5 * 1024 * 1024:
            AUDIT_FILE.replace(AUDIT_FILE.with_suffix(".log.1"))
        import json
        with AUDIT_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **record}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def extract_token(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    q = request.query_params.get("token", "")
    if q:
        return q.strip()
    return request.cookies.get(AUTH_COOKIE, "").strip()


async def guard(request: Request):
    """返回 None 表示放行；否则返回拒绝响应。"""
    path = request.url.path
    if path in PUBLIC_PATHS:
        return None
    ip = client_ip(request)
    if not limiter.hit(f"{ip}", path):
        audit({"ip": ip, "path": path, "event": "rate_limited"})
        return JSONResponse({"error": "too many requests"}, status_code=429)
    given = extract_token(request)
    if not given or not secrets.compare_digest(given, token()):
        audit({"ip": ip, "path": path, "event": "unauthorized"})
        if path.startswith("/api/"):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return PlainTextResponse(
            "需要访问令牌：在浏览器打开 http://<设备>:8000/?token=<令牌> ，"
            "令牌见设备上的 work/token.txt。", status_code=401
        )
    return None


def needs_cookie(request: Request) -> str | None:
    """带了 ?token= 且当前没有有效 cookie 时，返回要写入的 token。"""
    q = request.query_params.get("token", "").strip()
    if q and q == token() and request.cookies.get(AUTH_COOKIE) != q:
        return q
    return None
