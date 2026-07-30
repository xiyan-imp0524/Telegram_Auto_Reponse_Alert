from __future__ import annotations

import argparse
import logging
import sys

from config import AppConfig
from telegram_bot.notifier import TelegramNotifier
from workana.hybrid_monitor import HybridMonitor
from workana.monitor import RealtimeMonitor
from workana.optimizer import JobOptimizer
from workana.scraper import WorkanaScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("workana-monitor")


def run_once(config: AppConfig, *, notify: bool = True) -> int:
    monitor = RealtimeMonitor(config)
    try:
        if config.bootstrap_on_start and monitor.store.count_seen() == 0:
            seeded = monitor.bootstrap()
            logger.info("Bootstrapped %s existing jobs (no alerts sent)", seeded)
        return monitor.poll_once(notify=notify)
    finally:
        monitor.close()


def preview_jobs(config: AppConfig) -> None:
    with WorkanaScraper(
        language=config.workana_language,
        category=config.workana_category,
    ) as scraper:
        optimizer = JobOptimizer(config.optimizer)
        jobs = optimizer.optimize(scraper.fetch_recent_jobs(pages=config.scrape_pages))
        for job in jobs[:5]:
            logger.info(
                "[score %.1f] %s | %s | bids=%s",
                job.score,
                job.title,
                job.budget,
                job.total_bids,
            )


def run_forever(config: AppConfig) -> None:
    if config.monitor_mode == "hybrid":
        HybridMonitor(config).run_forever()
        return

    if config.monitor_mode == "pusher":
        from workana.pusher_monitor import PusherMonitor

        PusherMonitor(config).run_forever()
        return

    monitor = RealtimeMonitor(config)
