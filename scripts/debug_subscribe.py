"""Debug Pusher subscribe message format."""
import json
import re
import time

import httpx
import websocket

SESSION = "workana_session=g9obh70ts9i16h2pcq7c4snh47"
KEY = "5d14500e05a938842a18"
AUTH_URL = "https://www.workana.com/notifications/channel_access"

http = httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0", "Cookie": SESSION})
page = http.get("https://www.workana.com/en/jobs?category=it-programming")
csrf = re.search(r'name="csrf-token"\s+content="([^"]+)"', page.text).group(1)
cookies = dict(http.cookies)
cookie_header = "; ".join([SESSION] + [f"{k}={v}" for k, v in cookies.items()])
dcst = cookies.get("dcstcookieii", "")
notif_channel = re.search(r'"channel":"(presence-notification-[^"]+)"', page.text).group(1)
auth_headers = {
    "Cookie": cookie_header,
    "X-Requested-With": "XMLHttpRequest",
    "X-Csrf-Token": csrf,
    "x-dcst": dcst,
    "Accept": "application/json",
}

socket_id = {"value": None}


def subscribe(ws, channel: str, *, auth: dict | None = None) -> None:
    payload = {"channel": channel}
    if auth:
        payload["auth"] = auth["auth"]
        if "channel_data" in auth:
            payload["channel_data"] = auth["channel_data"]
    msg = {"event": "pusher:subscribe", "data": json.dumps(payload)}
    print("SEND", msg)
    ws.send(json.dumps(msg))


def on_message(ws, message):
    frame = json.loads(message)
    print("RECV", frame)
    event = frame.get("event")
    if event == "pusher:connection_established":
        socket_id["value"] = json.loads(frame["data"])["socket_id"]
        for channel in ["projects-en", notif_channel]:
            auth = None
            if channel.startswith("presence-"):
                r = http.post(
                    AUTH_URL,
                    data={"socket_id": socket_id["value"], "channel_name": channel},
                    headers=auth_headers,
                )
                print("AUTH", channel, r.status_code, r.text[:160])
                auth = r.json() if r.status_code == 200 and r.text.startswith("{") else None
            else:
                r = http.post(
                    AUTH_URL,
                    data={"socket_id": socket_id["value"], "channel_name": channel},
                    headers=auth_headers,
                )
                print("AUTH try", channel, r.status_code, r.text[:160])
            subscribe(ws, channel, auth=auth)


ws = websocket.WebSocketApp(
    f"wss://ws-mt1.pusher.com/app/{KEY}?protocol=7&client=js&version=7.0.3&flash=false",
    on_message=on_message,
)
import threading

threading.Thread(target=ws.run_forever, daemon=True).start()
time.sleep(12)
ws.close()
