from __future__ import annotations

import logging
import sys
import threading
from typing import Any
from urllib.parse import urlparse

from config import AppConfig
from telegram_bot.notifier import TelegramNotifier
from workana.client_enricher import ClientEnricher
from workana.health import HealthWatchdog
from workana.http_client import CloudflareBlockedError
from workana.models import WorkanaJob
from workana.optimizer import JobOptimizer
from workana.pusher_client import WorkanaPusherClient, WorkanaSession
from workana.scraper import WorkanaScraper
from workana.storage import JobStore

logger = logging.getLogger("workana-monitor")


class JobDispatcher:
    """Shared deduplication and Telegram delivery for poll + Pusher paths."""

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
        self._enricher = (
            ClientEnricher(cookie=config.workana_cookie, timeout=8.0)
            if config.workana_cookie
            else None
        )
        self._notified_slugs = set(self.store.list_notified_slugs())
        self._lock = threading.Lock()

    def bootstrap(self) -> int:
        seeded = 0
        for raw in self.scraper.fetch_all_language_results(page=1):
            slug = raw.get("slug")
            if not slug or slug in self._notified_slugs:
                continue
            job = self.scraper.normalize_job(raw)
            self.store.mark_seen(
                slug=job.slug,
                title=job.title,
                url=job.url,
                score=0,
                notified=False,
            )
            seeded += 1
        return seeded

    def catch_up_recent(self, max_age_hours: int = 6) -> int:
        """Send any recent jobs that were never notified."""
        sent = 0
        for raw in self.scraper.fetch_all_language_results(page=1):
            slug = raw.get("slug")
            if not slug or self.store.was_notified(slug):
                continue
            job = self.scraper.normalize_job(raw)
            age = JobOptimizer(self.config.optimizer)._posted_age_hours(job.posted_date)
            if age is not None and age > max_age_hours:
                continue
            if self.dispatch(job, source="catch-up"):
                sent += 1
        return sent

    def poll_once(self) -> tuple[int, int]:
        """Return (alerts_sent, listings_fetched)."""
        sent = 0
        results = self.scraper.fetch_all_language_results(page=1)
        for raw in results:
            slug = raw.get("slug")
            if not slug:
                continue
            job = self.scraper.normalize_job(raw)
            if self.dispatch(job, source="poll"):
                sent += 1
        return sent, len(results)

    def dispatch(self, job: WorkanaJob, *, source: str) -> bool:
        # Claim before enrich/send so Pusher + poll (or two processes) cannot double-send.
        with self._lock:
            if job.slug in self._notified_slugs or self.store.was_notified(job.slug):
                return False
            if not self.store.try_claim_notify(
                slug=job.slug,
                title=job.title,
                url=job.url,
                score=0.0,
            ):
                return False
            self._notified_slugs.add(job.slug)

        try:
            if self.config.notify_all:
                job.score = 0.0
                job = self._enrich_job(job)
                self.notifier.send_job(job)
                self.store.mark_seen(
                    slug=job.slug,
                    title=job.title,
                    url=job.url,
                    score=0,
                    notified=True,
                )
                logger.info(
                    "Alert sent via %s: %s [%s]",
                    source,
                    job.title,
                    job.subcategory or "IT & Programming",
                )
                return True

            optimized = self.optimizer.optimize([job])
            if not optimized:
                self.store.release_claim(job.slug)
                with self._lock:
                    self._notified_slugs.discard(job.slug)
                logger.info("Skipped %s from %s (filtered)", job.slug, source)
                return False

            matched = self._enrich_job(optimized[0])
            self.notifier.send_job(matched)
            self.store.mark_seen(
                slug=matched.slug,
                title=matched.title,
                url=matched.url,
                score=matched.score,
                notified=True,
            )
            logger.info("Alert sent via %s: %s", source, matched.title)
            return True
        except Exception:
            logger.exception("Telegram send failed for %s", job.slug)
            self.store.release_claim(job.slug)
            with self._lock:
                self._notified_slugs.discard(job.slug)
            return False

    def handle_pusher_payload(self, payload: dict[str, Any], *, source: str) -> None:
        job = self._payload_to_job(payload)
        if job is None:
            logger.info(
                "Ignored %s payload (could not parse job): %s",
                source,
                str(payload)[:200],
            )
            return
        self.dispatch(job, source=source)

    def _payload_to_job(self, payload: dict[str, Any]) -> WorkanaJob | None:
        slug = self._extract_slug(payload)
        if not slug:
            return None

        try:
            for raw in self.scraper.fetch_all_language_results(page=1):
                if raw.get("slug") == slug:
                    return self.scraper.normalize_job(raw)
        except Exception:
            logger.exception("Failed to enrich job %s from listing", slug)

        preferred = (
            str(payload.get("_language") or "")
            or self.config.workana_language
        )
        title = self._localized(payload.get("title"), preferred) or "New Workana project"
        description = self._localized(payload.get("body"), preferred) or ""

        return WorkanaJob(
            slug=slug,
            title=title,
            url=f"https://www.workana.com/job/{slug}",
            description=description,
            skills=self._extract_skills(payload),
            budget="Not specified",
            budget_min_usd=None,
            budget_max_usd=None,
            total_bids=None,
            posted_date="Just now",
            country="Unknown",
            is_urgent=False,
            is_hourly=False,
            author_name="",
            language=preferred or "en",
            raw=payload,
        )

    def _enrich_job(self, job: WorkanaJob) -> WorkanaJob:
        if job.raw.get("hasVerifiedPaymentMethod"):
            job.has_verified_payment = True
        if not job.author_name or not job.author_name.strip():
            job.author_name = str(job.raw.get("authorName", ""))

        if self._enricher is None:
            return job

        try:
            profile = self._enricher.fetch_profile(job.slug)
            if profile.name:
                job.author_name = profile.name
            elif not job.author_name.strip():
                job.author_name = "Not disclosed"
            if profile.job_title:
                job.title = profile.job_title
            job.member_since = profile.member_since
            job.member_year = profile.member_year
            job.published_projects = profile.published_projects
            job.projects_paid = profile.projects_paid
            if profile.has_verified_payment:
                job.has_verified_payment = True
        except Exception:
            logger.exception("Failed to fetch client profile for %s", job.slug)
        return job

    def close(self) -> None:
        self.scraper.close()
        if self._enricher is not None:
            self._enricher.close()

    @staticmethod
    def _localized(value: Any, locale: str) -> str:
        if isinstance(value, dict):
            for key in (locale, "en", "es", "pt"):
                if key in value and value[key]:
                    return str(value[key])
            return str(next(iter(value.values()), ""))
        return str(value or "")

    @staticmethod
    def _extract_skills(payload: dict[str, Any]) -> list[str]:
        skills_raw = payload.get("skills", [])
        if isinstance(skills_raw, dict):
            return [str(item) for item in skills_raw.values()]
        return [str(skill) for skill in skills_raw]

    @staticmethod
    def _extract_slug(payload: dict[str, Any]) -> str | None:
        if payload.get("slug"):
            return str(payload["slug"])

        url = str(payload.get("url") or payload.get("link") or "")
        if not url:
            return None

        path = urlparse(url).path.strip("/")
        if path.startswith("job/"):
            return path.split("/", 1)[1]
        return None


class HybridMonitor:
    """Pusher for instant alerts + polling backup (like Slack monitors)."""

    def __init__(self, config: AppConfig) -> None:
        if not config.workana_cookie:
            raise ValueError("WORKANA_COOKIE is required for hybrid mode")

        self.config = config
        self.dispatcher = JobDispatcher(config)
        self.health = HealthWatchdog(
            fail_threshold=config.health_fail_threshold,
            empty_threshold=config.health_empty_threshold,
            alert_cooldown_seconds=config.health_alert_cooldown_seconds,
            heartbeat_path=config.heartbeat_path,
            on_alert=self._send_health_alert,
            on_fatal=self._fatal_restart,
        )
        self.session = WorkanaSession.from_cookie(
            config.workana_cookie,
            language=config.workana_language,
        )
        self._client = WorkanaPusherClient(
            self.session,
            languages=config.workana_languages,
            on_project_added=lambda payload: self.dispatcher.handle_pusher_payload(
                payload, source="pusher:added"
            ),
            on_notification=lambda payload: self.dispatcher.handle_pusher_payload(
                payload, source="pusher:notification"
            ),
        )
        self._stop = threading.Event()
        self._fatal = False

    def run_forever(self) -> None:
        self._startup_probe()

        if self.config.bootstrap_on_start and self.dispatcher.store.count_seen() == 0:
            seeded = self.dispatcher.bootstrap()
            logger.info("Bootstrapped %s existing jobs", seeded)

        caught = self.dispatcher.catch_up_recent(max_age_hours=6)
        if caught:
            logger.info("Catch-up sent %s missed recent job(s)", caught)

        langs = ", ".join(self.config.workana_languages)
        self.dispatcher.notifier.send_text(
            "Workana monitor started.\n"
            "Mode: hybrid (Pusher + polling backup)\n"
            f"Category: {self.config.workana_category}\n"
            f"Languages: {langs}\n"
            f"Pusher channels: projects-{' / projects-'.join(self.config.workana_languages)}\n"
            f"Poll backup: every {self.config.poll_interval_seconds}s\n"
            "Health watchdog: ON (Telegram alert + auto-restart on outage)"
        )

        self._client.start()
        interval = self.config.poll_interval_seconds

        try:
            while not self._stop.is_set() and not self._fatal:
                try:
                    sent, fetched = self.dispatcher.poll_once()
                    self.health.record_success(result_count=fetched)
                    if sent:
                        logger.info("Poll backup sent %s alert(s)", sent)
                except Exception as exc:
                    self.health.record_failure(exc)
                    if isinstance(exc, CloudflareBlockedError):
                        logger.error("Cloudflare is blocking Workana requests")
                    else:
                        logger.exception("Poll backup failed")
                self._stop.wait(interval)
        except KeyboardInterrupt:
            logger.info("Stopping hybrid monitor")
        finally:
            self._client.stop()
            self.dispatcher.close()

        if self._fatal:
            sys.exit(2)

    def _startup_probe(self) -> None:
        try:
            results = self.dispatcher.scraper.fetch_all_language_results(page=1)
            if not results:
                raise RuntimeError("Startup probe returned 0 Workana jobs")
            self.health.probe_ok(detail=f"startup_results={len(results)}")
            logger.info("Startup probe OK — %s jobs visible", len(results))
        except Exception as exc:
            message = (
                "Workana monitor FAILED startup health check.\n"
                f"{exc}\n"
                "Process will exit so run_forever can retry."
            )
            logger.exception("%s", message)
            try:
                self.dispatcher.notifier.send_text(message)
            except Exception:
                logger.exception("Could not send startup failure alert")
            raise

    def _send_health_alert(self, message: str) -> None:
        self.dispatcher.notifier.send_text(message)

    def _fatal_restart(self, message: str) -> None:
        logger.error("Fatal health condition — exiting for restart: %s", message)
        self._fatal = True
        self._stop.set()
