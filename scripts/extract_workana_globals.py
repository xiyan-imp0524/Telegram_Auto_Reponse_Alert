"""Extract full Workana globals from authenticated page."""
from __future__ import annotations

import json
import re

import httpx

COOKIE = "workana_session=g9obh70ts9i16h2pcq7c4snh47"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Cookie": COOKIE,
}

r = httpx.get(
    "https://www.workana.com/en/jobs?category=it-programming",
    headers=HEADERS,
    follow_redirects=True,
    timeout=30,
)
text = r.text

for name in ["Workana.pusher", "Workana.worker", "Workana.locale", "Workana.notificationSettings"]:
    m = re.search(rf"{re.escape(name)}\s*=\s*(\{{.*?\}})\s*;", text, re.S)
    if m:
        raw = m.group(1)
        try:
            data = json.loads(raw)
            print(f"\n=== {name} ===")
            print(json.dumps(data, indent=2)[:2000])
        except json.JSONDecodeError:
            print(f"\n=== {name} (raw) ===")
            print(raw[:500])
    else:
        print(f"NOT FOUND: {name}")

# CSRF meta
csrf = re.search(r'name="csrf-token"\s+content="([^"]+)"', text)
print("\nCSRF:", csrf.group(1) if csrf else "none")

# all cookies from response
print("\nSet-Cookie headers:", r.headers.get_list("set-cookie"))
