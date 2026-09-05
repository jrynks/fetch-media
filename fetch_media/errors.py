"""Map yt-dlp stderr to a compact, honest error. Never invent success."""

from __future__ import annotations

import re

# Session / private — v1 will not scrape cookies or log in.
LOGIN_SNIPPETS = (
    "sign in",
    "signing in",
    "login required",
    "please log in",
    "please sign in",
    "private video",
    "this video is private",
    "video is private",
    "members-only",
    "members only",
    "join this channel",
    "this video is available to this channel's members",
    "use --cookies",
    "cookies-from-browser",
    "oauth",
    "age-restricted",
    "confirm your age",
    "not a bot",
    "http error 401",
    "http error 403: forbidden",
)

COOKIES_UNSUPPORTED = (
    "cookies-from-browser is not supported in fetch-media v1; "
    "pass a public URL instead (no session scraping)."
)

PRIVATE_UNSUPPORTED = (
    "This URL requires login or is private. "
    "fetch-media v1 only supports public URLs."
)

ERROR_LINE = re.compile(r"^ERROR:\s*(.+)$", re.MULTILINE | re.IGNORECASE)

# Drop noisy prefixes yt-dlp adds.
PREFIXES = re.compile(
    r"^(?:ERROR:\s*)?(?:\[[^\]]+\]\s*)?",
    re.IGNORECASE,
)


def classify_yt_dlp_error(stderr: str, stdout: str = "") -> str:
    blob = f"{stderr or ''}\n{stdout or ''}"
    low = blob.lower()
    if any(snippet in low for snippet in LOGIN_SNIPPETS):
        return PRIVATE_UNSUPPORTED
    extracted = _extract_error_line(stderr) or _extract_error_line(stdout)
    if extracted:
        return _truncate(extracted)
    stripped = (stderr or stdout or "").strip()
    if stripped:
        return _truncate(stripped.splitlines()[-1])
    return "yt-dlp failed"


def _extract_error_line(text: str) -> str | None:
    if not text:
        return None
    matches = ERROR_LINE.findall(text)
    if not matches:
        return None
    raw = matches[-1].strip()
    raw = PREFIXES.sub("", raw).strip()
    return raw or None


def _truncate(message: str, limit: int = 400) -> str:
    message = re.sub(r"\s+", " ", message).strip()
    if len(message) <= limit:
        return message
    return message[: limit - 1] + "…"
