"""Probe Workana authenticated notification surfaces (no cookies)."""
import re

import httpx

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
}

URLS = [
    "https://www.workana.com/users/notifications",
    "https://www.workana.com/users/notifications?format=json",
    "https://www.workana.com/en/users/notifications",
    "https://www.workana.com/users/notifications/unread",
    "https://www.workana.com/users/notifications/count",
    "https://www.workana.com/users/saved_searches",
    "https://www.workana.com/jobs/saved_searches",
]

with httpx.Client(timeout=20, follow_redirects=True) as client:
    for url in URLS:
        try:
            r = client.get(url, headers=HEADERS)
            ct = r.headers.get("content-type", "")
            body = r.text[:180].replace("\n", " ")
            print(f"{r.status_code:>3} {len(r.text):>6} {ct[:35]:<35} {url}")
            print(f"     {body}")
        except Exception as exc:
            print(f"ERR {url}: {exc}")

    page = client.get(
        "https://www.workana.com/en/jobs?category=it-programming",
        headers={**HEADERS, "Accept": "text/html"},
    )
    for pattern in [
        r"instant-notifications[^\"']{0,120}",
        r"notifications[^\"']{0,80}",
        r"wss?://[^\"']+",
        r"EventSource\([^)]+\)",
        r"/users/notifications[^\"']*",
        r"saved[_-]?search[^\"']{0,80}",
    ]:
        hits = sorted(set(re.findall(pattern, page.text, re.I)))
        if hits:
            print(f"\nHTML pattern {pattern}:")
            for hit in hits[:8]:
                print(" ", hit[:120])
