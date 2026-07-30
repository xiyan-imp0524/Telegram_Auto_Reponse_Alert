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
