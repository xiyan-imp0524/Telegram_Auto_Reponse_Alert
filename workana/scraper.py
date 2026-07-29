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
                        log.exception(
                            "Failed fetching Workana jobs for language=%s", lang
                        )

        if not batches:
            detail = "; ".join(errors) or "unknown error"
            raise RuntimeError(
                f"All Workana language fetches failed ({detail})"
            )

        if errors:
            log.warning(
                "Partial Workana fetch failure (%s/%s langs): %s",
                len(errors),
                len(self.languages),
                "; ".join(errors),
            )

        for results in batches:
            for raw in results:
                slug = raw.get("slug")
                if not slug or slug in seen_slugs:
                    continue
                seen_slugs.add(slug)
                merged.append(raw)
        return merged

    def fetch_recent_jobs(self, pages: int = 1) -> list[WorkanaJob]:
        jobs: list[WorkanaJob] = []
        seen_slugs: set[str] = set()

        for page in range(1, pages + 1):
            for raw in self.fetch_all_language_results(page):
                job = self.normalize_job(raw)
                if job.slug in seen_slugs:
                    continue
                seen_slugs.add(job.slug)
                jobs.append(job)

        return jobs

    def fetch_slugs(self, page: int = 1) -> list[str]:
        return [
            item["slug"]
            for item in self.fetch_all_language_results(page)
            if item.get("slug")
        ]

    def normalize_job(self, raw: dict[str, Any]) -> WorkanaJob:
        slug = raw["slug"]
        title = self._extract_title(raw.get("title", ""))
        description = self._clean_description(raw.get("description", ""))
        skills = [
            skill.get("anchorText", "").strip()
            for skill in raw.get("skills", [])
            if skill.get("anchorText")
        ]
        budget = raw.get("budget", "Not specified")
        budget_min, budget_max = self._parse_budget(budget)
        total_bids = self._parse_bids(raw.get("totalBids", ""))
        country = self._extract_country(raw.get("country", ""))
        subcategory = self._extract_subcategory(description)

        return WorkanaJob(
            slug=slug,
            title=title,
            url=f"{self.BASE_URL}/job/{slug}",
            description=description,
            skills=skills,
            budget=budget,
            budget_min_usd=budget_min,
            budget_max_usd=budget_max,
            total_bids=total_bids,
            posted_date=raw.get("postedDate", raw.get("publishedDate", "")),
            country=country,
            is_urgent=bool(raw.get("isUrgent")),
            is_hourly=bool(raw.get("isHourly")),
            author_name=raw.get("authorName", ""),
            subcategory=subcategory,
            has_verified_payment=bool(raw.get("hasVerifiedPaymentMethod")),
            language=str(raw.get("_language") or self.language),
            raw=raw,
        )

    def _client_or_create(self) -> WorkanaHttpClient:
        if self._client is None:
            self._client = WorkanaHttpClient(
                timeout=self.timeout,
                headers=JSON_HEADERS,
            )
            self._owns_client = True
        return self._client

    def _fetch_payload(self, page: int, *, language: str) -> dict[str, Any]:
        url = self._build_url(page, language=language)
        client = self._client_or_create()
        response = client.get(
            url,
            headers={
                **JSON_HEADERS,
