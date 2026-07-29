from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class WorkanaJob:
    slug: str
    title: str
    url: str
    description: str
    skills: list[str]
    budget: str
    budget_min_usd: float | None
    budget_max_usd: float | None
    total_bids: int | None
    posted_date: str
    country: str
    is_urgent: bool
    is_hourly: bool
    author_name: str
    subcategory: str = ""
    member_since: str = ""
    member_year: str = ""
    published_projects: int | None = None
    projects_paid: int | None = None
    has_verified_payment: bool = False
    language: str = "en"
    score: float = 0.0
    matched_skills: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def id(self) -> str:
        return self.slug
