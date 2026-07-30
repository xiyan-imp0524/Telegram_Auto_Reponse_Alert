import json
import threading
import time

import websocket

KEY = "5d14500e05a938842a18"


def on_message(ws, msg: str) -> None:
    frame = json.loads(msg)
    print("RECV", frame.get("event"), frame.get("channel", ""), str(frame)[:200])
    if frame.get("event") == "pusher:connection_established":
        ws.send(
            json.dumps(
                {
                    "event": "pusher:subscribe",
                    "data": {"channel": "projects-en"},
                }
            )
        )
        print("subscribed projects-en")


ws = websocket.WebSocketApp(
    f"wss://ws-mt1.pusher.com/app/{KEY}?protocol=7&client=js&version=7.0.3&flash=false",
    on_message=on_message,
)
threading.Thread(target=ws.run_forever, daemon=True).start()
time.sleep(8)
ws.close()
