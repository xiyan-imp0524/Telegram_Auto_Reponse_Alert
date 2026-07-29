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
                "Accept-Language": f"{language},en;q=0.9",
            },
        )
        response.raise_for_status()
        return self._parse_response(response)

    def _build_url(self, page: int, *, language: str) -> str:
        return (
            f"{self.BASE_URL}/{language}/jobs"
            f"?category={self.category}&order=recent&page={page}"
        )

    @staticmethod
    def _parse_response(response: Any) -> dict[str, Any]:
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            body = response.json()
            if isinstance(body, dict) and "results" in body:
                payload = body["results"]
                if isinstance(payload, dict) and "results" in payload:
                    return payload
                if isinstance(payload, list):
                    return {"results": payload}
            if isinstance(body, dict) and "results" in body.get("results", {}):
                return body["results"]

        match = RESULTS_INITIALS_PATTERN.search(response.text)
        if not match:
            raise ValueError("Could not find Workana job results in response")

        return json.loads(html.unescape(match.group(1)))

    @staticmethod
    def _extract_title(title_html: str) -> str:
        if not title_html:
            return "Untitled project"
        soup = BeautifulSoup(title_html, "html.parser")
        span = soup.find("span")
        candidates: list[str] = []
        if span and span.get("title"):
            candidates.append(str(span["title"]).strip())
        if span:
            candidates.append(span.get_text(" ", strip=True))
        candidates.append(soup.get_text(" ", strip=True))

        best = ""
        for candidate in candidates:
            cleaned = " ".join(candidate.split())
            cleaned = cleaned.rstrip(".").rstrip("…").rstrip(".")
            if cleaned.endswith("..."):
                cleaned = cleaned[:-3].rstrip()
            if len(cleaned) > len(best):
                best = cleaned
        return best or "Untitled project"

    @staticmethod
    def _clean_description(description_html: str) -> str:
        if not description_html:
            return ""
        text = BeautifulSoup(description_html, "html.parser").get_text("\n", strip=True)
        return re.sub(r"\n{3,}", "\n\n", text)

    @staticmethod
    def _parse_budget(budget: str) -> tuple[float | None, float | None]:
        if not budget:
            return None, None

        normalized = budget.replace(".", "").replace(",", "")
        numbers = re.findall(r"[\d]+", normalized)
        if not numbers:
            return None, None

        values = [float(number) for number in numbers[:2]]
        if len(values) == 1:
            return values[0], values[0]
        return values[0], values[1]

    @staticmethod
    def _parse_bids(total_bids: str) -> int | None:
        if not total_bids:
            return None
        match = re.search(r"(\d+)", total_bids)
        return int(match.group(1)) if match else None

    @staticmethod
    def _extract_subcategory(description: str) -> str:
        if not description:
            return ""
        match = re.search(
            r"(?:Subcategory|Subcategor[ií]a)\s*:?\s*(.+?)(?:\n|Project size|Tama[nñ]o|Skills|Habilidades|$)",
            description,
            re.IGNORECASE,
        )
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_country(country_html: str) -> str:
        if not country_html:
            return "Unknown"
        soup = BeautifulSoup(country_html, "html.parser")
        country = soup.select_one(".country-name")
        if country:
            return country.get_text(" ", strip=True)
        img = soup.find("img")
        if img and img.get("title"):
            return str(img["title"]).strip()
        return soup.get_text(" ", strip=True) or "Unknown"
