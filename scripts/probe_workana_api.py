"""Probe Workana for faster JSON endpoints."""
from __future__ import annotations

import re

import httpx

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
}

CANDIDATES = [
    "https://www.workana.com/jobs?category=it-programming&page=1",
    "https://www.workana.com/en/jobs?category=it-programming&page=1",
    "https://www.workana.com/jobs/search?category=it-programming&page=1",
    "https://www.workana.com/en/jobs/search?category=it-programming&page=1",
    "https://www.workana.com/api/jobs?category=it-programming&page=1",
]


def main() -> None:
    with httpx.Client(timeout=20, follow_redirects=True) as client:
        for url in CANDIDATES:
            try:
                r = client.get(url, headers=HEADERS)
                ct = r.headers.get("content-type", "")
                has_results = "results-initials" in r.text or '"results"' in r.text
                print(f"{r.status_code} {len(r.text):>7} {ct[:40]:<40} results={has_results} {url}")
            except Exception as exc:
                print(f"ERR {url} -> {exc}")

        page = client.get(
            "https://www.workana.com/en/jobs?category=it-programming&page=1",
            headers={**HEADERS, "Accept": "text/html"},
        )
        scripts = re.findall(r'src="(https://cf\.wkncdn\.com/static/assets/build/[^"]+\.js)"', page.text)
        print(f"\nFound {len(scripts)} JS bundles")
        for script in scripts[:3]:
            js = client.get(script).text
            for pattern in [r"/jobs[^\"']{0,80}", r"loadResults", r"searchResults", r"results-initials"]:
                hits = set(re.findall(pattern, js))
                if hits:
                    print(f"  {script.split('/')[-1]}: {list(hits)[:5]}")


if __name__ == "__main__":
    main()
