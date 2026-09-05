"""Environment check: yt-dlp on PATH, ffmpeg for merges, writable out dir."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from fetch_media import __version__
from fetch_media.result import FetchResult, failed, ok
from fetch_media.ytdlp import DEFAULT_OUT_DIR, find_ffmpeg, find_yt_dlp, YtDlpNotFound


def run_doctor(*, out_dir: Path | str = DEFAULT_OUT_DIR) -> FetchResult:
    yt = _probe_yt_dlp()
    ff = _probe_ffmpeg()
    py = {
        "ok": True,
        "version": sys.version.split()[0],
        "path": sys.executable,
    }
    dest = Path(out_dir).expanduser()
    writable = _ensure_writable(dest)
    extras: dict[str, Any] = {
        "yt_dlp": yt,
        "ffmpeg": ff,
        "python": py,
        "out_dir": {"path": str(dest), "writable": writable},
        "fetch_media": __version__,
    }
    if not yt.get("ok"):
        return failed(
            None,
            "yt-dlp is not on PATH. Install with: pip install yt-dlp",
            extras=extras,
        )
    if not writable:
        return failed(
            None,
            f"output directory is not writable: {dest}",
            extras=extras,
        )
    return ok(None, extras=extras)


def format_doctor_human(result: FetchResult) -> str:
    extras = result.extras or {}
    lines = []
    for key, label in (
        ("yt_dlp", "yt-dlp"),
        ("ffmpeg", "ffmpeg"),
        ("python", "python"),
    ):
        info = extras.get(key) or {}
        mark = "ok" if info.get("ok") else "MISSING"
        version = info.get("version") or "-"
        path = info.get("path") or "-"
        lines.append(f"{label:<8} {mark:<8} {version:<16} {path}")
    out = extras.get("out_dir") or {}
    writable = "writable" if out.get("writable") else "NOT WRITABLE"
    lines.append(f"{'out':<8} {writable:<8} {out.get('path') or DEFAULT_OUT_DIR}")
    if result.status == "FAILED" and result.error:
        lines.append(f"FAILED  {result.error}")
    else:
        ff = extras.get("ffmpeg") or {}
        if not ff.get("ok"):
            lines.append("note    ffmpeg missing — audio/video merges may fail")
        lines.append("OK      fetch-media doctor")
    return "\n".join(lines)


def _probe_yt_dlp() -> dict[str, Any]:
    try:
        argv = find_yt_dlp()
    except YtDlpNotFound:
        return {"ok": False, "version": None, "path": None}
    path = argv[0] if len(argv) == 1 else " ".join(argv)
    version = _run_version([*argv, "--version"])
    return {"ok": True, "version": version, "path": path}


def _probe_ffmpeg() -> dict[str, Any]:
    path = find_ffmpeg()
    if not path:
        return {"ok": False, "version": None, "path": None}
    version = None
    try:
        proc = subprocess.run(
            [path, "-version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )
        first = (proc.stdout or "").splitlines()[:1]
        if first:
            # "ffmpeg version 7.0.2-static ..."
            parts = first[0].split()
            if len(parts) >= 3 and parts[0].lower() == "ffmpeg":
                version = parts[2]
            else:
                version = first[0].strip()
    except (OSError, subprocess.TimeoutExpired):
        version = None
    return {"ok": True, "version": version, "path": path}


def _run_version(argv: list[str]) -> Optional[str]:
    try:
        proc = subprocess.run(
            argv,
            check=False,
            capture_output=True,
            text=True,
            timeout=8,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (proc.stdout or proc.stderr or "").strip()
    return text.splitlines()[0].strip() if text else None


def _ensure_writable(dest: Path) -> bool:
    try:
        dest.mkdir(parents=True, exist_ok=True)
        probe = dest / ".fetch-media-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False
