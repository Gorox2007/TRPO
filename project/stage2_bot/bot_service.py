from __future__ import annotations

import shlex
import sys
import time
from typing import Any

from .core import CandidateRecommendation, DatingCoreService
from .db import DatabaseError, PhotoRecord, UserRecord
from .telegram_api import TelegramApiError, TelegramClient


HELP_TEXT = (
    "Команды:\n"
    "/start - регистрация\n"
    "/profile - посмотреть анкету\n"
    "/profile_set birth_date=2000-01-31 gender=female city=Москва bio=\"Люблю кофе\" - создать/обновить анкету\n"
    "/profile_delete - удалить анкету\n"
    "/prefs - посмотреть предпочтения\n"
    "/prefs age=18-35 gender=any city=any distance=50 - обновить предпочтения\n"
    "/next - следующий кандидат по рейтингу\n"
    "/like - лайк текущего кандидата\n"
    "/skip - пропуск текущего кандидата\n"
    "/photo_add file_id=... unique_id=... - добавить фото вручную\n"
    "Можно также отправить фото в чат, и бот добавит его в анкету."
)


class TelegramBotService:
    def __init__(self, tg: TelegramClient, core: DatingCoreService) -> None:
        self.tg = tg
        self.core = core
        self.offset: int | None = None
        self.current_candidates: dict[int, int] = {}

    def run_forever(self) -> None:
        while True:
            try:
                updates = self.tg.get_updates(offset=self.offset)
            except TelegramApiError as exc:
                if not exc.retriable:
                    raise
                print(f"Telegram polling warning: {exc}. Retrying in 3 seconds.", file=sys.stderr)
                time.sleep(3)
                continue

            for update in updates:
                self.offset = int(update["update_id"]) + 1
                try:
                    self._handle_update(update)
                except TelegramApiError as exc:
                    print(f"Telegram response warning: {exc}. Update skipped.", file=sys.stderr)

    def _handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message")
        if message is None:
            return

        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            return

        sender = message.get("from") or {}
        telegram_id = sender.get("id")
        username = sender.get("username")
        first_name = sender.get("first_name")
        last_name = sender.get("last_name")

        if telegram_id is None:
            self.tg.send_message(chat_id, "Не удалось определить Telegram ID.")
            return

        if message.get("photo"):
            self._cmd_photo(chat_id, int(telegram_id), message["photo"])
            return

        text = (message.get("text") or "").strip()

        if text.startswith("/start"):
            self._cmd_start(chat_id, int(telegram_id), username, first_name, last_name)
            return

        if text.startswith("/help"):
            self.tg.send_message(chat_id, HELP_TEXT)
            return

        if text.startswith("/profile_set"):
            self._cmd_profile_set(chat_id, int(telegram_id), _command_args(text))
            return

        if text.startswith("/profile_delete"):
            self._cmd_profile_delete(chat_id, int(telegram_id))
            return

        if text.startswith("/profile"):
            self._cmd_profile(chat_id, int(telegram_id))
            return

        if text.startswith("/prefs"):
            self._cmd_prefs(chat_id, int(telegram_id), _command_args(text))
            return

        if text.startswith("/photo_add"):
            self._cmd_photo_add(chat_id, int(telegram_id), _command_args(text))
            return

        if text.startswith("/next"):
            self._cmd_next(chat_id, int(telegram_id))
            return

        if text.startswith("/like"):
            self._cmd_reaction(chat_id, int(telegram_id), "like")
            return

        if text.startswith("/skip"):
            self._cmd_reaction(chat_id, int(telegram_id), "skip")
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
            "Этап 3: анкеты, рейтинг и подбор кандидатов доступны. Используйте /help.",
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

        self._send_profile_card(chat_id, user)

    def _cmd_profile_set(self, chat_id: int, telegram_id: int, args: str) -> None:
        try:
            fields = _parse_key_values(args)
            user = self.core.update_profile(
                telegram_id=telegram_id,
                birth_date=fields.get("birth_date"),
                gender=fields.get("gender"),
                city=fields.get("city"),
                bio=fields.get("bio"),
            )
        except (DatabaseError, ValueError) as exc:
            self.tg.send_message(chat_id, f"Не удалось сохранить анкету: {exc}")
            return

        self._send_profile_card(chat_id, user, prefix="Анкета сохранена.\n\n")

    def _cmd_profile_delete(self, chat_id: int, telegram_id: int) -> None:
        try:
            deleted = self.core.delete_profile(telegram_id)
        except DatabaseError as exc:
            self.tg.send_message(chat_id, f"Ошибка БД: {exc}")
            return

        self.current_candidates.pop(telegram_id, None)
        if deleted:
            self.tg.send_message(chat_id, "Анкета удалена. Чтобы создать новую, отправьте /start.")
        else:
            self.tg.send_message(chat_id, "Анкета не найдена. Для регистрации отправьте /start.")

    def _cmd_prefs(self, chat_id: int, telegram_id: int, args: str) -> None:
        try:
            if args.strip():
                fields = _parse_key_values(args)
                age_min, age_max = _parse_age_range(fields.get("age"))
                pref = self.core.update_preferences(
                    telegram_id=telegram_id,
                    age_min=_optional_int(fields.get("age_min")) or age_min,
                    age_max=_optional_int(fields.get("age_max")) or age_max,
                    preferred_gender=fields.get("gender") or fields.get("preferred_gender"),
                    preferred_city=fields.get("city") or fields.get("preferred_city"),
                    max_distance_km=_optional_int(fields.get("distance") or fields.get("max_distance_km")),
                )
                prefix = "Предпочтения обновлены:\n"
            else:
                pref = self.core.get_or_create_preferences(telegram_id)
                prefix = "Ваши предпочтения:\n"
        except (DatabaseError, ValueError) as exc:
            self.tg.send_message(chat_id, f"Не удалось обработать предпочтения: {exc}")
            return

        self.tg.send_message(
            chat_id,
            prefix
            + f"age: {pref.age_min}-{pref.age_max}\n"
            + f"preferred_gender: {pref.preferred_gender}\n"
            + f"preferred_city: {pref.preferred_city}\n"
            + f"max_distance_km: {pref.max_distance_km}",
        )

    def _cmd_photo(self, chat_id: int, telegram_id: int, photos: list[dict[str, Any]]) -> None:
        best_photo = photos[-1]
        try:
            photo = self.core.add_photo(
                telegram_id=telegram_id,
                telegram_file_id=str(best_photo["file_id"]),
                telegram_file_unique_id=str(best_photo["file_unique_id"]),
            )
        except (DatabaseError, ValueError, KeyError) as exc:
            self.tg.send_message(chat_id, f"Не удалось добавить фото: {exc}")
            return
        self.tg.send_message(chat_id, f"Фото добавлено в анкету, позиция: {photo.position}.")

    def _cmd_photo_add(self, chat_id: int, telegram_id: int, args: str) -> None:
        try:
            fields = _parse_key_values(args)
            photo = self.core.add_photo(
                telegram_id=telegram_id,
                telegram_file_id=fields["file_id"],
                telegram_file_unique_id=fields["unique_id"],
                position=_optional_int(fields.get("position")),
                is_primary=_parse_bool(fields.get("primary")),
            )
        except (DatabaseError, ValueError, KeyError) as exc:
            self.tg.send_message(chat_id, f"Не удалось добавить фото: {exc}")
            return
        self.tg.send_message(chat_id, f"Фото добавлено в анкету, позиция: {photo.position}.")

    def _cmd_next(self, chat_id: int, telegram_id: int) -> None:
        try:
            profile = self.core.get_profile(telegram_id)
            if profile is None:
                self.tg.send_message(chat_id, "Сначала зарегистрируйтесь через /start.")
                return
            candidate = self.core.get_next_candidate(telegram_id)
        except DatabaseError as exc:
            self.tg.send_message(chat_id, f"Ошибка БД: {exc}")
            return

        if candidate is None:
            self.current_candidates.pop(telegram_id, None)
            self.tg.send_message(chat_id, "Подходящих кандидатов пока нет. Попробуйте позже или расширьте /prefs.")
            return

        self.current_candidates[telegram_id] = candidate.user.id
        self._send_candidate_card(chat_id, candidate)

    def _cmd_reaction(self, chat_id: int, telegram_id: int, action_type: str) -> None:
        target_user_id = self.current_candidates.get(telegram_id)
        if target_user_id is None:
            self.tg.send_message(chat_id, "Сначала получите кандидата командой /next.")
            return

        try:
            result = self.core.record_reaction(telegram_id, target_user_id, action_type)
        except DatabaseError as exc:
            self.tg.send_message(chat_id, f"Ошибка БД: {exc}")
            return

        self.current_candidates.pop(telegram_id, None)
        if result.is_match:
            name = _display_name(result.target)
            self.tg.send_message(chat_id, f"Это взаимный лайк с {name}! Можно начинать общение.")
            return
        if action_type == "like":
            self.tg.send_message(chat_id, "Лайк сохранен. Используйте /next для следующего кандидата.")
        else:
            self.tg.send_message(chat_id, "Кандидат пропущен. Используйте /next для следующего кандидата.")

    def _send_profile_card(self, chat_id: int, user: UserRecord, prefix: str = "") -> None:
        text = prefix + _format_profile(user)
        photos = self.core.list_photos_for_user_id(user.id)
        if not photos:
            self.tg.send_message(chat_id, text)
            return

        try:
            self._send_photos(chat_id, photos, text)
        except TelegramApiError:
            self.tg.send_message(chat_id, text)

    def _send_candidate_card(self, chat_id: int, candidate: CandidateRecommendation) -> None:
        text = _format_candidate(candidate)
        photos = self.core.list_photos_for_user_id(candidate.user.id)
        if not photos:
            self.tg.send_message(chat_id, text)
            return

        try:
            self._send_photos(chat_id, photos, text)
        except TelegramApiError:
            self.tg.send_message(chat_id, text)

    def _send_photos(self, chat_id: int, photos: list[PhotoRecord], caption: str) -> None:
        if len(photos) == 1:
            self.tg.send_photo(chat_id, photos[0].telegram_file_id, caption=caption)
            return
        try:
            self._send_photo_album(chat_id, photos, caption)
        except TelegramApiError:
            self._send_photo_series(chat_id, photos, caption)

    def _send_photo_album(self, chat_id: int, photos: list[PhotoRecord], caption: str) -> None:
        media: list[dict[str, Any]] = []
        for index, photo in enumerate(photos):
            item: dict[str, Any] = {
                "type": "photo",
                "media": photo.telegram_file_id,
            }
            if index == 0:
                item["caption"] = caption
            media.append(item)
        self.tg.send_media_group(chat_id, media)

    def _send_photo_series(self, chat_id: int, photos: list[PhotoRecord], caption: str) -> None:
        self.tg.send_photo(chat_id, photos[0].telegram_file_id, caption=caption)
        for photo in photos[1:]:
            time.sleep(0.2)
            self.tg.send_photo(chat_id, photo.telegram_file_id)


def _format_profile(user: UserRecord) -> str:
    return (
        "Ваша анкета:\n"
        f"name: {_display_name(user)}\n"
        f"username: {user.username or '-'}\n"
        f"birth_date: {user.birth_date or '-'}\n"
        f"gender: {user.gender or '-'}\n"
        f"city: {user.city or '-'}\n"
        f"bio: {user.bio or '-'}\n"
        f"photos: {user.photo_count}\n"
        f"profile_completeness: {user.profile_completeness:.0f}%"
    )


def _format_candidate(candidate: CandidateRecommendation) -> str:
    user = candidate.user
    return (
        "Кандидат:\n"
        f"name: {_display_name(user)}\n"
        f"age: {_age_or_dash(user.birth_date)}\n"
        f"gender: {user.gender or '-'}\n"
        f"city: {user.city or '-'}\n"
        f"bio: {user.bio or '-'}\n"
        f"photos: {user.photo_count}\n\n"
        f"score: {candidate.score:.2f}\n"
        f"primary: {candidate.primary_score:.2f}, behavior: {candidate.behavioral_score:.2f}\n\n"
        "Ответьте /like или /skip."
    )


def _display_name(user: UserRecord) -> str:
    parts = [part for part in [user.first_name, user.last_name] if part]
    if parts:
        return " ".join(parts)
    return user.username or f"user_{user.telegram_id}"


def _age_or_dash(birth_date: str | None) -> str:
    if birth_date is None:
        return "-"
    from .core import _age_from_birth_date

    age = _age_from_birth_date(birth_date)
    return "-" if age is None else str(age)


def _command_args(text: str) -> str:
    parts = text.split(maxsplit=1)
    return "" if len(parts) == 1 else parts[1]


def _parse_key_values(args: str) -> dict[str, str]:
    if not args.strip():
        return {}
    result: dict[str, str] = {}
    for token in shlex.split(args):
        if "=" not in token:
            raise ValueError(f"expected key=value, got {token!r}")
        key, value = token.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def _parse_age_range(raw: str | None) -> tuple[int | None, int | None]:
    if raw is None:
        return None, None
    if "-" not in raw:
        raise ValueError("age must use MIN-MAX format, for example age=18-35")
    left, right = raw.split("-", 1)
    return int(left), int(right)


def _optional_int(raw: str | None) -> int | None:
    if raw in {None, ""}:
        return None
    return int(raw)


def _parse_bool(raw: str | None) -> bool:
    if raw is None:
        return False
    return raw.casefold() in {"1", "true", "yes", "да"}

