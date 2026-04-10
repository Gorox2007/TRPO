from __future__ import annotations

from stage2_bot.db import PostgresRepository, PreferenceRecord, UserRecord


class DatingCoreService:
    """Core layer from Stage 1 docs."""

    def __init__(self, repo: PostgresRepository) -> None:
        self.repo = repo

    def register_user(self, telegram_id: int, username: str | None, first_name: str | None, last_name: str | None) -> UserRecord:
        return self.repo.register_or_update_user(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )

    def get_profile(self, telegram_id: int) -> UserRecord | None:
        return self.repo.get_user_by_telegram_id(telegram_id)

    def get_or_create_preferences(self, telegram_id: int) -> PreferenceRecord:
        return self.repo.ensure_default_preferences(telegram_id)

