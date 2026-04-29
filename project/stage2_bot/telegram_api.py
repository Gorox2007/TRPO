from __future__ import annotations

import json
import socket
from dataclasses import dataclass
from typing import Any
from urllib import error, request


class TelegramApiError(Exception):
    """Raised when Telegram API call fails."""


@dataclass
class TelegramClient:
    token: str
    timeout_sec: int = 25
    api_base: str = "https://api.telegram.org"

    def get_updates(self, offset: int | None = None) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"timeout": self.timeout_sec}
        if offset is not None:
            payload["offset"] = offset
        response = self._call("getUpdates", payload)
        return response.get("result", [])

    def send_message(self, chat_id: int, text: str) -> None:
        self._call(
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": text,
            },
        )

    def _call(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.api_base}/bot{self.token}/{method}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            url=url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=max(self.timeout_sec + 20, 30)) as resp:
                response = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            raw_body = exc.read().decode("utf-8", errors="replace")
            raise TelegramApiError(f"HTTP {exc.code}: {raw_body}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise TelegramApiError("request timed out") from exc
        except error.URLError as exc:
            raise TelegramApiError(f"network error: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise TelegramApiError("invalid JSON from Telegram API") from exc

        if not response.get("ok", False):
            raise TelegramApiError(str(response))
        return response
