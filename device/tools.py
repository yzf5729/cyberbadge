"""工具集：文件、网页、可选无头浏览器。所有文件操作限制在 AGENT_WORKDIR 内。"""
from __future__ import annotations

import os
import pathlib
from typing import Any

import httpx

ROOT = pathlib.Path(os.environ.get("AGENT_WORKDIR", "./work")).resolve()
ROOT.mkdir(parents=True, exist_ok=True)


def _safe(path: str) -> pathlib.Path:
    target = (ROOT / path).resolve()
    if target != ROOT and ROOT not in target.parents:
        raise ValueError(f"路径越界：{path}（只能在 {ROOT} 内操作）")
    return target


def read_file(path: str) -> str:
    p = _safe(path)
    if not p.is_file():
        return f"文件不存在：{path}"
    return p.read_text(encoding="utf-8", errors="replace")[:20000]


def write_file(path: str, content: str) -> str:
    p = _safe(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return f"已写入 {path}（{len(content)} 字符）"


def list_dir(path: str = ".") -> str:
    p = _safe(path)
    if not p.is_dir():
        return f"目录不存在：{path}"
    lines = []
    for item in sorted(p.iterdir())[:200]:
        lines.append(("[目录] " if item.is_dir() else "[文件] ") + item.name)
    return "\n".join(lines) or "（空目录）"


def http_get(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return "只支持 http/https"
    try:
        r = httpx.get(url, timeout=25, follow_redirects=True,
                      headers={"User-Agent": "cyberbadge/0.1"})
        return f"HTTP {r.status_code}\n{r.text[:15000]}"
    except Exception as exc:  # noqa: BLE001
        return f"抓取失败：{exc}"


def browser_open(url: str) -> str:
    """可选：需要 pip install playwright && playwright install chromium"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "未安装 Playwright。执行：pip install playwright && playwright install chromium"
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            title = page.title()
            text = page.inner_text("body")[:10000]
            browser.close()
            return f"标题：{title}\n\n{text}"
    except Exception as exc:  # noqa: BLE001
        return f"浏览器打开失败：{exc}"


_DISPATCH = {
    "read_file": read_file,
    "write_file": write_file,
    "list_dir": list_dir,
    "http_get": http_get,
    "browser_open": browser_open,
}

TOOLS: list[dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "read_file", "description": "读取工作区中的文本文件",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file", "description": "把文本写入工作区文件（会覆盖）",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                       "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "list_dir", "description": "列出工作区目录",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "http_get", "description": "抓取网页正文（纯 HTTP，不执行 JS）",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {
        "name": "browser_open", "description": "用无头浏览器打开网页并取正文（需 Playwright）",
        "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
]


def execute(name: str, args: dict) -> str:
    fn = _DISPATCH.get(name)
    if not fn:
        return f"未知工具：{name}"
    try:
        return str(fn(**args))
    except Exception as exc:  # noqa: BLE001
        return f"工具 {name} 出错：{exc}"
