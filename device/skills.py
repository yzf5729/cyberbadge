"""技能：work/skills/*.md，frontmatter（name/description 可选）+ 正文即提示词。"""
from __future__ import annotations

import os
import pathlib
import re

SKILLS_DIR = pathlib.Path(os.environ.get("AGENT_WORKDIR", "./work")).resolve() / "skills"
FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def _parse(path: pathlib.Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta: dict[str, str] = {}
    m = FRONT.match(text)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()
        text = text[m.end():]
    title = meta.get("name") or next(
        (ln.lstrip("# ").strip() for ln in text.splitlines() if ln.strip()), path.stem
    )
    return {
        "name": path.stem,
        "title": title,
        "description": meta.get("description", ""),
        "body": text.strip(),
        "path": str(path),
    }


def scan() -> list[dict]:
    SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    return [_parse(p) for p in sorted(SKILLS_DIR.glob("*.md"))]


def get(name: str) -> dict | None:
    for s in scan():
        if s["name"] == name:
            return s
    return None


def prompt_section(enabled: dict[str, bool] | None = None, budget: int = 6000) -> str:
    """把已启用技能拼进 system prompt（每个最多 1200 字，总量受预算限制）。"""
    parts, total = [], 0
    for s in scan():
        if enabled is not None and not enabled.get(s["name"], True):
            continue
        chunk = f"### 技能：{s['title']}\n{s['body'][:1200]}"
        if total + len(chunk) > budget:
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n\n".join(parts)
