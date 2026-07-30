from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass
from typing import Any, Callable

import websocket

from workana.http_client import WorkanaHttpClient

logger = logging.getLogger(__name__)

PUSHER_KEY = "5d14500e05a938842a18"
PUSHER_CLUSTER = "mt1"
AUTH_URL = "https://www.workana.com/notifications/channel_access"


@dataclass(slots=True)
class WorkanaSession:
    cookie: str
    csrf_token: str
    dcst_token: str
    notification_channel: str
    language: str = "en"

    @classmethod
    def from_cookie(cls, cookie: str, *, language: str = "en") -> WorkanaSession:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Cookie": cookie.strip(),
        }
        with WorkanaHttpClient(timeout=30, headers=headers) as client:
            response = client.get(
                f"https://www.workana.com/{language}/jobs?category=it-programming"
            )
            response.raise_for_status()
            if "/login" in str(response.url):
                raise ValueError("Workana session cookie is invalid or expired")

            csrf_match = re.search(
                r'name="csrf-token"\s+content="([^"]+)"',
                response.text,
            )
            channel_match = re.search(
                r'"channel":"(presence-notification-[^"]+)"',
                response.text,
            )
            if not csrf_match or not channel_match:
                raise ValueError(
                    "Could not load Workana notification settings. "
                    "Ensure you are using a freelancer session cookie."
                )

            cookies = {name: value for name, value in client.cookies.items()}
            cookie_header = cookie.strip()
            if not cookie_header.endswith(";"):
                cookie_header += ";"
            for name, value in cookies.items():
                if f"{name}=" not in cookie_header:
                    cookie_header += f" {name}={value};"

            return cls(
                cookie=cookie_header.strip(),
                csrf_token=csrf_match.group(1),
                dcst_token=cookies.get("dcstcookieii", ""),
                notification_channel=channel_match.group(1),
                language=language,
            )

    @property
    def projects_channel(self) -> str:
        return f"projects-{self.language}"

    def projects_channels(self, languages: list[str] | None = None) -> list[str]:
        langs = languages or [self.language]
        return [f"projects-{lang}" for lang in langs]

    @property
    def auth_headers(self) -> dict[str, str]:
        return {
            "Cookie": self.cookie,
            "X-Requested-With": "XMLHttpRequest",
            "X-Csrf-Token": self.csrf_token,
            "x-dcst": self.dcst_token,
            "Accept": "application/json",
        }


class WorkanaPusherClient:
    def __init__(
        self,
        session: WorkanaSession,
        *,
        languages: list[str] | None = None,
        on_project_added: Callable[[dict[str, Any]], None] | None = None,
        on_notification: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.session = session
        self.languages = languages or [session.language]
        self.project_channels = set(session.projects_channels(self.languages))
        self.on_project_added = on_project_added
        self.on_notification = on_notification
        self._socket_id: str | None = None
        self._ws: websocket.WebSocketApp | None = None
        self._thread: threading.Thread | None = None
        self._http = WorkanaHttpClient(timeout=20)
        self._running = False
        self._reconnect_delay = 3

    def start(self) -> None:
        self._running = True
        self._connect()

    def stop(self) -> None:
        self._running = False
        if self._ws is not None:
            self._ws.close()
        self._http.close()

    def wait(self) -> None:
        if self._thread is not None:
            self._thread.join()

    def _connect(self) -> None:
        url = (
            f"wss://ws-{PUSHER_CLUSTER}.pusher.com/app/{PUSHER_KEY}"
            "?protocol=7&client=js&version=7.0.3&flash=false"
        )
        self._ws = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
        )
        self._thread = threading.Thread(target=self._ws.run_forever, daemon=True)
        self._thread.start()

    def _on_open(self, _ws: websocket.WebSocketApp) -> None:
        logger.info("Pusher connected")

    def _on_close(self, _ws: websocket.WebSocketApp, status: int, msg: str) -> None:
        logger.warning("Pusher closed (%s): %s", status, msg)
        if self._running:
            logger.info("Reconnecting to Pusher in %ss", self._reconnect_delay)
            threading.Timer(self._reconnect_delay, self._connect).start()

    def _on_error(self, _ws: websocket.WebSocketApp, error: Exception) -> None:
        logger.error("Pusher error: %s", error)

    def _on_message(self, _ws: websocket.WebSocketApp, message: str) -> None:
        frame = json.loads(message)
        event = frame.get("event", "")
        channel = frame.get("channel", "")
        raw_data = frame.get("data", "{}")

        if event == "pusher:connection_established":
            self._socket_id = json.loads(raw_data)["socket_id"]
            logger.info("Pusher socket ready: %s", self._socket_id)
            for channel_name in sorted(self.project_channels):
                self._subscribe(channel_name, presence=False)
            self._subscribe(self.session.notification_channel, presence=True)
            return

        if event in {
            "pusher:subscription_succeeded",
            "pusher_internal:subscription_succeeded",
        }:
            logger.info("Subscribed to %s", channel)
            return

        if event in {"pusher:subscription_error", "pusher:error"}:
            logger.error("Pusher subscription error on %s: %s", channel, raw_data)
            return

        payload = self._parse_payload(raw_data)
        if event == "added" and channel in self.project_channels:
            lang = channel.replace("projects-", "", 1)
            payload["_language"] = lang
            logger.info("Pusher added event on %s", channel)
            if self.on_project_added:
                self.on_project_added(payload)
            return

        if event == "notification" and channel == self.session.notification_channel:
            logger.info("Pusher notification event received")
            if self.on_notification:
                self.on_notification(payload)
            return

        if event and not event.startswith("pusher"):
            logger.info("Pusher event %s on %s: %s", event, channel, str(payload)[:200])

    def _subscribe(self, channel_name: str, *, presence: bool) -> None:
        if not self._socket_id or self._ws is None:
            return

        data: dict[str, Any] = {"channel": channel_name}
        if presence or channel_name.startswith(("private-", "presence-")):
            auth_data = self._authorize(channel_name)
            data["auth"] = auth_data["auth"]
            if "channel_data" in auth_data:
                data["channel_data"] = auth_data["channel_data"]

        self._send("pusher:subscribe", data)

    def _authorize(self, channel_name: str) -> dict[str, Any]:
        response = self._http.post(
            AUTH_URL,
            data={"socket_id": self._socket_id, "channel_name": channel_name},
            headers=self.session.auth_headers,
        )
        response.raise_for_status()
        return response.json()

    def _send(self, event: str, data: dict[str, Any]) -> None:
        if self._ws is None:
            return
        self._ws.send(json.dumps({"event": event, "data": data}))

    @staticmethod
    def _parse_payload(raw_data: str | dict[str, Any]) -> dict[str, Any]:
        if isinstance(raw_data, dict):
            return raw_data
        try:
            return json.loads(raw_data)
        except json.JSONDecodeError:
            return {"raw": raw_data}
