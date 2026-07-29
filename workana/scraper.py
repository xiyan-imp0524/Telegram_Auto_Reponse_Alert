from __future__ import annotations

import html
import json
import re
from typing import Any

from bs4 import BeautifulSoup

from workana.http_client import USER_AGENT, WorkanaHttpClient
from workana.models import WorkanaJob

RESULTS_INITIALS_PATTERN = re.compile(
    r":results-initials='(\{.*?\})'\s",
    re.DOTALL,
)
JSON_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
    "Accept-Language": "en,en;q=0.9",
}


class WorkanaScraper:
    BASE_URL = "https://www.workana.com"
    ALL_LANGUAGES = ("en", "es", "pt")

    def __init__(
        self,
        *,
        language: str = "en",
        languages: list[str] | None = None,
        category: str = "it-programming",
        timeout: float = 20.0,
        client: WorkanaHttpClient | None = None,
    ) -> None:
        if languages:
            self.languages = [lang.strip().lower() for lang in languages if lang.strip()]
        else:
            self.languages = [language.strip().lower() or "en"]
        self.language = self.languages[0]
        self.category = category
        self.timeout = timeout
        self._client = client
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> WorkanaScraper:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def fetch_results(self, page: int = 1, *, language: str | None = None) -> list[dict[str, Any]]:
        lang = language or self.language
        payload = self._fetch_payload(page, language=lang)
        results = list(payload.get("results", []))
        for raw in results:
            raw["_language"] = lang
        return results

    def fetch_all_language_results(self, page: int = 1) -> list[dict[str, Any]]:
        """Fetch IT & Programming jobs across all languages in parallel, deduped by slug.

        Raises RuntimeError if every language request fails (never returns a silent empty list).
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import logging

        log = logging.getLogger(__name__)
        merged: list[dict[str, Any]] = []
        seen_slugs: set[str] = set()
        batches: list[list[dict[str, Any]]] = []
        errors: list[str] = []

        if len(self.languages) == 1:
            lang = self.languages[0]
            try:
                batches = [self.fetch_results(page, language=lang)]
            except Exception as exc:
                raise RuntimeError(
                    f"Failed fetching Workana jobs for language={lang}: {exc}"
                ) from exc
        else:
            with ThreadPoolExecutor(max_workers=len(self.languages)) as pool:
                futures = {
                    pool.submit(self.fetch_results, page, language=lang): lang
                    for lang in self.languages
                }
                for future in as_completed(futures):
                    lang = futures[future]
                    try:
                        batches.append(future.result())
                    except Exception as exc:
                        errors.append(f"{lang}: {exc}")
