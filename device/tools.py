"""工具集：文件、文档、OCR、图像、格式转换、网页。

所有文件操作限制在 AGENT_WORKDIR 内；重依赖按需导入，未安装时返回可读提示。
"""
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


def _need(module: str, hint: str):
    try:
        return __import__(module)
    except ImportError as exc:  # pragma: no cover - 依赖缺失路径
        raise RuntimeError(f"缺少依赖 {module}：{hint}") from exc


# ---------- 基础文件 ----------

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


# ---------- Office 文档 ----------

def read_docx(path: str) -> str:
    """抽取 docx 正文段落与表格（内容级）。"""
    docx = _need("docx", "pip install python-docx")
    p = _safe(path)
    if not p.is_file():
        return f"文件不存在：{path}"
    doc = docx.Document(str(p))
    paras = [para.text for para in doc.paragraphs if para.text.strip()]
    out = [f"段落 {len(paras)} 个：", *paras[:200]]
    if doc.tables:
        out.append(f"\n表格 {len(doc.tables)} 个：")
        for i, table in enumerate(doc.tables[:5], 1):
            out.append(f"表 {i}（{len(table.rows)}×{len(table.columns)}）：")
            for row in table.rows[:10]:
                out.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(out)[:20000]


def read_xlsx(path: str, sheet: str | None = None, max_rows: int = 50) -> str:
    openpyxl = _need("openpyxl", "pip install openpyxl")
    p = _safe(path)
    if not p.is_file():
        return f"文件不存在：{path}"
    wb = openpyxl.load_workbook(str(p), data_only=True, read_only=True)
    names = wb.sheetnames
    targets = [sheet] if sheet in names else names[:3]
    out = [f"工作表：{', '.join(names)}"]
    for name in targets:
        ws = wb[name]
        out.append(f"\n[{name}] {ws.max_row} 行 × {ws.max_column} 列")
        for row in list(ws.iter_rows(values_only=True))[:max_rows]:
            cells = ["" if c is None else str(c) for c in row]
            if any(cells):
                out.append(" | ".join(cells))
    wb.close()
    return "\n".join(out)[:20000]


def read_pptx(path: str) -> str:
    pptx = _need("pptx", "pip install python-pptx")
    p = _safe(path)
    if not p.is_file():
        return f"文件不存在：{path}"
    prs = pptx.Presentation(str(p))
    out = [f"共 {len(prs.slides)} 页"]
    for i, slide in enumerate(prs.slides, 1):
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                texts.append(shape.text_frame.text.strip())
        out.append(f"\n第 {i} 页：" + (" / ".join(texts) if texts else "（无文字）"))
    return "\n".join(out)[:20000]


def read_pdf(path: str, max_pages: int = 20) -> str:
    pypdf = _need("pypdf", "pip install pypdf")
    p = _safe(path)
    if not p.is_file():
        return f"文件不存在：{path}"
    reader = pypdf.PdfReader(str(p))
    out = [f"共 {len(reader.pages)} 页"]
    for i, page in enumerate(reader.pages[:max_pages], 1):
        text = (page.extract_text() or "").strip()
        out.append(f"\n--- 第 {i} 页 ---\n{text[:3000] if text else '（无文字层，可能是扫描件，建议用 ocr_pdf）'}")
    return "\n".join(out)[:24000]


def convert_office(path: str, to: str = "pdf") -> str:
    """LibreOffice headless 转换（本地优先，失败提示原因）。"""
    from .office_convert import convert

    p = _safe(path)
    result = convert(p, to)
    if result.ok:
        return f"已转换：{result.output}（{result.elapsed_s:.1f}s）"
    return f"转换失败：{result.detail}"


# ---------- OCR ----------

def ocr_image(path: str, lang: str = "chi_sim+eng") -> str:
    pytesseract = _need("pytesseract", "pip install pytesseract pillow，并安装 tesseract-ocr 与 chi_sim 语言包")
    pil = _need("PIL.Image", "pip install pillow")
    p = _safe(path)
    if not p.is_file():
        return f"文件不存在：{path}"
    text = pytesseract.image_to_string(pil.open(str(p)), lang=lang)
    return (text or "（没有识别到文字）").strip()[:20000]


def ocr_pdf(path: str, max_pages: int = 5, lang: str = "chi_sim+eng") -> str:
    fitz = _need("fitz", "pip install PyMuPDF")
    import tempfile

    pytesseract = _need("pytesseract", "pip install pytesseract")
    pil = _need("PIL.Image", "pip install pillow")
    p = _safe(path)
    if not p.is_file():
        return f"文件不存在：{path}"
    doc = fitz.open(str(p))
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, page in enumerate(doc[:max_pages], 1):
            pix = page.get_pixmap(dpi=150)
            img = pathlib.Path(tmp) / f"p{i}.png"
            pix.save(str(img))
            text = pytesseract.image_to_string(pil.open(str(img)), lang=lang).strip()
            out.append(f"--- 第 {i} 页 ---\n{text or '（无文字）'}")
    return "\n".join(out)[:24000]


# ---------- 图像 ----------

def image_op(path: str, action: str = "info", width: int | None = None,
             height: int | None = None, box: str | None = None) -> str:
    pil = _need("PIL.Image", "pip install pillow")
    p = _safe(path)
    if not p.is_file():
        return f"文件不存在：{path}"
    img = pil.open(str(p))
    if action == "info":
        return f"{p.name}: {img.width}×{img.height}, {img.mode}, {p.stat().st_size/1024:.0f}KB"
    if action == "resize":
        w, h = width or img.width, height or img.height
        out = p.with_name(f"{p.stem}_{w}x{h}{p.suffix}")
        img.resize((w, h)).save(out)
        return f"已缩放：{out.name}（{w}×{h}）"
    if action == "crop" and box:
        left, top, right, bottom = (int(v) for v in box.split(","))
        out = p.with_name(f"{p.stem}_crop{p.suffix}")
        img.crop((left, top, right, bottom)).save(out)
        return f"已裁剪：{out.name}"
    if action == "convert":
        out = p.with_suffix(".jpg")
        img.convert("RGB").save(out, quality=88)
        return f"已转换：{out.name}"
    return f"不支持的 action：{action}（info/resize/crop/convert）"


# ---------- 网页 ----------

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
    "read_docx": read_docx,
    "read_xlsx": read_xlsx,
    "read_pptx": read_pptx,
    "read_pdf": read_pdf,
    "convert_office": convert_office,
    "ocr_image": ocr_image,
    "ocr_pdf": ocr_pdf,
    "image_op": image_op,
    "http_get": http_get,
    "browser_open": browser_open,
}


def _f(name: str, description: str, props: dict[str, Any], required: list[str] | None = None) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": props, "required": required or []}}}


TOOLS: list[dict[str, Any]] = [
    _f("read_file", "读取工作区中的文本文件", {"path": {"type": "string"}}, ["path"]),
    _f("write_file", "把文本写入工作区文件（会覆盖）",
       {"path": {"type": "string"}, "content": {"type": "string"}}, ["path", "content"]),
    _f("list_dir", "列出工作区目录", {"path": {"type": "string"}}),
    _f("read_docx", "读取 Word 文档正文与表格", {"path": {"type": "string"}}, ["path"]),
    _f("read_xlsx", "读取 Excel 表格（可指定工作表）",
       {"path": {"type": "string"}, "sheet": {"type": "string"}, "max_rows": {"type": "integer"}}, ["path"]),
    _f("read_pptx", "读取 PowerPoint 每页文字", {"path": {"type": "string"}}, ["path"]),
    _f("read_pdf", "读取 PDF 文本层（前 20 页）", {"path": {"type": "string"}}, ["path"]),
    _f("convert_office", "用 LibreOffice 转换格式（如 docx→pdf）",
       {"path": {"type": "string"}, "to": {"type": "string"}}, ["path"]),
    _f("ocr_image", "OCR 识别图片文字（默认中英文）",
       {"path": {"type": "string"}, "lang": {"type": "string"}}, ["path"]),
    _f("ocr_pdf", "把 PDF 前几页渲染成图后 OCR（扫描件用）",
       {"path": {"type": "string"}, "max_pages": {"type": "integer"}, "lang": {"type": "string"}}, ["path"]),
    _f("image_op", "图片信息/缩放/裁剪/转 JPG",
       {"path": {"type": "string"}, "action": {"type": "string"}, "width": {"type": "integer"},
        "height": {"type": "integer"}, "box": {"type": "string"}}, ["path"]),
    _f("http_get", "抓取网页正文（纯 HTTP，不执行 JS）", {"url": {"type": "string"}}, ["url"]),
    _f("browser_open", "用无头浏览器打开网页并取正文（需 Playwright）", {"url": {"type": "string"}}, ["url"]),
]


def execute(name: str, args: dict) -> str:
    from .security import audit
    fn = _DISPATCH.get(name)
    if not fn:
        audit({"event": "tool", "tool": name, "ok": False, "error": "unknown"})
        return f"未知工具：{name}"
    try:
        out = str(fn(**args))
        audit({"event": "tool", "tool": name, "ok": True, "bytes": len(out)})
        return out
    except Exception as exc:  # noqa: BLE001
        audit({"event": "tool", "tool": name, "ok": False, "error": str(exc)[:120]})
        return f"工具 {name} 出错：{exc}"
