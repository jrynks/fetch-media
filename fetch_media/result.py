"""Compact fetch-media/v1 JSON chip. Never invent path/title/duration on failure."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal, Optional

from fetch_media import SCHEMA

Status = Literal["OK", "FAILED"]


def _clean_str(value: Any) -> Optional[str]:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return None


def duration_sec_from(value: Any) -> Optional[int]:
    """Coerce yt-dlp duration to int seconds. None if missing/unusable — never guess."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number or number < 0:  # NaN or negative
        return None
    return int(round(number))


@dataclass
class FetchResult:
    url: Optional[str]
    status: Status
    path: Optional[str] = None
    title: Optional[str] = None
    duration_sec: Optional[int] = None
    extractor: Optional[str] = None
    error: Optional[str] = None
    id: Optional[str] = None
    ext: Optional[str] = None
    filesize_bytes: Optional[int] = None
    extras: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        chip: dict[str, Any] = {
            "schema": SCHEMA,
            "url": self.url,
            "status": self.status,
            "path": self.path if self.status == "OK" else None,
            "title": self.title,
            "duration_sec": self.duration_sec,
            "extractor": self.extractor,
            "error": self.error,
        }
        if self.id is not None:
            chip["id"] = self.id
        if self.ext is not None:
            chip["ext"] = self.ext
        if self.filesize_bytes is not None:
            chip["filesize_bytes"] = self.filesize_bytes
        if self.extras:
            for key, value in self.extras.items():
                if key not in chip:
                    chip[key] = value
        return chip

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

    def format_human(self) -> str:
        if self.status == "FAILED":
            err = self.error or "failed"
            return f"FAILED  {err}"
        path = self.path or "(no file)"
        lines = [f"OK  {path}"]
        if self.title:
            lines.append(f"    {self.title}")
        bits = []
        if self.duration_sec is not None:
            bits.append(_fmt_duration(self.duration_sec))
        if self.extractor:
            bits.append(self.extractor)
        if self.ext:
            bits.append(self.ext)
        if bits:
            lines.append("    " + "  ".join(bits))
        return "\n".join(lines)


def ok(
    url: Optional[str],
    *,
    path: Optional[str] = None,
    title: Optional[str] = None,
    duration_sec: Optional[int] = None,
    extractor: Optional[str] = None,
    id: Optional[str] = None,
    ext: Optional[str] = None,
    filesize_bytes: Optional[int] = None,
    extras: Optional[dict[str, Any]] = None,
) -> FetchResult:
    return FetchResult(
        url=url,
        status="OK",
        path=path,
        title=_clean_str(title),
        duration_sec=duration_sec,
        extractor=_clean_str(extractor),
        error=None,
        id=_clean_str(id),
        ext=_clean_str(ext),
        filesize_bytes=filesize_bytes,
        extras=extras,
    )


def failed(
    url: Optional[str],
    error: str,
    *,
    title: Optional[str] = None,
    duration_sec: Optional[int] = None,
    extractor: Optional[str] = None,
    id: Optional[str] = None,
    ext: Optional[str] = None,
    extras: Optional[dict[str, Any]] = None,
) -> FetchResult:
    # Hard contract: FAILED never carries a path (invented or leftover).
    return FetchResult(
        url=url,
        status="FAILED",
        path=None,
        title=_clean_str(title),
        duration_sec=duration_sec,
        extractor=_clean_str(extractor),
        error=error,
        id=_clean_str(id),
        ext=_clean_str(ext),
        extras=extras,
    )


def _fmt_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{sec:02d}"
    return f"{minutes}:{sec:02d}"
