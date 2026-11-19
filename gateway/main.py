"""薄网关：设备鉴权 + 转发到上游 LLM（可配置主备供应商）。

设备只拿到 DEVICE_TOKEN，拿不到上游 API Key。
运行：uvicorn gateway.main:app --port 8787
"""
from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

app = FastAPI(title="Agent Box Gateway", version="0.1.0")

DEVICE_TOKEN = os.environ.get("DEVICE_TOKEN", "change-me")

UPSTREAMS = [
    {
        "base": os.environ.get("UPSTREAM_BASE", "https://api.deepseek.com/v1").rstrip("/"),
        "key": os.environ.get("UPSTREAM_KEY", ""),
        "model": os.environ.get("UPSTREAM_MODEL", ""),
    }
]
fallback = os.environ.get("UPSTREAM_FALLBACK_BASE", "").strip()
if fallback:
    UPSTREAMS.append({
        "base": fallback.rstrip("/"),
        "key": os.environ.get("UPSTREAM_FALLBACK_KEY", ""),
        "model": os.environ.get("UPSTREAM_FALLBACK_MODEL", ""),
    })


def _check(auth: str | None) -> None:
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(401, "missing device token")
    if auth.removeprefix("Bearer ").strip() != DEVICE_TOKEN:
        raise HTTPException(401, "invalid device token")


@app.get("/health")
async def health():
    return {"ok": True, "upstreams": len(UPSTREAMS)}


@app.post("/v1/chat/completions")
async def proxy(payload: dict, authorization: str | None = Header(default=None)):
    _check(authorization)
    errors = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        for up in UPSTREAMS:
            if not up["key"]:
                continue
            body = dict(payload)
            if up["model"]:
                body["model"] = up["model"]
            try:
                r = await client.post(
                    f"{up['base']}/chat/completions",
                    headers={"Authorization": f"Bearer {up['key']}", "Content-Type": "application/json"},
                    json=body,
                )
                if r.status_code == 200:
                    return JSONResponse(r.json())
                errors.append(f"{up['base']} -> HTTP {r.status_code}: {r.text[:200]}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{up['base']} -> {exc}")
    return JSONResponse({"error": "所有上游都失败", "detail": errors}, status_code=502)
