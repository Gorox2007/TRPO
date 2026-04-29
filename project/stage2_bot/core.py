from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .cache import CachedCandidate, RecommendationCache
from .db import (
    ActionResult,
    CandidateStats,
    PhotoRecord,
    PostgresRepository,
    PreferenceRecord,
    UserRecord,
)


@dataclass
class CandidateRecommendation:
    user: UserRecord
    score: float
    primary_score: float
    behavioral_score: float
    referral_score: float


class DatingCoreService:
    """Core layer for profile CRUD, ranking, cache and reactions."""

    def __init__(
        self,
        repo: PostgresRepository,
        cache: RecommendationCache | None = None,
        recommendation_batch_size: int = 10,
    ) -> None:
        self.repo = repo
        self.cache = cache or RecommendationCache()
        self.recommendation_batch_size = recommendation_batch_size

    def register_user(
        self,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        referral_code: str | None = None,
    ) -> UserRecord:
        return self.repo.register_or_update_user(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            referral_code=referral_code,
        )

    def get_profile(self, telegram_id: int) -> UserRecord | None:
        return self.repo.get_user_by_telegram_id(telegram_id)

    def update_profile(
        self,
        telegram_id: int,
        birth_date: str | None = None,
        gender: str | None = None,
        city: str | None = None,
        bio: str | None = None,
    ) -> UserRecord:
        self._validate_profile_fields(birth_date=birth_date, gender=gender, city=city)
        user = self.repo.update_profile(
            telegram_id=telegram_id,
            birth_date=birth_date,
            gender=gender,
            city=city,
            bio=bio,
        )
        self.cache.invalidate(user.id)
        return user

    def delete_profile(self, telegram_id: int) -> bool:
        user = self.repo.get_user_by_telegram_id(telegram_id)
        if user is not None:
            self.cache.invalidate(user.id)
        return self.repo.delete_profile(telegram_id)

    def get_or_create_preferences(self, telegram_id: int) -> PreferenceRecord:
        return self.repo.ensure_default_preferences(telegram_id)

    def update_preferences(
        self,
        telegram_id: int,
        age_min: int | None = None,
        age_max: int | None = None,
        preferred_gender: str | None = None,
        preferred_city: str | None = None,
        max_distance_km: int | None = None,
    ) -> PreferenceRecord:
        self._validate_preferences(age_min, age_max, preferred_gender, preferred_city, max_distance_km)
        user = self.repo.get_user_by_telegram_id(telegram_id)
        pref = self.repo.update_preferences(
            telegram_id=telegram_id,
            age_min=age_min,
            age_max=age_max,
            preferred_gender=preferred_gender,
            preferred_city=preferred_city,
            max_distance_km=max_distance_km,
        )
        if user is not None:
            self.cache.invalidate(user.id)
        return pref

    def add_photo(
        self,
        telegram_id: int,
        telegram_file_id: str,
        telegram_file_unique_id: str,
        position: int | None = None,
        is_primary: bool = False,
    ) -> PhotoRecord:
        if not telegram_file_id or not telegram_file_unique_id:
            raise ValueError("photo file_id and file_unique_id are required")
        photo = self.repo.add_photo(
            telegram_id=telegram_id,
            telegram_file_id=telegram_file_id,
            telegram_file_unique_id=telegram_file_unique_id,
            position=position,
            is_primary=is_primary,
        )
        user = self.repo.get_user_by_telegram_id(telegram_id)
        if user is not None:
            self.cache.invalidate(user.id)
        return photo

    def get_next_candidate(self, telegram_id: int) -> CandidateRecommendation | None:
        viewer = self.repo.get_user_by_telegram_id(telegram_id)
        if viewer is None:
            return None

        cached = self.cache.pop_next(viewer.id)
        if cached is not None:
            return self._recommendation_from_cache(cached)

        ranked = self.rank_candidates(telegram_id)
        self.cache.set(
            viewer.id,
            [
                CachedCandidate(
                    user_id=item.user.id,
                    score=item.score,
                    primary_score=item.primary_score,
                    behavioral_score=item.behavioral_score,
                    referral_score=item.referral_score,
                )
                for item in ranked[: self.recommendation_batch_size]
            ],
        )
        cached = self.cache.pop_next(viewer.id)
        if cached is None:
            return None
        return self._recommendation_from_cache(cached)

    def rank_candidates(self, telegram_id: int) -> list[CandidateRecommendation]:
        viewer = self.repo.get_user_by_telegram_id(telegram_id)
        if viewer is None:
            return []
        preferences = self.repo.ensure_default_preferences(telegram_id)
        candidate_stats = self.repo.list_candidates_for_user(viewer.id)
        ranked = [
            self._score_candidate(viewer=viewer, preferences=preferences, candidate=stats)
            for stats in candidate_stats
        ]
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked

    def record_reaction(
        self,
        actor_telegram_id: int,
        target_user_id: int,
        action_type: str,
    ) -> ActionResult:
        actor = self.repo.get_user_by_telegram_id(actor_telegram_id)
        result = self.repo.record_action(actor_telegram_id, target_user_id, action_type)
        if actor is not None:
            self.cache.invalidate(actor.id)
        return result

    def _recommendation_from_cache(self, cached: CachedCandidate) -> CandidateRecommendation:
        return CandidateRecommendation(
            user=self.repo.get_user_by_id(cached.user_id),
            score=cached.score,
            primary_score=cached.primary_score,
            behavioral_score=cached.behavioral_score,
            referral_score=cached.referral_score,
        )

    def _score_candidate(
        self,
        viewer: UserRecord,
        preferences: PreferenceRecord,
        candidate: CandidateStats,
    ) -> CandidateRecommendation:
        age_score = self._age_score(candidate.user.birth_date, preferences)
        gender_score = 100.0 if preferences.preferred_gender in {"any", candidate.user.gender} else 0.0
        city_score = self._city_score(viewer_city=viewer.city, preferred_city=preferences.preferred_city, candidate_city=candidate.user.city)
        completeness_score = candidate.user.profile_completeness
        photo_score = min(candidate.user.photo_count, 5) / 5 * 100

        primary_score = (
            age_score * 0.25
            + gender_score * 0.20
            + city_score * 0.20
            + completeness_score * 0.25
            + photo_score * 0.10
        )

        total_reactions = candidate.likes_received + candidate.skips_received
        like_ratio = candidate.likes_received / total_reactions if total_reactions else 0.5
        like_score = like_ratio * 100
        match_score = min(candidate.matches_count, 10) / 10 * 100
        behavioral_score = like_score * 0.70 + match_score * 0.30

        referral_score = min(candidate.referrals_count, 5) / 5 * 100

        total_score = primary_score * 0.65 + behavioral_score * 0.30 + referral_score * 0.05
        return CandidateRecommendation(
            user=candidate.user,
            score=round(total_score, 2),
            primary_score=round(primary_score, 2),
            behavioral_score=round(behavioral_score, 2),
            referral_score=round(referral_score, 2),
        )

    @staticmethod
    def _age_score(birth_date: str | None, preferences: PreferenceRecord) -> float:
        age = _age_from_birth_date(birth_date)
        if age is None:
            return 30.0
        if preferences.age_min <= age <= preferences.age_max:
            return 100.0
        distance = min(abs(age - preferences.age_min), abs(age - preferences.age_max))
        return max(0.0, 100.0 - distance * 15)

    @staticmethod
    def _city_score(viewer_city: str | None, preferred_city: str, candidate_city: str | None) -> float:
        if preferred_city == "any":
            if viewer_city and candidate_city and viewer_city.casefold() == candidate_city.casefold():
                return 100.0
            return 70.0
        if candidate_city and candidate_city.casefold() == preferred_city.casefold():
            return 100.0
        return 0.0

    @staticmethod
    def _validate_profile_fields(
        birth_date: str | None,
        gender: str | None,
        city: str | None,
    ) -> None:
        if birth_date is not None:
            _parse_date(birth_date)
        if gender is not None and gender not in {"male", "female", "other"}:
            raise ValueError("gender must be one of: male, female, other")
        if city is not None and not city.strip():
            raise ValueError("city cannot be empty")

    @staticmethod
    def _validate_preferences(
        age_min: int | None,
        age_max: int | None,
        preferred_gender: str | None,
        preferred_city: str | None,
        max_distance_km: int | None,
    ) -> None:
        if age_min is not None and not 18 <= age_min <= 99:
            raise ValueError("age_min must be between 18 and 99")
        if age_max is not None and not 18 <= age_max <= 99:
            raise ValueError("age_max must be between 18 and 99")
        if age_min is not None and age_max is not None and age_max < age_min:
            raise ValueError("age_max must be greater than or equal to age_min")
        if preferred_gender is not None and preferred_gender not in {"male", "female", "any"}:
            raise ValueError("preferred gender must be one of: male, female, any")
        if preferred_city is not None and not preferred_city.strip():
            raise ValueError("preferred_city cannot be empty")
        if max_distance_km is not None and not 1 <= max_distance_km <= 500:
            raise ValueError("max_distance_km must be between 1 and 500")


def _age_from_birth_date(birth_date: str | None) -> int | None:
    if birth_date is None:
        return None
    born = _parse_date(birth_date)
    today = date.today()
    years = today.year - born.year
    if (today.month, today.day) < (born.month, born.day):
        years -= 1
    return years


def _parse_date(raw: str) -> date:
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD format") from exc
