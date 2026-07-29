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
            **(headers or {}),
        }
        if cookies:
            self._session.cookies.update(cookies)

    @property
    def cookies(self) -> Any:
        return self._session.cookies

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        allow_redirects: bool = True,
    ) -> Any:
        return self._request(
            "GET",
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=allow_redirects,
        )

    def post(
        self,
        url: str,
        *,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        allow_redirects: bool = True,
    ) -> Any:
        return self._request(
            "POST",
            url,
            data=data,
            headers=headers,
            timeout=timeout,
            allow_redirects=allow_redirects,
        )

    def _request(
        self,
        method: str,
        url: str,
        *,
        data: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
        allow_redirects: bool = True,
    ) -> Any:
        global _active_impersonate

        merged = {**self._default_headers, **(headers or {})}
        timeout_s = timeout if timeout is not None else self.timeout
        candidates = list(IMPERSONATE_CANDIDATES)
        if _active_impersonate and _active_impersonate in candidates:
            candidates.remove(_active_impersonate)
            candidates.insert(0, _active_impersonate)

        last_error: Exception | None = None
        for impersonate in candidates:
            try:
                response = self._session.request(
                    method,
                    url,
                    data=data,
                    headers=merged,
                    timeout=timeout_s,
                    allow_redirects=allow_redirects,
                    impersonate=impersonate,
                )
            except Exception as exc:  # network / TLS errors
                last_error = exc
                logger.warning("Workana %s failed with %s: %s", impersonate, type(exc).__name__, exc)
                continue

            if is_cloudflare_challenge(response):
                last_error = CloudflareBlockedError(
                    f"Cloudflare blocked with impersonate={impersonate} "
                    f"({response.status_code})"
                )
                logger.warning("%s", last_error)
                continue

            if _active_impersonate != impersonate:
                logger.info("Using Chrome impersonation profile: %s", impersonate)
                _active_impersonate = impersonate
            return response

        if last_error is not None:
            raise last_error
        raise CloudflareBlockedError("Cloudflare blocked all impersonation profiles")

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> WorkanaHttpClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
