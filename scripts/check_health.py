"""Quick health check for the Workana monitor."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config import AppConfig
from workana.http_client import CloudflareBlockedError, WorkanaHttpClient
from workana.scraper import WorkanaScraper


def main() -> int:
    config = AppConfig.from_env(require_telegram=False)
    heartbeat = config.heartbeat_path
    print(f"heartbeat: {heartbeat}")
    if heartbeat.exists():
        print(heartbeat.read_text(encoding="utf-8").strip())
    else:
        print("(missing — monitor may not be running)")

    try:
        with WorkanaHttpClient(timeout=20) as client:
            response = client.get(
                f"https://www.workana.com/{config.workana_language}/jobs"
                f"?category={config.workana_category}&order=recent&page=1",
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            print(f"http: {response.status_code} {response.headers.get('content-type', '')}")
        with WorkanaScraper(
            languages=config.workana_languages,
            category=config.workana_category,
        ) as scraper:
            jobs = scraper.fetch_all_language_results(page=1)
            print(f"jobs: {len(jobs)} across {config.workana_languages}")
    except CloudflareBlockedError as exc:
        print(f"FAIL cloudflare: {exc}")
        return 2
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
