"""Pusher test with auth after connection established."""
from __future__ import annotations

import json
import re
import threading
import time

import httpx
import pysher

SESSION = "workana_session=g9obh70ts9i16h2pcq7c4snh47"
PUSHER_KEY = "5d14500e05a938842a18"
AUTH_URL = "https://www.workana.com/notifications/channel_access"

http = httpx.Client(
    timeout=30,
    follow_redirects=True,
    headers={"User-Agent": "Mozilla/5.0", "Cookie": SESSION},
)
page = http.get("https://www.workana.com/en/jobs?category=it-programming")
csrf = re.search(r'name="csrf-token"\s+content="([^"]+)"', page.text).group(1)
cookies = dict(http.cookies)
cookie_header = "; ".join([SESSION] + [f"{k}={v}" for k, v in cookies.items()])
dcst = cookies.get("dcstcookieii", "")
notification_channel = re.search(
    r'"channel":"(presence-notification-[^"]+)"',
    page.text,
).group(1)

auth_headers = {
    "Cookie": cookie_header,
    "X-Requested-With": "XMLHttpRequest",
    "X-Csrf-Token": csrf,
    "x-dcst": dcst,
    "Accept": "application/json",
}

pusher = pysher.Pusher(PUSHER_KEY, secure=True)
done = threading.Event()


def authenticate(socket_id: str, channel_name: str) -> dict:
    response = http.post(
        AUTH_URL,
        data={"socket_id": socket_id, "channel_name": channel_name},
        headers=auth_headers,
    )
    print(f"auth {channel_name}: {response.status_code}")
    if response.status_code != 200:
        print(response.text[:200])
        raise RuntimeError(f"Auth failed for {channel_name}")
    return response.json()


def on_connected(_data: str) -> None:
    socket_id = pusher.connection.socket_id
    print("socket_id", socket_id)

    for channel_name in ["projects-en", notification_channel]:
        try:
            if channel_name.startswith("presence-"):
                auth_data = authenticate(socket_id, channel_name)
                channel = pysher.channel.Channel(
                    channel_name,
                    pusher.connection,
                    auth=auth_data["auth"],
                    channel_data=auth_data.get("channel_data"),
                )
            else:
                try:
                    auth_data = authenticate(socket_id, channel_name)
                    channel = pysher.channel.Channel(
                        channel_name,
                        pusher.connection,
                        auth=auth_data.get("auth"),
                    )
                except RuntimeError:
                    channel = pusher.subscribe(channel_name)
                    print(f"subscribed public {channel_name}")
                    channel = channel
                    continue

            pusher.channels[channel_name] = channel
            channel.subscribe()
            print(f"subscribed {channel_name}")

            def bind_added(event: str, data: str, ch=channel) -> None:
                ch.bind("added", lambda d: print("ADDED", d))
                ch.bind("notification", lambda d: print("NOTIFICATION", d[:400]))
                ch.bind("pusher:subscription_succeeded", lambda _: print(f"{channel_name} ready"))

            bind_added("x", "y")
        except Exception as exc:
            print(f"failed {channel_name}: {exc}")

    done.set()


pusher.connection.bind("pusher:connection_established", on_connected)
print("connecting...")
pusher.connect()
done.wait(timeout=10)
print("listening 25s")
time.sleep(25)
pusher.disconnect()
