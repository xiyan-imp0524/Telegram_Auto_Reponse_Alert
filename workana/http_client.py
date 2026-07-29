"""HTTP client that impersonates Chrome to pass Cloudflare."""

from __future__ import annotations

import logging
from typing import Any

from curl_cffi import requests as curl_requests

logger = logging.getLogger(__name__)

# Prefer newer Chrome profiles; fall back if Cloudflare fingerprint changes.
IMPERSONATE_CANDIDATES = (
    "chrome131",
    "chrome124",
    "chrome120",
    "chrome116",
    "chrome",
)
DEFAULT_TIMEOUT = 30.0
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

_active_impersonate: str | None = None


class CloudflareBlockedError(RuntimeError):
    """Raised when Cloudflare challenge HTML is returned instead of Workana."""


def is_cloudflare_challenge(response: Any) -> bool:
    status = getattr(response, "status_code", 0)
    text = (getattr(response, "text", None) or "")[:800].lower()
    headers = getattr(response, "headers", {}) or {}
    server = str(headers.get("server", "")).lower()

    markers = (
        "just a moment",
        "cf-browser-verification",
        "cf-challenge",
        "attention required",
        "enable javascript and cookies",
        "checking your browser",
        "cloudflare",
    )
    if status in {403, 503} and any(marker in text for marker in markers):
        return True
    if "just a moment" in text or "cf-browser-verification" in text:
        return True
    if server == "cloudflare" and status in {403, 503} and "application/json" not in str(
        headers.get("content-type", "")
    ):
        return True
    return False


def _ensure_not_cloudflare(response: Any) -> None:
    if is_cloudflare_challenge(response):
        raise CloudflareBlockedError(
            f"Cloudflare blocked Workana request ({getattr(response, 'status_code', '?')})"
        )


class WorkanaHttpClient:
    """Thin Session wrapper with Chrome TLS fingerprinting and CF fallbacks."""

    def __init__(
        self,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
    ) -> None:
        self.timeout = timeout
        self._session = curl_requests.Session()
        self._default_headers = {
            "User-Agent": USER_AGENT,
