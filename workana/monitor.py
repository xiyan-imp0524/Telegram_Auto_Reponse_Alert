from __future__ import annotations

import logging
import time
from typing import Callable

from config import AppConfig
from telegram_bot.notifier import TelegramNotifier
from workana.optimizer import JobOptimizer
from workana.scraper import WorkanaScraper
from workana.storage import JobStore

logger = logging.getLogger("workana-monitor")


class RealtimeMonitor:
    """Poll Workana frequently and notify Telegram as soon as a new job appears."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.store = JobStore(config.db_path)
        self.optimizer = JobOptimizer(config.optimizer)
        self.notifier = TelegramNotifier(
            token=config.telegram_bot_token,
            chat_id=config.telegram_chat_id,
        )
        self.scraper = WorkanaScraper(
            language=config.workana_language,
            languages=config.workana_languages,
            category=config.workana_category,
        )
        self._known_slugs = self._load_known_slugs()
        self._raw_by_slug: dict[str, dict] = {}

    def _load_known_slugs(self) -> set[str]:
        return set(self.store.list_slugs())

    def bootstrap(self) -> int:
        """Mark current listings as seen so only future uploads trigger alerts."""
        results = self.scraper.fetch_results(page=1)
        seeded = 0
        for raw in results:
            slug = raw.get("slug")
            if not slug or slug in self._known_slugs:
                continue
            job = self.scraper.normalize_job(raw)
            self.store.mark_seen(
                slug=job.slug,
                title=job.title,
                url=job.url,
                score=0,
                notified=False,
            )
            self._known_slugs.add(slug)
            seeded += 1
        return seeded

    def poll_once(self, *, notify: bool = True) -> int:
        results = self.scraper.fetch_results(page=1)
        self._raw_by_slug = {
            raw["slug"]: raw for raw in results if raw.get("slug")
        }

        new_slugs = [
            slug for slug in self._raw_by_slug if slug not in self._known_slugs
        ]
        if not new_slugs:
            return 0

        sent = 0
        for slug in new_slugs:
            job = self.scraper.normalize_job(self._raw_by_slug[slug])
            optimized = self.optimizer.optimize([job])
            if not optimized:
                self._remember(job.slug, job.title, job.url, score=0, notified=False)
                continue

            matched = optimized[0]
            self._remember(
                matched.slug,
