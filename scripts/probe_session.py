"""Probe authenticated Workana session for Pusher config."""
from __future__ import annotations

import json
import re

import httpx

COOKIE = "workana_session=g9obh70ts9i16h2pcq7c4snh47"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Cookie": COOKIE,
}

with httpx.Client(timeout=30, follow_redirects=True, headers=HEADERS) as client:
    for url in [
        "https://www.workana.com/en/jobs?category=it-programming",
        "https://www.workana.com/users/notifications",
        "https://www.workana.com/dashboard",
    ]:
        r = client.get(url)
        print(f"\n=== {url} -> {r.status_code} len={len(r.text)} ===")
        if "login" in str(r.url).lower():
            print("REDIRECTED TO LOGIN - cookie may be invalid")
        for pattern in [
            r"Workana\.pusher\s*=\s*(\{.*?\});",
            r'"pusher"\s*:\s*(\{.*?\})',
            r"applicationKey['\"]?\s*[:=]\s*['\"]([^'\"]+)",
            r"authEndpoint['\"]?\s*[:=]\s*['\"]([^'\"]+)",
            r"channel['\"]?\s*[:=]\s*['\"]([^'\"]+)",
            r"loggedInCompany['\"]?\s*:\s*(true|false)",
            r"skillNotifications[^]]{0,200}",
        ]:
            hits = re.findall(pattern, r.text, re.S | re.I)
            if hits:
                print(f"  {pattern[:40]}: {str(hits[0])[:300]}")

    # Try JSON notifications
    r = client.get(
        "https://www.workana.com/users/notifications",
        headers={
            **HEADERS,
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
        },
    )
    print(f"\nnotifications json: {r.status_code} ct={r.headers.get('content-type')}")
    print(r.text[:500])
