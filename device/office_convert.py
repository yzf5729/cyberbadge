"""LibreOffice headless 转换封装（胸牌本地，受内存闸门约束）。

设计约束（见 docs/capabilities.md）：
- 单并发：同一时刻只允许一个 soffice 进程；
- 内存闸门：MemAvailable 低于阈值直接拒绝；
- 超时：默认 120s，超时杀进程组；
- 隔离 profile：-env:UserInstallation=file:///tmp/lo-profile；
- 用完即退，不做常驻。

本模块只依赖标准库，可在 ARM64 板子上直接运行。
"""
from __future__ import annotations

import os
import pathlib
import shutil
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass

SOFFICE_CANDIDATES = [
    "soffice",
    "libreoffice",
    "/usr/bin/soffice",
    "/usr/lib/libreoffice/program/soffice",
]

MIN_AVAILABLE_MB = 700          # 低于此值拒绝本地转换
DEFAULT_TIMEOUT_S = 120
LOCK_PATH = pathlib.Path(os.environ.get("HOME", "/tmp")) / ".cache/cyberbadge/office.lock"


class OfficeError(RuntimeError):
    """转换失败（含内存不足、超时、未安装）。"""


@dataclass
class ConvertResult:
    ok: bool
    output: str = ""
    detail: str = ""
    elapsed_s: float = 0.0


def find_soffice() -> str | None:
    for c in SOFFICE_CANDIDATES:
        p = shutil.which(c) or (c if pathlib.Path(c).is_file() else None)
        if p:
            return p
    return None


def _mem_available_mb() -> int:
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        pass
    return 10**6  # 读不到就当充足，交给超时兜底


def _lock() -> int:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, ImportError) as exc:  # 已有任务在跑
        os.close(fd)
        raise OfficeError("本地转换忙（另一个 soffice 正在运行），请稍后或转远端") from exc
    return fd


def _unlock(fd: int) -> None:
    try:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def convert(src: str | os.PathLike[str], target: str = "pdf",
            timeout_s: int = DEFAULT_TIMEOUT_S,
            outdir: str | os.PathLike[str] | None = None) -> ConvertResult:
    """把 src 转成 target 格式（pdf/docx/xlsx/pptx 等）。

    返回 ConvertResult；失败抛出 OfficeError 的变体不抛，而是 ok=False。
    """
    src_path = pathlib.Path(src).expanduser()
    if not src_path.is_file():
        return ConvertResult(False, detail=f"文件不存在：{src_path}")
    if src_path.stat().st_size == 0:
        return ConvertResult(False, detail="文件为空")

    soffice = find_soffice()
    if not soffice:
        return ConvertResult(False, detail="未安装 LibreOffice（apt install libreoffice-core libreoffice-writer）")

    mem = _mem_available_mb()
    if mem < MIN_AVAILABLE_MB:
        return ConvertResult(False, detail=f"内存不足：可用 {mem}MB < {MIN_AVAILABLE_MB}MB，请转远端")

    dest = pathlib.Path(outdir).expanduser() if outdir else src_path.parent
    dest.mkdir(parents=True, exist_ok=True)

    fd = _lock()
    started = time.time()
    proc: subprocess.Popen[bytes] | None = None
    try:
        cmd = [
            soffice,
            "--headless",
            "--norestore",
            "--nolockcheck",
            "--nodefault",
            f"-env:UserInstallation=file://{tempfile.gettempdir()}/lo-profile",
            "--convert-to",
            target,
            "--outdir",
            str(dest),
            str(src_path),
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # 便于整组杀
        )
        try:
            out, _ = proc.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=10)
            return ConvertResult(False, detail=f"转换超时（>{timeout_s}s）", elapsed_s=time.time() - started)
        elapsed = time.time() - started
        expected = dest / f"{src_path.stem}.{target}"
        if proc.returncode != 0:
            tail = (out or b"").decode("utf-8", "replace")[-400:]
            return ConvertResult(False, detail=f"soffice 退出码 {proc.returncode}：{tail}", elapsed_s=elapsed)
        if not expected.is_file() or expected.stat().st_size < 1024:
            return ConvertResult(False, detail="转换结果缺失或过小（排版可能不支持）", elapsed_s=elapsed)
        return ConvertResult(True, output=str(expected), elapsed_s=elapsed)
    finally:
        _unlock(fd)


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="LibreOffice headless 转换")
    ap.add_argument("src", nargs="?")
    ap.add_argument("--to", default="pdf")
    ap.add_argument("--check", action="store_true", help="检查环境")
    a = ap.parse_args()
    if a.check:
        print("soffice:", find_soffice() or "未安装")
        print("MemAvailable:", f"{_mem_available_mb()}MB")
    elif a.src:
        r = convert(a.src, a.to)
        print("OK" if r.ok else "FAIL", r.output, r.detail, f"{r.elapsed_s:.1f}s")
    else:
        ap.print_help()
