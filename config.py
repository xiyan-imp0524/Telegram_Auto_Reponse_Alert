from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from workana.optimizer import OptimizerConfig


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _to_int(value: str | None, default: int) -> int:
    if not value:
        return default
    return int(value)


def _to_float(value: str | None, default: float) -> float:
    if not value:
        return default
    return float(value)


@dataclass(slots=True)
class AppConfig:
    telegram_bot_token: str
    telegram_chat_id: str
    monitor_mode: str
    workana_cookie: str
    poll_interval_seconds: int
    min_poll_interval_seconds: int
    bootstrap_on_start: bool
    notify_all: bool
    workana_language: str
    workana_languages: list[str]
    workana_category: str
    scrape_pages: int
    db_path: Path
    health_fail_threshold: int
    health_empty_threshold: int
    health_alert_cooldown_seconds: int
    heartbeat_path: Path
    optimizer: OptimizerConfig

    @classmethod
    def from_env(
        cls,
        env_file: Path | None = None,
        *,
        require_telegram: bool = True,
    ) -> AppConfig:
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        if require_telegram and (not token or not chat_id):
            raise ValueError(
                "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env"
            )

        max_bids_raw = os.getenv("MAX_BIDS", "").strip()
        max_bids = int(max_bids_raw) if max_bids_raw else None

        max_age_raw = os.getenv("MAX_AGE_HOURS", "").strip()
        max_age_hours = int(max_age_raw) if max_age_raw else None

        poll_interval = _to_int(os.getenv("POLL_INTERVAL_SECONDS"), 5)
        min_poll_interval = _to_int(os.getenv("MIN_POLL_INTERVAL_SECONDS"), 3)
        if poll_interval < min_poll_interval:
            poll_interval = min_poll_interval

        bootstrap_raw = os.getenv("BOOTSTRAP_ON_START", "true").strip().lower()
        bootstrap_on_start = bootstrap_raw not in {"0", "false", "no"}

        notify_all_raw = os.getenv("NOTIFY_ALL", "true").strip().lower()
        notify_all = notify_all_raw not in {"0", "false", "no"}

        monitor_mode = os.getenv("MONITOR_MODE", "hybrid").strip().lower()
        workana_cookie = os.getenv("WORKANA_COOKIE", "").strip()
        if monitor_mode in {"pusher", "hybrid"} and not workana_cookie:
            monitor_mode = "poll"

        languages_raw = os.getenv("WORKANA_LANGUAGES", "en,es,pt").strip().lower()
        if languages_raw in {"all", "*"}:
            workana_languages = ["en", "es", "pt"]
        else:
            workana_languages = _split_csv(languages_raw) or ["en", "es", "pt"]

        workana_language = os.getenv("WORKANA_LANGUAGE", workana_languages[0]).strip()
        if workana_language and workana_language not in workana_languages:
            workana_languages = [workana_language, *workana_languages]

        return cls(
            telegram_bot_token=token,
            telegram_chat_id=chat_id,
            monitor_mode=monitor_mode,
            workana_cookie=workana_cookie,
            poll_interval_seconds=poll_interval,
            min_poll_interval_seconds=min_poll_interval,
            bootstrap_on_start=bootstrap_on_start,
            notify_all=notify_all,
            workana_language=workana_language or workana_languages[0],
            workana_languages=workana_languages,
            workana_category=os.getenv("WORKANA_CATEGORY", "it-programming").strip(),
            scrape_pages=_to_int(os.getenv("SCRAPE_PAGES"), 1),
            db_path=Path(os.getenv("DB_PATH", "data/workana_jobs.db")),
            health_fail_threshold=_to_int(os.getenv("HEALTH_FAIL_THRESHOLD"), 5),
            health_empty_threshold=_to_int(os.getenv("HEALTH_EMPTY_THRESHOLD"), 8),
            health_alert_cooldown_seconds=_to_int(
                os.getenv("HEALTH_ALERT_COOLDOWN_SECONDS"), 300
            ),
            heartbeat_path=Path(os.getenv("HEARTBEAT_PATH", "data/heartbeat.txt")),
            optimizer=OptimizerConfig(
                preferred_skills=_split_csv(os.getenv("PREFERRED_SKILLS")),
                keywords=_split_csv(os.getenv("KEYWORDS")),
                excluded_keywords=_split_csv(os.getenv("EXCLUDED_KEYWORDS")),
                min_budget_usd=_to_float(os.getenv("MIN_BUDGET_USD"), 0),
                max_bids=max_bids,
                max_age_hours=max_age_hours,
            ),
        )
