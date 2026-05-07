from __future__ import annotations

import http.client
import json
import socket
from dataclasses import dataclass
from typing import Any
from urllib import error, request


class TelegramApiError(Exception):
    """Raised when Telegram API call fails."""

    def __init__(self, message: str, *, status_code: int | None = None, retriable: bool = True) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retriable = retriable


@dataclass
class TelegramClient:
    token: str
    timeout_sec: int = 25
    api_base: str = "https://api.telegram.org"

    def get_me(self) -> dict[str, Any]:
        response = self._call("getMe", {}, request_timeout=10)
        return response.get("result", {})

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

    def send_photo(self, chat_id: int, photo: str, caption: str | None = None) -> None:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "photo": photo,
        }
        if caption is not None:
            payload["caption"] = caption
        self._call("sendPhoto", payload)

    def send_media_group(self, chat_id: int, media: list[dict[str, Any]]) -> None:
        self._call(
            "sendMediaGroup",
            {
                "chat_id": chat_id,
                "media": media,
            },
        )

    def _call(
        self,
        method: str,
        payload: dict[str, Any],
        request_timeout: int | None = None,
    ) -> dict[str, Any]:
        url = f"{self.api_base}/bot{self.token}/{method}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            url=url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        timeout = request_timeout if request_timeout is not None else max(self.timeout_sec + 20, 30)
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                response = json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            raw_body = exc.read().decode("utf-8", errors="replace")
            retriable = exc.code in {408, 409, 425, 429, 500, 502, 503, 504}
            raise TelegramApiError(
                f"HTTP {exc.code}: {raw_body}",
                status_code=exc.code,
                retriable=retriable,
            ) from exc
        except (TimeoutError, socket.timeout) as exc:
            raise TelegramApiError("request timed out", retriable=True) from exc
        except (
            http.client.RemoteDisconnected,
            ConnectionResetError,
            ConnectionAbortedError,
            BrokenPipeError,
        ) as exc:
            raise TelegramApiError(f"connection dropped: {exc}", retriable=True) from exc
        except error.URLError as exc:
            raise TelegramApiError(f"network error: {exc.reason}", retriable=True) from exc
        except json.JSONDecodeError as exc:
            raise TelegramApiError("invalid JSON from Telegram API", retriable=False) from exc

        if not response.get("ok", False):
            error_code = response.get("error_code")
            retriable = error_code in {408, 409, 425, 429, 500, 502, 503, 504}
            raise TelegramApiError(str(response), status_code=error_code, retriable=retriable)
        return response
