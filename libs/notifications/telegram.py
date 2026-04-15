from __future__ import annotations

from typing import Any

import httpx

from libs.utils.config import settings


class TelegramBotClient:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            base_url=settings.telegram_api_base_url.rstrip("/"),
            timeout=10.0,
        )

    def send_message(
        self,
        *,
        token: str,
        chat_id: str,
        text: str,
        parse_mode: str,
        disable_web_page_preview: bool,
    ) -> dict[str, Any]:
        response = self._client.post(
            f"/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": disable_web_page_preview,
            },
        )
        response.raise_for_status()
        return response.json()
