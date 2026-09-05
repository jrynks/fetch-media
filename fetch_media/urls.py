"""Public http(s) URLs only. No file://, no cookies, no local/loopback."""

from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}


class UrlError(ValueError):
    pass


def validate_public_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        raise UrlError("missing URL")
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_SCHEMES:
        shown = scheme if scheme else "missing-scheme"
        raise UrlError(
            f"only public http(s) URLs are supported, not {shown}. "
            "fetch-media v1 does not follow login/private flows."
        )
    host = parsed.hostname
    if not host:
        raise UrlError("URL is missing a host")
    lowered = host.lower().rstrip(".")
    if lowered in {"localhost", "localhost.localdomain"} or lowered.endswith(".localhost"):
        raise UrlError("refusing local/loopback URL")
    if _literal_ip_blocked(lowered):
        raise UrlError("refusing local, loopback, or link-local URL")
    return raw


def _literal_ip_blocked(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(
        ip.is_loopback
        or ip.is_unspecified
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
    )
