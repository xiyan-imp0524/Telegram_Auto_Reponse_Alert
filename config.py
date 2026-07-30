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
