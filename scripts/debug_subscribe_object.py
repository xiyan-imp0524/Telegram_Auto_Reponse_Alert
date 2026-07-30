import json
import re
import threading
import time

import httpx
import websocket

SESSION = "workana_session=g9obh70ts9i16h2pcq7c4snh47"
KEY = "5d14500e05a938842a18"
http = httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0", "Cookie": SESSION})
page = http.get("https://www.workana.com/en/jobs?category=it-programming")
csrf = re.search(r'name="csrf-token"\s+content="([^"]+)"', page.text).group(1)
cookies = dict(http.cookies)
cookie = "; ".join([SESSION] + [f"{k}={v}" for k, v in cookies.items()])
dcst = cookies.get("dcstcookieii", "")
notif = re.search(r'"channel":"(presence-notification-[^"]+)"', page.text).group(1)
headers = {
    "Cookie": cookie,
    "X-Requested-With": "XMLHttpRequest",
    "X-Csrf-Token": csrf,
    "x-dcst": dcst,
    "Accept": "application/json",
}


def on_message(ws, msg: str) -> None:
    frame = json.loads(msg)
    print("RECV", frame.get("event"), str(frame)[:220])
    if frame.get("event") == "pusher:connection_established":
        sid = json.loads(frame["data"])["socket_id"]
        auth = http.post(
            "https://www.workana.com/notifications/channel_access",
            data={"socket_id": sid, "channel_name": notif},
            headers=headers,
        ).json()
        payload = {
            "channel": notif,
            "auth": auth["auth"],
            "channel_data": auth["channel_data"],
        }
        ws.send(json.dumps({"event": "pusher:subscribe", "data": payload}))
        print("SENT with object data")


ws = websocket.WebSocketApp(
    f"wss://ws-mt1.pusher.com/app/{KEY}?protocol=7&client=js&version=7.0.3&flash=false",
    on_message=on_message,
)
threading.Thread(target=ws.run_forever, daemon=True).start()
time.sleep(8)
ws.close()
