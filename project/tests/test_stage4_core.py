from __future__ import annotations

import unittest
from datetime import date

from stage2_bot.cache import RecommendationCache
from stage2_bot.core import DatingCoreService
from stage2_bot.db import CandidateStats, PreferenceRecord, UserRecord


class Stage4CoreTests(unittest.TestCase):
    def test_rank_candidates_orders_by_score(self) -> None:
        viewer = _make_user(1, 100001, city="Москва", gender="male", birth_date=_birth_date_for_age(28))
        stronger = _make_user(
            2,
            100002,
            first_name="Анна",
            city="Москва",
            gender="female",
            birth_date=_birth_date_for_age(27),
            profile_completeness=100.0,
            photo_count=4,
        )
        weaker = _make_user(
            3,
            100003,
            first_name="Ева",
            city="Казань",
            gender="female",
            birth_date=_birth_date_for_age(37),
            profile_completeness=60.0,
            photo_count=1,
        )
        repo = FakeRepository(
            users=[viewer, stronger, weaker],
            preferences={
                viewer.telegram_id: PreferenceRecord(24, 30, "female", "Москва"),
            },
            candidates={
                viewer.id: [
                    CandidateStats(user=stronger, likes_received=8, skips_received=2, matches_count=3),
                    CandidateStats(user=weaker, likes_received=1, skips_received=4, matches_count=0),
                ]
            },
        )
        service = DatingCoreService(repo=repo, cache=RecommendationCache(), recommendation_batch_size=2)

        ranked = service.rank_candidates(viewer.telegram_id)

        self.assertEqual([item.user.id for item in ranked], [stronger.id, weaker.id])
        self.assertGreater(ranked[0].score, ranked[1].score)
        self.assertGreater(ranked[0].primary_score, ranked[1].primary_score)

    def test_rank_candidates_limit_returns_only_top_n(self) -> None:
        viewer = _make_user(1, 200001, city="Москва", gender="male", birth_date=_birth_date_for_age(29))
        candidate_a = _make_user(
            2,
            200002,
            first_name="Алина",
            city="Москва",
            gender="female",
            birth_date=_birth_date_for_age(26),
            profile_completeness=100.0,
            photo_count=4,
        )
        candidate_b = _make_user(
            3,
            200003,
            first_name="Мария",
            city="Москва",
            gender="female",
            birth_date=_birth_date_for_age(31),
            profile_completeness=85.0,
            photo_count=2,
        )
        repo = FakeRepository(
            users=[viewer, candidate_a, candidate_b],
            preferences={
                viewer.telegram_id: PreferenceRecord(23, 32, "female", "Москва"),
            },
            candidates={
                viewer.id: [
                    CandidateStats(user=candidate_a, likes_received=6, skips_received=1, matches_count=2),
                    CandidateStats(user=candidate_b, likes_received=2, skips_received=1, matches_count=1),
                ]
            },
        )
        service = DatingCoreService(repo=repo, cache=RecommendationCache(), recommendation_batch_size=1)

        ranked = service.rank_candidates(viewer.telegram_id, limit=1)

        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].user.id, candidate_a.id)

    def test_get_next_candidate_uses_precached_batch(self) -> None:
        viewer = _make_user(1, 300001, city="Москва", gender="male", birth_date=_birth_date_for_age(28))
        candidate_a = _make_user(
            2,
            300002,
            first_name="Лиза",
            city="Москва",
            gender="female",
            birth_date=_birth_date_for_age(25),
            profile_completeness=100.0,
            photo_count=3,
        )
        candidate_b = _make_user(
            3,
            300003,
            first_name="Нина",
            city="Москва",
            gender="female",
            birth_date=_birth_date_for_age(27),
            profile_completeness=90.0,
            photo_count=2,
        )
        repo = FakeRepository(
            users=[viewer, candidate_a, candidate_b],
            preferences={
                viewer.telegram_id: PreferenceRecord(22, 32, "female", "Москва"),
            },
            candidates={
                viewer.id: [
                    CandidateStats(user=candidate_a, likes_received=5, skips_received=1, matches_count=2),
                    CandidateStats(user=candidate_b, likes_received=2, skips_received=1, matches_count=1),
                ]
            },
        )
        cache = RecommendationCache()
        service = DatingCoreService(repo=repo, cache=cache, recommendation_batch_size=2)

        first_candidate = service.get_next_candidate(viewer.telegram_id)
        second_candidate = service.get_next_candidate(viewer.telegram_id)

        self.assertIsNotNone(first_candidate)
        self.assertIsNotNone(second_candidate)
        self.assertEqual(first_candidate.user.id, candidate_a.id)
        self.assertEqual(second_candidate.user.id, candidate_b.id)
        self.assertEqual(repo.list_candidates_calls, 1)


class FakeRepository:
    def __init__(
        self,
        users: list[UserRecord],
        preferences: dict[int, PreferenceRecord],
        candidates: dict[int, list[CandidateStats]],
    ) -> None:
        self.users_by_id = {user.id: user for user in users}
        self.users_by_telegram_id = {user.telegram_id: user for user in users}
        self.preferences = preferences
        self.candidates = candidates
        self.list_candidates_calls = 0

    def get_user_by_telegram_id(self, telegram_id: int) -> UserRecord | None:
        return self.users_by_telegram_id.get(telegram_id)

    def get_user_by_id(self, user_id: int) -> UserRecord:
        return self.users_by_id[user_id]

    def ensure_default_preferences(self, telegram_id: int) -> PreferenceRecord:
        return self.preferences[telegram_id]

    def list_candidates_for_user(self, viewer_user_id: int, limit: int = 200) -> list[CandidateStats]:
        self.list_candidates_calls += 1
        return list(self.candidates.get(viewer_user_id, []))[:limit]


def _make_user(
    user_id: int,
    telegram_id: int,
    *,
    first_name: str = "User",
    last_name: str | None = None,
    username: str | None = None,
    birth_date: str | None = None,
    gender: str | None = None,
    bio: str | None = "bio",
    city: str | None = None,
    profile_completeness: float = 80.0,
    photo_count: int = 2,
) -> UserRecord:
    return UserRecord(
        id=user_id,
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        birth_date=birth_date,
        gender=gender,
        bio=bio,
        city=city,
        profile_completeness=profile_completeness,
        status="active",
        photo_count=photo_count,
        created_at="2026-05-07T00:00:00+03:00",
        updated_at="2026-05-07T00:00:00+03:00",
    )


def _birth_date_for_age(age: int) -> str:
    today = date.today()
    return date(today.year - age, max(1, today.month), max(1, today.day)).isoformat()


if __name__ == "__main__":
    unittest.main()
