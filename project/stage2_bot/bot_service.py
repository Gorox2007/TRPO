from __future__ import annotations

from typing import Any

from stage2_bot.core import DatingCoreService
from stage2_bot.db import DatabaseError
from stage2_bot.telegram_api import TelegramClient


HELP_TEXT = (
    "Команды:\n"
    "/start - регистрация\n"
    "/profile - мой профиль\n"
    "/prefs - мои предпочтения\n"
    "/next - следующий кандидат (заглушка Этапа 2)\n"
    "/like - лайк текущего кандидата (заглушка Этапа 2)\n"
    "/skip - пропуск кандидата (заглушка Этапа 2)\n"
    "/help - помощь"
)


class TelegramBotService:
    """Bot layer from Stage 1 docs."""

    def __init__(self, tg: TelegramClient, core: DatingCoreService) -> None:
        self.tg = tg
        self.core = core
        self.offset: int | None = None

    def run_forever(self) -> None:
        while True:
            updates = self.tg.get_updates(offset=self.offset)
            for update in updates:
                self.offset = int(update["update_id"]) + 1
                self._handle_update(update)

    def _handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message")
        if message is None:
            return

        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            return

        text = (message.get("text") or "").strip()
        sender = message.get("from") or {}
        telegram_id = sender.get("id")
        username = sender.get("username")
        first_name = sender.get("first_name")
        last_name = sender.get("last_name")

        if telegram_id is None:
            self.tg.send_message(chat_id, "Не удалось определить Telegram ID.")
            return

        if text.startswith("/start"):
            self._cmd_start(chat_id, int(telegram_id), username, first_name, last_name)
            return

        if text.startswith("/help"):
            self.tg.send_message(chat_id, HELP_TEXT)
            return

        if text.startswith("/profile"):
            self._cmd_profile(chat_id, int(telegram_id))
            return

        if text.startswith("/prefs"):
            self._cmd_prefs(chat_id, int(telegram_id))
            return

        if text.startswith("/next"):
            self.tg.send_message(chat_id, "Подбор кандидатов будет реализован на Этапе 3.")
            return

        if text.startswith("/like"):
            self.tg.send_message(chat_id, "Лайки будут полноценно реализованы на Этапе 3.")
            return

        if text.startswith("/skip"):
            self.tg.send_message(chat_id, "Пропуски кандидатов будут полноценно реализованы на Этапе 3.")
            return

        self.tg.send_message(chat_id, "Неизвестная команда. Используйте /help.")

    def _cmd_start(
        self,
        chat_id: int,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
    ) -> None:
        try:
            user = self.core.register_user(telegram_id, username, first_name, last_name)
            total = self.core.repo.count_users()
        except DatabaseError as exc:
            self.tg.send_message(chat_id, f"Ошибка БД: {exc}")
            return

        name = first_name or username or "пользователь"
        self.tg.send_message(
            chat_id,
            f"Привет, {name}!\n"
            "Вы зарегистрированы в боте.\n"
            f"telegram_id: {user.telegram_id}\n"
            f"Всего пользователей: {total}\n\n"
            "Этап 2: базовая функциональность готова.",
        )

    def _cmd_profile(self, chat_id: int, telegram_id: int) -> None:
        try:
            user = self.core.get_profile(telegram_id)
        except DatabaseError as exc:
            self.tg.send_message(chat_id, f"Ошибка БД: {exc}")
            return

        if user is None:
            self.tg.send_message(chat_id, "Вы еще не зарегистрированы. Нажмите /start.")
            return

        self.tg.send_message(
            chat_id,
            "Ваш профиль:\n"
            f"telegram_id: {user.telegram_id}\n"
            f"username: {user.username or '-'}\n"
            f"first_name: {user.first_name or '-'}\n"
            f"last_name: {user.last_name or '-'}\n"
            f"birth_date: {user.birth_date or '-'}\n"
            f"gender: {user.gender or '-'}\n"
            f"city: {user.city or '-'}\n"
            f"profile_completeness: {user.profile_completeness}",
        )

    def _cmd_prefs(self, chat_id: int, telegram_id: int) -> None:
        try:
            pref = self.core.get_or_create_preferences(telegram_id)
        except DatabaseError as exc:
            self.tg.send_message(chat_id, f"Ошибка БД: {exc}")
            return

        self.tg.send_message(
            chat_id,
            "Ваши предпочтения:\n"
            f"age: {pref.age_min}-{pref.age_max}\n"
            f"preferred_gender: {pref.preferred_gender}\n"
            f"preferred_city: {pref.preferred_city}\n"
            f"max_distance_km: {pref.max_distance_km}",
        )

