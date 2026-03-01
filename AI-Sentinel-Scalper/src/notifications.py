from __future__ import annotations

import os

import requests


def send_telegram_alert(message: str) -> bool:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": f"🤖 GEMINI_BOT ALERT\n{message}",
    }
    try:
        requests.post(url, json=payload, timeout=5)
        return True
    except Exception:
        return False
