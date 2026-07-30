"""Subscribe to Workana Pusher channels after connection."""
import json
import re
import time

import httpx
import pysher

SESSION = "workana_session=g9obh70ts9i16h2pcq7c4snh47"
http = httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0", "Cookie": SESSION})
page = http.get("https://www.workana.com/en/jobs?category=it-programming")
csrf = re.search(r'name="csrf-token"\s+content="([^"]+)"', page.text).group(1)
cookies = dict(http.cookies)
cookie_header = "; ".join([SESSION] + [f"{k}={v}" for k, v in cookies.items()])
dcst = cookies.get("dcstcookieii", "")
notification_channel = re.search(r'"channel":"(presence-notification-[^"]+)"', page.text).group(1)

auth_headers = {
    "Cookie": cookie_header,
    "X-Requested-With": "XMLHttpRequest",
    "X-Csrf-Token": csrf,
    "x-dcst": dcst,
}

pusher = pysher.Pusher(
    "5d14500e05a938842a18",
    secure=True,
    auth_endpoint="https://www.workana.com/notifications/channel_access",
    auth_endpoint_headers=auth_headers,
)


def on_connected(_: str) -> None:
    print("connected, socket:", pusher.connection.socket_id)

    projects = pusher.subscribe("projects-en")
    projects.bind("pusher:subscription_succeeded", lambda __: print("projects-en OK"))
    projects.bind("pusher:subscription_error", lambda err: print("projects-en error", err))
    projects.bind("added", lambda data: print("ADDED", data))

    notif = pusher.subscribe(notification_channel)
    notif.bind("pusher:subscription_succeeded", lambda __: print("notifications OK"))
    notif.bind("pusher:subscription_error", lambda err: print("notifications error", err))
    notif.bind("notification", lambda data: print("NOTIF", str(data)[:500]))


pusher.connection.bind("pusher:connection_established", on_connected)
pusher.connect()
time.sleep(25)
pusher.disconnect()
