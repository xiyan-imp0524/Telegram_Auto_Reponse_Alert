import statistics
import time

import httpx

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
}
URL = "https://www.workana.com/en/jobs?category=it-programming&page=1"

times = []
with httpx.Client(timeout=20, follow_redirects=True) as client:
    for _ in range(5):
        start = time.perf_counter()
        r = client.get(URL, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        slugs = [item["slug"] for item in data["results"]["results"]]
        elapsed = (time.perf_counter() - start) * 1000
        times.append(elapsed)
        print(f"{elapsed:.0f}ms | {len(slugs)} jobs | newest={slugs[0][:50]}")

print(f"avg={statistics.mean(times):.0f}ms min={min(times):.0f}ms max={max(times):.0f}ms")
