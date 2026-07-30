from __future__ import annotations

import re

import httpx

from workana.models import WorkanaJob

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"

COUNTRY_FLAGS: dict[str, str] = {
    "argentina": "🇦🇷",
    "brazil": "🇧🇷",
    "brasil": "🇧🇷",
    "mexico": "🇲🇽",
    "méxico": "🇲🇽",
    "colombia": "🇨🇴",
    "chile": "🇨🇱",
    "peru": "🇵🇪",
    "perú": "🇵🇪",
    "uruguay": "🇺🇾",
    "paraguay": "🇵🇾",
    "bolivia": "🇧🇴",
    "ecuador": "🇪🇨",
    "venezuela": "🇻🇪",
    "spain": "🇪🇸",
    "españa": "🇪🇸",
    "portugal": "🇵🇹",
    "united states": "🇺🇸",
    "usa": "🇺🇸",
    "canada": "🇨🇦",
    "united kingdom": "🇬🇧",
    "uk": "🇬🇧",
    "germany": "🇩🇪",
    "france": "🇫🇷",
    "italy": "🇮🇹",
    "india": "🇮🇳",
    "bangladesh": "🇧🇩",
    "pakistan": "🇵🇰",
    "china": "🇨🇳",
    "japan": "🇯🇵",
    "south korea": "🇰🇷",
    "australia": "🇦🇺",
    "new zealand": "🇳🇿",
    "botswana": "🇧🇼",
    "south africa": "🇿🇦",
    "nigeria": "🇳🇬",
    "philippines": "🇵🇭",
    "indonesia": "🇮🇩",
    "vietnam": "🇻🇳",
    "thailand": "🇹🇭",
    "turkey": "🇹🇷",
    "russia": "🇷🇺",
    "ukraine": "🇺🇦",
    "poland": "🇵🇱",
    "netherlands": "🇳🇱",
    "belgium": "🇧🇪",
    "switzerland": "🇨🇭",
    "austria": "🇦🇹",
    "costa rica": "🇨🇷",
    "panama": "🇵🇦",
    "guatemala": "🇬🇹",
    "honduras": "🇭🇳",
    "el salvador": "🇸🇻",
    "nicaragua": "🇳🇮",
    "dominican republic": "🇩🇴",
    "cuba": "🇨🇺",
    "puerto rico": "🇵🇷",
}


class TelegramNotifier:
    def __init__(self, *, token: str, chat_id: str, timeout: float = 30.0) -> None:
        self.token = token
        self.chat_id = chat_id
        self.timeout = timeout

    def send_job(self, job: WorkanaJob) -> None:
        self._send_message(self.format_job(job))

    def send_text(self, text: str) -> None:
        self._send_message(text)

    def format_job(self, job: WorkanaJob) -> str:
        budget = self._format_budget(job.budget)
        flag = self._country_flag(job.country)
        country = job.country.strip() or "Unknown"
        title = self._single_line(self._title_in_english(job))
        client = job.author_name.strip() or "Unknown"
        joined = job.member_since or job.member_year or "Unknown"
