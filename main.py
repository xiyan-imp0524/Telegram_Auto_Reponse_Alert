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
    try:
        if config.bootstrap_on_start and monitor.store.count_seen() == 0:
            seeded = monitor.bootstrap()
            logger.info(
                "First run: bootstrapped %s existing jobs — only new uploads will alert",
                seeded,
            )

        monitor.run_forever()
    finally:
        monitor.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Monitor Workana IT & Programming jobs and notify Telegram."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one polling cycle and exit.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and score jobs without sending Telegram messages.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.once and not args.dry_run:
        from workana.instance_lock import acquire_singleton_lock

        acquire_singleton_lock()
    config = AppConfig.from_env(require_telegram=not args.dry_run)

    if args.once or args.dry_run:
        sent = run_once(config, notify=not args.dry_run)
        if args.dry_run:
            logger.info("Dry run complete. %s new jobs detected.", sent)
            if sent == 0:
                preview_jobs(config)
        return 0

    run_forever(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
