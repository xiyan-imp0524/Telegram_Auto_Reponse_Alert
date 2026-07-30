from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from workana.http_client import USER_AGENT, WorkanaHttpClient


@dataclass(slots=True)
class ClientProfile:
    name: str = ""
    job_title: str = ""
    member_since: str = ""
    member_year: str = ""
    published_projects: int | None = None
    projects_paid: int | None = None
    has_verified_payment: bool = False

    @property
    def is_populated(self) -> bool:
        return bool(
            self.member_since
            or self.published_projects is not None
            or self.projects_paid is not None
        )


class ClientEnricher:
    def __init__(self, *, cookie: str, timeout: float = 20.0) -> None:
        self.cookie = cookie.strip()
        self._client = WorkanaHttpClient(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Cookie": self.cookie},
        )

    def close(self) -> None:
        self._client.close()

    def fetch_profile(self, slug: str) -> ClientProfile:
        response = self._client.get(f"https://www.workana.com/job/{slug}")
        response.raise_for_status()
        return self._parse_profile(response.text)

    @staticmethod
    def _parse_profile(html: str) -> ClientProfile:
        soup = BeautifulSoup(html, "html.parser")
        profile = ClientProfile()

        title_el = soup.select_one("h1.h2, header h1, .project-header h1, h1")
        if title_el:
            profile.job_title = " ".join(title_el.get_text(" ", strip=True).split())

        name_el = soup.select_one(".user-name, .media-heading, .employer-name")
        if name_el:
            profile.name = name_el.get_text(" ", strip=True)

        for block in soup.select("div.item-data"):
            value_el = block.select_one("p.h4")
            label_el = block.find("p", class_=lambda c: c != "h4")
            if not label_el:
                label_el = block.find_all("p")[-1] if block.find_all("p") else None
            if not label_el:
                continue

            label = label_el.get_text(" ", strip=True).lower()
            value = value_el.get_text(" ", strip=True) if value_el else label_el.get_text(" ", strip=True)

            if "published projects" in label:
                profile.published_projects = ClientEnricher._to_int(value)
            elif "projects paid" in label or "payments" in label:
                profile.projects_paid = ClientEnricher._to_int(value)
            elif "member since" in label or value.lower().startswith("member since"):
                member_text = value if "member since" in value.lower() else label_el.get_text(" ", strip=True)
                profile.member_since = re.sub(
                    r"^member since:?\s*",
                    "",
                    member_text,
                    flags=re.I,
                ).strip()
                year_match = re.search(r"(20\d{2})", profile.member_since)
                if year_match:
                    profile.member_year = year_match.group(1)

        verified = soup.find(string=re.compile(r"verified payment", re.I))
        profile.has_verified_payment = verified is not None
        return profile

    @staticmethod
    def _to_int(value: str) -> int | None:
        match = re.search(r"\d+", value or "")
        return int(match.group(0)) if match else None
