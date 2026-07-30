from __future__ import annotations

import logging
import re
import time
from typing import Any
from urllib.parse import urlparse

from config import AppConfig
from telegram_bot.notifier import TelegramNotifier
from workana.models import WorkanaJob
from workana.optimizer import JobOptimizer
from workana.pusher_client import WorkanaPusherClient, WorkanaSession
from workana.scraper import WorkanaScraper
from workana.storage import JobStore

logger = logging.getLogger("workana-monitor")


class PusherMonitor:
    def __init__(self, config: AppConfig) -> None:
        if not config.workana_cookie:
            raise ValueError("WORKANA_COOKIE is required for Pusher realtime mode")

        self.config = config
        self.session = WorkanaSession.from_cookie(
            config.workana_cookie,
            language=config.workana_language,
        )
        self.store = JobStore(config.db_path)
        self.optimizer = JobOptimizer(config.optimizer)
        self.notifier = TelegramNotifier(
            token=config.telegram_bot_token,
            chat_id=config.telegram_chat_id,
        )
        self.scraper = WorkanaScraper(
            language=config.workana_language,
            category=config.workana_category,
        )
        self._known_slugs = set(self.store.list_slugs())
        self._client = WorkanaPusherClient(
            self.session,
            on_project_added=self._handle_project_event,
            on_notification=self._handle_notification_event,
        )

    def run_forever(self) -> None:
        self.notifier.send_text(
            "Workana instant monitor started.\n"
            f"Mode: Pusher push ({self.session.projects_channel})\n"
            "You will be alerted as soon as Workana publishes a new project."
        )
        self._client.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping Pusher monitor")
        finally:
            self._client.stop()
            self.scraper.close()

    def _handle_project_event(self, payload: dict[str, Any]) -> None:
        job = self._payload_to_job(payload)
        if job is None:
            return
        self._process_job(job, source="pusher:added")

    def _handle_notification_event(self, payload: dict[str, Any]) -> None:
        job = self._notification_to_job(payload)
        if job is None:
            return
        self._process_job(job, source="pusher:notification")

    def _process_job(self, job: WorkanaJob, *, source: str) -> None:
        if job.slug in self._known_slugs:
            return

        optimized = self.optimizer.optimize([job])
        self.store.mark_seen(
            slug=job.slug,
            title=job.title,
            url=job.url,
            score=optimized[0].score if optimized else 0,
            notified=False,
        )
        self._known_slugs.add(job.slug)

        if not optimized:
            logger.info("Ignored %s from %s (filtered out)", job.slug, source)
            return

        matched = optimized[0]
        self.notifier.send_job(matched)
        self.store.mark_seen(
            slug=matched.slug,
            title=matched.title,
            url=matched.url,
            score=matched.score,
            notified=True,
        )
        logger.info("Instant alert sent (%s): %s", source, matched.title)

    def _payload_to_job(self, payload: dict[str, Any]) -> WorkanaJob | None:
        url = payload.get("url", "")
        slug = self._extract_slug(url, payload)
        if not slug:
            logger.debug("Skipping event without slug: %s", payload)
            return None

        locale = self.config.workana_language
        title_data = payload.get("title", {})
        body_data = payload.get("body", {})
        title = title_data.get(locale) if isinstance(title_data, dict) else str(title_data)
        description = body_data.get(locale) if isinstance(body_data, dict) else str(body_data)

        skills_raw = payload.get("skills", [])
        if isinstance(skills_raw, dict):
            skills = [str(value) for value in skills_raw.values()]
        else:
            skills = [str(skill) for skill in skills_raw]

        return WorkanaJob(
            slug=slug,
            title=title or "New Workana project",
            url=f"https://www.workana.com/job/{slug}",
            description=description or "",
            skills=skills,
            budget="Not specified",
            budget_min_usd=None,
            budget_max_usd=None,
            total_bids=None,
            posted_date="Just now",
            country="Unknown",
            is_urgent=False,
            is_hourly=False,
            author_name="",
            raw=payload,
        )

    def _notification_to_job(self, payload: dict[str, Any]) -> WorkanaJob | None:
        url = payload.get("url") or payload.get("link") or ""
        slug = self._extract_slug(url, payload)
        if not slug:
            return None

        try:
            results = self.scraper.fetch_results(page=1)
            for raw in results:
                if raw.get("slug") == slug:
                    return self.scraper.normalize_job(raw)
        except Exception:
            logger.exception("Failed to enrich notification for %s", slug)

        title = str(payload.get("title", "New Workana project"))
        description = str(payload.get("body", ""))
        return WorkanaJob(
            slug=slug,
            title=title,
            url=f"https://www.workana.com/job/{slug}",
            description=description,
            skills=[],
            budget="Not specified",
            budget_min_usd=None,
            budget_max_usd=None,
            total_bids=None,
            posted_date="Just now",
            country="Unknown",
            is_urgent=False,
            is_hourly=False,
            author_name="",
            raw=payload,
        )

    @staticmethod
    def _extract_slug(url: str, payload: dict[str, Any]) -> str | None:
        if payload.get("slug"):
            return str(payload["slug"])

        if not url:
            return None

        path = urlparse(url).path.strip("/")
        if path.startswith("job/"):
            return path.split("/", 1)[1]
        return None
