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

