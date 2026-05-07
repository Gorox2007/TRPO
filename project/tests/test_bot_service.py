from __future__ import annotations

import unittest

from stage2_bot.bot_service import TelegramBotService
from stage2_bot.db import ActionResult, MatchRecord, UserRecord


class BotServiceTests(unittest.TestCase):
    def test_prefs_rejects_removed_distance_filter(self) -> None:
        core = FakeCore()
        tg = FakeTelegramClient()
        service = TelegramBotService(tg=tg, core=core)

        service._cmd_prefs(chat_id=1000, telegram_id=100001, args="age=20-30 distance=50")

        self.assertEqual(len(tg.messages), 1)
        self.assertIn("distance больше не поддерживается", tg.messages[0][1])

    def test_like_uses_persisted_current_candidate_and_shows_contact(self) -> None:
        target_user = _make_user(2, 200002, first_name="Анна", username="anna_match")
        core = FakeCore(
            current_candidate_user_id=target_user.id,
            action_result=ActionResult(action_type="like", target=target_user, is_match=True),
        )
        tg = FakeTelegramClient()
        service = TelegramBotService(tg=tg, core=core)

        service._cmd_reaction(chat_id=1000, telegram_id=100001, action_type="like")

        self.assertEqual(core.reaction_calls, [(100001, target_user.id, "like")])
        self.assertEqual(core.cleared_for, [100001])
        self.assertEqual(len(tg.messages), 1)
        self.assertIn("@anna_match", tg.messages[0][1])
        self.assertIn("https://t.me/anna_match", tg.messages[0][1])

    def test_matches_command_shows_contacts(self) -> None:
        match_with_contact = MatchRecord(
            user=_make_user(2, 200002, first_name="Алина", username="alina"),
            created_at="2026-05-07T12:00:00+03:00",
        )
        match_without_contact = MatchRecord(
            user=_make_user(3, 200003, first_name="Мария", username=None),
            created_at="2026-05-07T13:00:00+03:00",
        )
        core = FakeCore(matches=[match_with_contact, match_without_contact])
        tg = FakeTelegramClient()
        service = TelegramBotService(tg=tg, core=core)

        service._cmd_matches(chat_id=1000, telegram_id=100001)

        self.assertEqual(len(tg.messages), 1)
        text = tg.messages[0][1]
        self.assertIn("Ваши мэтчи:", text)
        self.assertIn("@alina", text)
        self.assertIn("нет @username", text)


class FakeCore:
    def __init__(
        self,
        *,
        current_candidate_user_id: int | None = None,
        action_result: ActionResult | None = None,
        matches: list[MatchRecord] | None = None,
    ) -> None:
        self.current_candidate_user_id = current_candidate_user_id
        self.action_result = action_result
        self.matches = matches or []
        self.reaction_calls: list[tuple[int, int, str]] = []
        self.cleared_for: list[int] = []

    def get_current_candidate_user_id(self, telegram_id: int) -> int | None:
        return self.current_candidate_user_id

    def record_reaction(self, actor_telegram_id: int, target_user_id: int, action_type: str) -> ActionResult:
        self.reaction_calls.append((actor_telegram_id, target_user_id, action_type))
        assert self.action_result is not None
        return self.action_result

    def clear_current_candidate(self, telegram_id: int) -> None:
        self.cleared_for.append(telegram_id)
        self.current_candidate_user_id = None

    def list_matches(self, telegram_id: int, limit: int = 50) -> list[MatchRecord]:
        return self.matches


class FakeTelegramClient:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    def send_message(self, chat_id: int, text: str) -> None:
        self.messages.append((chat_id, text))


def _make_user(
    user_id: int,
    telegram_id: int,
    *,
    first_name: str,
    username: str | None,
) -> UserRecord:
    return UserRecord(
        id=user_id,
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=None,
        birth_date=None,
        gender=None,
        bio=None,
        city=None,
        profile_completeness=80.0,
        status="active",
        photo_count=1,
        created_at="2026-05-07T00:00:00+03:00",
        updated_at="2026-05-07T00:00:00+03:00",
    )


if __name__ == "__main__":
    unittest.main()
