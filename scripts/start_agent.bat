@echo off
cd /d C:\AI\cyberbadge
set AGENT_WORKDIR=C:\AI\cyberbadge\work
"C:\AI\cyberbadge\.venv\Scripts\python.exe" -m uvicorn device.main:app --host 0.0.0.0 --port 8000 >> C:\AI\cyberbadge\agent.log 2>&1
