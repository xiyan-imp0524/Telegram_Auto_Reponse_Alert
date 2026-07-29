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
