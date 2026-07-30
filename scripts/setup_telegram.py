"""Help set up Telegram credentials for the Workana monitor."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
API = "https://api.telegram.org/bot{token}/{method}"


def prompt(label: str) -> str:
    value = input(f"{label}: ").strip()
    if not value:
        raise SystemExit("Cancelled.")
    return value


def call_api(token: str, method: str, **params: object) -> dict:
    response = httpx.get(
        API.format(token=token, method=method),
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    if not body.get("ok"):
        raise RuntimeError(f"Telegram API error: {body}")
    return body


def update_env(token: str, chat_id: str) -> None:
    lines: list[str] = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    values = {
        "TELEGRAM_BOT_TOKEN": token,
        "TELEGRAM_CHAT_ID": chat_id,
    }
    seen: set[str] = set()

    for index, line in enumerate(lines):
        for key, value in values.items():
            if line.startswith(f"{key}="):
                lines[index] = f"{key}={value}"
                seen.add(key)

    for key, value in values.items():
        if key not in seen:
            lines.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    print("Telegram setup for Workana monitor\n")

    token = prompt("Paste your bot token from @BotFather")
    me = call_api(token, "getMe")["result"]
    print(f"Bot OK: @{me['username']} ({me['first_name']})")

    print(
        "\n1. Open Telegram and search for your bot\n"
        f"2. Start a chat and send any message (for example: hello)\n"
        "3. Press Enter here after you have sent the message"
    )
    input()

    updates = call_api(token, "getUpdates")["result"]
    if not updates:
        print(
            "No messages found yet. Send a message to your bot and run this script again.",
            file=sys.stderr,
        )
        return 1

    chat = updates[-1]["message"]["chat"]
    chat_id = str(chat["id"])
    chat_name = chat.get("username") or chat.get("first_name") or chat_id
    print(f"Chat found: {chat_name} (id={chat_id})")

    test = httpx.post(
        API.format(token=token, method="sendMessage"),
        json={
            "chat_id": chat_id,
            "text": "Workana monitor connected. You will receive new job alerts here.",
        },
        timeout=30,
    )
    test.raise_for_status()
    print("Test message sent.")

    update_env(token, chat_id)
    print(f"Saved TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to {ENV_PATH}")
    print("\nNext step: python main.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
