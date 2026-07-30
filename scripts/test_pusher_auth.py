"""Test Pusher channel auth with Workana session."""
from __future__ import annotations

import re

import httpx

SESSION = "workana_session=g9obh70ts9i16h2pcq7c4snh47"
BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Cookie": SESSION,
}

with httpx.Client(timeout=30, follow_redirects=True) as client:
    page = client.get(
        "https://www.workana.com/en/jobs?category=it-programming",
        headers=BASE_HEADERS,
    )
    csrf = re.search(r'name="csrf-token"\s+content="([^"]+)"', page.text)
    csrf_token = csrf.group(1) if csrf else ""

    cookies = dict(client.cookies)
    dcst = cookies.get("dcstcookieii", "")
    cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
    if SESSION.split("=")[0] not in cookie_header:
        cookie_header = f"{SESSION}; {cookie_header}" if cookie_header else SESSION

    print("cookies:", list(cookies.keys()))
    print("csrf:", csrf_token[:30], "...")
    print("dcst:", dcst[:20], "...")

    auth_url = "https://www.workana.com/notifications/channel_access"
    for channel in [
        "projects-en",
        "presence-notification-2e566604d888a6d15b3dc7e218dd598e",
    ]:
        r = client.post(
            auth_url,
            data={"socket_id": "1234.5678", "channel_name": channel},
            headers={
                "User-Agent": BASE_HEADERS["User-Agent"],
                "Cookie": cookie_header,
                "X-Requested-With": "XMLHttpRequest",
                "X-Csrf-Token": csrf_token,
                "x-dcst": dcst,
                "Accept": "application/json",
            },
        )
        print(f"\n{channel}: {r.status_code}")
        print(r.text[:400])
