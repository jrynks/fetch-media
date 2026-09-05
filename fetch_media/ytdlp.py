"""subprocess yt-dlp wrapper. List-argv only — never shell=True."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence

from fetch_media.errors import classify_yt_dlp_error
from fetch_media.result import FetchResult, duration_sec_from, failed, ok
from fetch_media.urls import UrlError, validate_public_url

DEFAULT_OUT_DIR = Path("/tmp/fetch-media")
PRINT_FILEPATH = "after_move:%(filepath)s"
INFO_JSON_SUFFIX = ".info.json"
SKIP_NAME_PARTS = (".part", ".ytdl", ".temp")
FORMAT_RE = re.compile(r"^[A-Za-z0-9_/*+\-\[\]().,:=]+$")
FILESIZE_RE = re.compile(r"^\d+(?:\.\d+)?[KMGTkmgt]?i?B?$")
FILESIZE_PARSE = re.compile(
    r"^(?P<n>\d+(?:\.\d+)?)(?P<u>[KMGTkmgt])?(?P<i>i)?[Bb]?$"
)

# yt-dlp argv we never pass through even if a caller tries.
REFUSED_FLAGS = {
    "--cookies-from-browser",
    "--cookies",
    "--netrc",
    "--username",
    "--password",
    "--video-password",
    "--ap-username",
    "--ap-password",
    "--add-header",
    "--exec",
    "--exec-before-download",
    "--enable-file-urls",
    "--load-info-json",
}


class YtDlpNotFound(RuntimeError):
    pass


def find_yt_dlp() -> list[str]:
    """Return argv prefix for yt-dlp. FETCH_MEDIA_YT_DLP overrides (tests)."""
    override = os.environ.get("FETCH_MEDIA_YT_DLP")
    if override:
        return shlex.split(override)
    binary = shutil.which("yt-dlp")
    if binary:
        return [binary]
    try:
        import yt_dlp  # noqa: F401
    except ImportError as exc:
        raise YtDlpNotFound(
            "yt-dlp is not on PATH. Install with: pip install yt-dlp"
        ) from exc
    return [sys.executable, "-m", "yt_dlp"]


def find_ffmpeg() -> Optional[str]:
    return shutil.which("ffmpeg")


def parse_max_filesize(spec: str) -> int:
    match = FILESIZE_PARSE.match(spec)
    if not match:
        raise ValueError("invalid --max-filesize value (try 50M)")
    number = float(match.group("n"))
    unit = (match.group("u") or "").upper()
    iec = bool(match.group("i"))
    base = 1024 if iec else 1000
    mul = {"": 1, "K": base, "M": base**2, "G": base**3, "T": base**4}[unit]
    return int(number * mul)


def build_get_argv(
    url: str,
    *,
    audio_only: bool = False,
    format: Optional[str] = None,
    out_dir: Path = DEFAULT_OUT_DIR,
    playlist: bool = False,
    max_filesize: Optional[str] = None,
    yt_dlp: Optional[Sequence[str]] = None,
) -> list[str]:
    prefix = list(yt_dlp) if yt_dlp is not None else find_yt_dlp()
    out_dir = Path(out_dir)
    template = str(out_dir / "%(id)s.%(ext)s")
    cmd: list[str] = [
        *prefix,
        "--restrict-filenames",
        "--write-info-json",
        "--ignore-config",
        "--no-progress",
        "--newline",
        "--no-colors",
        "--socket-timeout",
        "30",
        "-o",
        template,
        "--print",
        PRINT_FILEPATH,
    ]
    if not playlist:
        cmd.append("--no-playlist")
    if audio_only:
        cmd.extend(["-x", "--audio-format", "mp3"])
    if format:
        if not FORMAT_RE.match(format):
            raise ValueError("invalid --format value")
        cmd.extend(["-f", format])
    if max_filesize:
        if not FILESIZE_RE.match(max_filesize):
            raise ValueError("invalid --max-filesize value (try 50M)")
        cmd.extend(["--max-filesize", max_filesize])
    cmd.append("--")
    cmd.append(url)
    return cmd


def build_info_argv(
    url: str,
    *,
    playlist: bool = False,
    yt_dlp: Optional[Sequence[str]] = None,
) -> list[str]:
    prefix = list(yt_dlp) if yt_dlp is not None else find_yt_dlp()
    cmd: list[str] = [
        *prefix,
        "--dump-json",
        "--skip-download",
        "--ignore-config",
        "--no-progress",
        "--no-colors",
        "--socket-timeout",
        "30",
    ]
    if not playlist:
        cmd.append("--no-playlist")
    cmd.append("--")
    cmd.append(url)
    return cmd


def run_subprocess(argv: Sequence[str], *, timeout: Optional[float] = None) -> subprocess.CompletedProcess[str]:
    if any(a in REFUSED_FLAGS or a.split("=", 1)[0] in REFUSED_FLAGS for a in argv):
        raise ValueError("refused yt-dlp flag")
    return subprocess.run(
        list(argv),
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
        shell=False,
    )


def get_media(
    url: str,
    *,
    audio_only: bool = False,
    format: Optional[str] = None,
    out_dir: Path | str = DEFAULT_OUT_DIR,
    playlist: bool = False,
    max_filesize: Optional[str] = None,
    timeout: Optional[float] = None,
) -> FetchResult:
    try:
        url = validate_public_url(url)
    except UrlError as exc:
        return failed(url, str(exc))

    dest = Path(out_dir).expanduser()
    try:
        dest.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return failed(url, f"cannot write to {dest}: {exc}")

    try:
        argv = build_get_argv(
            url,
            audio_only=audio_only,
            format=format,
            out_dir=dest,
            playlist=playlist,
            max_filesize=max_filesize,
        )
    except YtDlpNotFound as exc:
        return failed(url, str(exc))
    except ValueError as exc:
        return failed(url, str(exc))

    try:
        proc = run_subprocess(argv, timeout=timeout)
    except subprocess.TimeoutExpired:
        return failed(url, f"yt-dlp timed out after {int(timeout or 0)}s")
    except FileNotFoundError:
        return failed(url, "yt-dlp is not on PATH. Install with: pip install yt-dlp")

    if proc.returncode != 0:
        return failed(url, classify_yt_dlp_error(proc.stderr, proc.stdout))

    paths = _existing_media_paths(proc.stdout, dest)
    if not paths:
        return failed(
            url,
            "download finished but no file was written (not treating as OK)",
        )

    media = paths[0]
    try:
        _assert_max_filesize(media, max_filesize)
    except ValueError as exc:
        return failed(url, str(exc))

    info = _load_info_json(media)
    meta = _fields_from_info(info)
    extras: dict = {}
    if len(paths) > 1:
        extras["paths"] = [str(p.resolve()) for p in paths]
    file_ext = media.suffix.lstrip(".") or None
    return ok(
        url,
        path=str(media.resolve()),
        title=meta.get("title"),
        duration_sec=meta.get("duration_sec"),
        extractor=meta.get("extractor"),
        id=meta.get("id"),
        ext=file_ext or meta.get("ext"),
        filesize_bytes=_filesize(media),
        extras=extras or None,
    )


def info_media(
    url: str,
    *,
    playlist: bool = False,
    timeout: Optional[float] = None,
) -> FetchResult:
    try:
        url = validate_public_url(url)
    except UrlError as exc:
        return failed(url, str(exc))

    try:
        argv = build_info_argv(url, playlist=playlist)
    except YtDlpNotFound as exc:
        return failed(url, str(exc))

    try:
        proc = run_subprocess(argv, timeout=timeout)
    except subprocess.TimeoutExpired:
        return failed(url, f"yt-dlp timed out after {int(timeout or 0)}s")
    except FileNotFoundError:
        return failed(url, "yt-dlp is not on PATH. Install with: pip install yt-dlp")

    if proc.returncode != 0:
        return failed(url, classify_yt_dlp_error(proc.stderr, proc.stdout))

    payload = _first_json_object(proc.stdout)
    if payload is None:
        return failed(url, "yt-dlp returned no metadata JSON")

    meta = _fields_from_info(payload)
    extras: dict = {}
    if playlist and isinstance(payload.get("entries"), list):
        extras["entry_count"] = len(payload["entries"])
    return ok(
        url,
        path=None,
        title=meta.get("title"),
        duration_sec=meta.get("duration_sec"),
        extractor=meta.get("extractor"),
        id=meta.get("id"),
        ext=meta.get("ext"),
        extras=extras or None,
    )


def _assert_max_filesize(path: Path, spec: Optional[str]) -> None:
    if not spec:
        return
    limit = parse_max_filesize(spec)
    size = _filesize(path)
    if size is not None and size > limit:
        raise ValueError(f"file exceeds --max-filesize {spec} ({size} bytes)")


def _existing_media_paths(stdout: str, out_dir: Path) -> list[Path]:
    found: list[Path] = []
    seen: set[str] = set()
    for line in (stdout or "").splitlines():
        candidate = line.strip()
        if not candidate or candidate.startswith("{"):
            continue
        path = Path(candidate)
        if not path.is_file():
            continue
        if _skip_media(path):
            continue
        resolved = str(path.resolve())
        if resolved in seen:
            continue
        seen.add(resolved)
        found.append(path)
    return found


def _skip_media(path: Path) -> bool:
    name = path.name
    if name.endswith(INFO_JSON_SUFFIX):
        return True
    lowered = name.lower()
    return any(part in lowered for part in SKIP_NAME_PARTS)


def _load_info_json(media: Path) -> Optional[dict]:
    candidates = [
        media.with_name(media.stem + INFO_JSON_SUFFIX),
        media.parent / f"{media.stem}{INFO_JSON_SUFFIX}",
    ]
    for candidate in candidates:
        data = _read_json_file(candidate)
        if data is not None:
            return data
    matches = [p for p in media.parent.glob(f"*{INFO_JSON_SUFFIX}") if p.is_file()]
    if len(matches) == 1:
        return _read_json_file(matches[0])
    return None


def _read_json_file(path: Path) -> Optional[dict]:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _first_json_object(text: str) -> Optional[dict]:
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            return data
    stripped = (text or "").strip()
    if stripped.startswith("{"):
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None
    return None


def _fields_from_info(info: Optional[dict]) -> dict:
    if not info:
        return {}
    extractor = info.get("extractor") or info.get("extractor_key")
    ext = info.get("ext") or info.get("audio_ext") or info.get("video_ext")
    if ext in (None, "none"):
        ext = None
    return {
        "title": info.get("title"),
        "duration_sec": duration_sec_from(info.get("duration")),
        "extractor": extractor,
        "id": info.get("id"),
        "ext": ext,
    }


def _filesize(path: Path) -> Optional[int]:
    try:
        size = path.stat().st_size
    except OSError:
        return None
    return size
