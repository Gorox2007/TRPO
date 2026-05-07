from __future__ import annotations

from dataclasses import dataclass
from time import monotonic


@dataclass
class CachedCandidate:
    user_id: int
    score: float
    primary_score: float
    behavioral_score: float


@dataclass
class _CacheEntry:
    candidates: list[CachedCandidate]
    expires_at: float


class RecommendationCache:
    """Small in-memory cache for pre-ranked candidate queues."""

    def __init__(self, ttl_sec: int = 300) -> None:
        self.ttl_sec = ttl_sec
        self._entries: dict[int, _CacheEntry] = {}

    def get(self, viewer_user_id: int) -> list[CachedCandidate]:
        entry = self._entries.get(viewer_user_id)
        if entry is None:
            return []
        if entry.expires_at <= monotonic():
            self._entries.pop(viewer_user_id, None)
            return []
        return list(entry.candidates)

    def set(self, viewer_user_id: int, candidates: list[CachedCandidate]) -> None:
        self._entries[viewer_user_id] = _CacheEntry(
            candidates=list(candidates),
            expires_at=monotonic() + self.ttl_sec,
        )

    def pop_next(self, viewer_user_id: int) -> CachedCandidate | None:
        candidates = self.get(viewer_user_id)
        if not candidates:
            return None
        next_candidate = candidates.pop(0)
        self.set(viewer_user_id, candidates)
        return next_candidate

    def invalidate(self, viewer_user_id: int) -> None:
        self._entries.pop(viewer_user_id, None)
