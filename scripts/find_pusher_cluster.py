"""Discover Pusher cluster by trying common endpoints."""
import json
import time

import websocket

KEY = "5d14500e05a938842a18"
CLUSTERS = ["mt1", "us2", "us3", "eu", "ap1", "sa1", "ap2", "ap3", "ap4"]


def try_cluster(cluster: str) -> None:
    url = (
        f"wss://ws-{cluster}.pusher.com/app/{KEY}"
        "?protocol=7&client=js&version=7.0.3&flash=false"
    )
    result = {"cluster": cluster, "ok": False}

    def on_message(_ws, message: str) -> None:
        data = json.loads(message)
        if data.get("event") == "pusher:connection_established":
            result["ok"] = True
            result["socket"] = json.loads(data["data"])["socket_id"]
            _ws.close()

    def on_error(_ws, error: Exception) -> None:
        result["error"] = str(error)

    ws = websocket.WebSocketApp(url, on_message=on_message, on_error=on_error)
    thread = __import__("threading").Thread(target=ws.run_forever, daemon=True)
    thread.start()
    thread.join(timeout=5)
    status = "OK" if result.get("ok") else result.get("error", "timeout")
    print(f"{cluster}: {status} {result.get('socket', '')}")


for cluster in CLUSTERS:
    try_cluster(cluster)
