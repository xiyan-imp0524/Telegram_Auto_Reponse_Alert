"""Live test: connect to Workana Pusher channels."""
from __future__ import annotations

import json
import re
import time

import httpx
import pysher

SESSION = "workana_session=g9obh70ts9i16h2pcq7c4snh47"
PUSHER_KEY = "5d14500e05a938842a18"
AUTH_URL = "https://www.workana.com/notifications/channel_access"

client = httpx.Client(
    timeout=30,
    follow_redirects=True,
    headers={"User-Agent": "Mozilla/5.0", "Cookie": SESSION},
)
page = client.get("https://www.workana.com/en/jobs?category=it-programming")
csrf = re.search(r'name="csrf-token"\s+content="([^"]+)"', page.text)
csrf_token = csrf.group(1) if csrf else ""
cookies = dict(client.cookies)
cookie_header = "; ".join([SESSION] + [f"{k}={v}" for k, v in cookies.items()])
dcst = cookies.get("dcstcookieii", "")

notif_match = re.search(
    r'"channel":"(presence-notification-[^"]+)"',
    page.text,
)
if not notif_match:
    raise RuntimeError("Could not find notification channel in page")
notification_channel = notif_match.group(1)
print("notification channel:", notification_channel)


def pusher_auth(socket_id: str, channel_name: str) -> dict:
    response = client.post(
        AUTH_URL,
        data={"socket_id": socket_id, "channel_name": channel_name},
        headers={
            "Cookie": cookie_header,
            "X-Requested-With": "XMLHttpRequest",
            "X-Csrf-Token": csrf_token,
            "x-dcst": dcst,
            "Accept": "application/json",
        },
    )
    print(f"auth {channel_name}: {response.status_code} {response.text[:120]}")
    return response.json()


pusher = pysher.Pusher(
    PUSHER_KEY,
    secure=True,
    auth_endpoint=AUTH_URL,
    auth_endpoint_headers={
        "Cookie": cookie_header,
        "X-Requested-With": "XMLHttpRequest",
        "X-Csrf-Token": csrf_token,
        "x-dcst": dcst,
    },
)

pusher.connection.bind(
    "pusher:connection_established",
    lambda data: print("connected", data),
)

projects = pusher.subscribe("projects-en")
projects.bind("pusher:subscription_succeeded", lambda _: print("projects-en subscribed"))
projects.bind("added", lambda event: print("PROJECT ADDED:", event))

notif = pusher.subscribe(notification_channel)
notif.bind("pusher:subscription_succeeded", lambda _: print("notification subscribed"))
notif.bind("notification", lambda event: print("NOTIFICATION:", event[:500] if isinstance(event, str) else event))

print("Connecting for 15 seconds...")
pusher.connect()
time.sleep(15)
pusher.disconnect()
print("done")
