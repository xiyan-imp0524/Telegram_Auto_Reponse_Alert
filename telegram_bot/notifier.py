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
        published = (
            str(job.published_projects)
            if job.published_projects is not None
            else "?"
        )
        paid = str(job.projects_paid) if job.projects_paid is not None else "?"

        # Telegram always wraps long lines on mobile — keep meta short on line 1,
        # put the full title alone on line 2 so it stays readable as one block.
        line1 = f"{self._escape(budget)} • {flag} {self._escape(country)}"
        line2 = f"<b>{self._escape(title)}</b>"
        line3 = (
            f"Client: <b>{self._escape(client)}</b> • "
            f"Joined Date: <b>{self._escape(joined)}</b> • "
            f"Publish: <b>{self._escape(published)}</b> • "
            f"Pay: <b>{self._escape(paid)}</b>"
        )
        line4 = f'<a href="{self._escape(job.url)}">Open link</a>'

        return f"{line1}\n\n{line2}\n\n{line3}\n\n{line4}"

    def _title_in_english(self, job: WorkanaJob) -> str:
        title = self._single_line(job.title)
        if not title:
            return "Untitled project"
        if job.language in {"", "en"} or self._looks_english(title):
            return title
        translated = self._translate_to_english(title, source=job.language or "auto")
        return self._single_line(translated or title)

    def _translate_to_english(self, text: str, *, source: str) -> str:
        try:
            langpair = "autodetect|en" if source in {"", "auto"} else f"{source}|en"
            response = httpx.get(
                "https://api.mymemory.translated.net/get",
                params={"q": text, "langpair": langpair},
                timeout=min(self.timeout, 2.5),
            )
            response.raise_for_status()
            data = response.json()
            translated = (
                data.get("responseData", {}).get("translatedText") or ""
            ).strip()
            if not translated or translated.upper().startswith("MYMEMORY WARNING"):
                return text
            return translated
        except Exception:
            return text

    @staticmethod
    def _single_line(value: str) -> str:
        return " ".join((value or "").replace("\u00a0", " ").split())

    def _send_message(self, text: str) -> None:
        url = TELEGRAM_API.format(token=self.token, method="sendMessage")
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            body = response.json()
            if not body.get("ok"):
                raise RuntimeError(f"Telegram API error: {body}")

    @staticmethod
    def _format_budget(budget: str) -> str:
        raw = (budget or "Not specified").strip()
        if raw.lower().startswith("usd"):
            return raw
        if re.search(r"\d", raw):
            return f"USD {raw}" if "usd" not in raw.lower() else raw
        return raw

    @staticmethod
    def _country_flag(country: str) -> str:
        key = (country or "").strip().lower()
        return COUNTRY_FLAGS.get(key, "🌍")

    @staticmethod
    def _looks_english(text: str) -> bool:
        lowered = text.lower()
        markers = ("á", "é", "í", "ó", "ú", "ñ", "ã", "õ", "ç", "¿", "¡")
        return not any(marker in lowered for marker in markers)

    @staticmethod
    def _escape(value: str) -> str:
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
