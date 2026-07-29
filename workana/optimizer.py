from __future__ import annotations

import re
from dataclasses import dataclass

from workana.models import WorkanaJob


@dataclass(slots=True)
class OptimizerConfig:
    preferred_skills: list[str]
    keywords: list[str]
    excluded_keywords: list[str]
    min_budget_usd: float
    max_bids: int | None
    max_age_hours: int | None = None


class JobOptimizer:
    AGE_PATTERN = re.compile(
        r"(?P<value>\d+)\s*(?P<unit>minute|minutes|min|hour|hours|day|days|week|weeks|"
        r"minuto|minutos|hora|horas|día|dias|días|semana|semanas)",
        re.IGNORECASE,
    )

    def __init__(self, config: OptimizerConfig) -> None:
        self.config = config
        self.preferred_skills = {skill.lower() for skill in config.preferred_skills}
        self.keywords = [keyword.lower() for keyword in config.keywords if keyword]
        self.excluded_keywords = [
            keyword.lower() for keyword in config.excluded_keywords if keyword
        ]

    def optimize(self, jobs: list[WorkanaJob]) -> list[WorkanaJob]:
        scored: list[WorkanaJob] = []
        for job in jobs:
            if not self._passes_filters(job):
                continue
            job.score = self._score(job)
            job.matched_skills = self._matched_skills(job)
            scored.append(job)
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored

    def _passes_filters(self, job: WorkanaJob) -> bool:
        haystack = self._search_text(job)

        if self.excluded_keywords and any(
            keyword in haystack for keyword in self.excluded_keywords
        ):
            return False

        if self.keywords and not any(keyword in haystack for keyword in self.keywords):
            return False

        if self.config.min_budget_usd > 0:
            budget_floor = job.budget_max_usd or job.budget_min_usd
            if budget_floor is None or budget_floor < self.config.min_budget_usd:
                return False

        if self.config.max_bids is not None:
            if job.total_bids is not None and job.total_bids > self.config.max_bids:
                return False

        if self.config.max_age_hours is not None:
            age_hours = self._posted_age_hours(job.posted_date)
            if age_hours is not None and age_hours > self.config.max_age_hours:
                return False

        return True

    def _score(self, job: WorkanaJob) -> float:
        score = 0.0
        haystack = self._search_text(job)

        matched = self._matched_skills(job)
        score += len(matched) * 12

        if self.keywords:
            score += sum(8 for keyword in self.keywords if keyword in haystack)

        if job.is_urgent:
            score += 10

        if job.total_bids is not None:
            if job.total_bids <= 5:
                score += 15
            elif job.total_bids <= 15:
                score += 8
            elif job.total_bids <= 30:
                score += 3

        budget_ceiling = job.budget_max_usd or job.budget_min_usd
        if budget_ceiling:
            score += min(budget_ceiling / 250, 20)

        age_hours = self._posted_age_hours(job.posted_date)
        if age_hours is not None:
            if age_hours <= 6:
                score += 12
            elif age_hours <= 24:
                score += 8
            elif age_hours <= 48:
                score += 4

        return round(score, 2)

    def _matched_skills(self, job: WorkanaJob) -> list[str]:
        if not self.preferred_skills:
            return []
        return [
            skill
            for skill in job.skills
            if skill.lower() in self.preferred_skills
        ]

    @staticmethod
    def _search_text(job: WorkanaJob) -> str:
        return " ".join(
            [
                job.title.lower(),
                job.description.lower(),
                " ".join(skill.lower() for skill in job.skills),
            ]
        )

    @classmethod
    def _posted_age_hours(cls, posted_date: str) -> float | None:
        if not posted_date:
            return None

        match = cls.AGE_PATTERN.search(posted_date.lower())
        if not match:
            return None

        value = int(match.group("value"))
        unit = match.group("unit").lower()

        if unit.startswith("min"):
            return value / 60
        if unit.startswith("hour") or unit.startswith("hora"):
            return float(value)
        if unit.startswith("day") or unit.startswith("d"):
            return value * 24
        if unit.startswith("week") or unit.startswith("semana"):
            return value * 24 * 7
        return None
