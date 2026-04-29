"""Cache strategy implementations for comparison practice."""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Tuple

import psycopg
from redis import Redis

CACHE_KEY_PREFIX = "cachecmp:item:"


@dataclass
class StrategyStats:
    reads: int = 0
    writes: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    db_reads: int = 0
    db_writes: int = 0
    cache_writes: int = 0
    errors: int = 0
    wb_flush_batches: int = 0
    wb_flushed_items: int = 0
    wb_queue_max: int = 0
    wb_queue_samples: int = 0
    wb_queue_sum: int = 0


class BaseStrategy:
    name = "base"

    def __init__(self, redis_client: Redis, pg_dsn: str, cache_ttl_sec: int) -> None:
        self.redis = redis_client
        self.pg_dsn = pg_dsn
        self.pg_conn = psycopg.connect(pg_dsn, autocommit=True)
        self.cache_ttl_sec = cache_ttl_sec
        self.stats = StrategyStats()
        self._lock = threading.Lock()

    def _cache_key(self, item_id: int) -> str:
        return f"{CACHE_KEY_PREFIX}{item_id}"

    def _inc(self, field: str, value: int = 1) -> None:
        with self._lock:
            current = getattr(self.stats, field)
            setattr(self.stats, field, current + value)

    def _record_queue_size(self, queue_size: int) -> None:
        with self._lock:
            self.stats.wb_queue_samples += 1
            self.stats.wb_queue_sum += queue_size
            if queue_size > self.stats.wb_queue_max:
                self.stats.wb_queue_max = queue_size

    def _fetch_from_db(self, item_id: int) -> str:
        with self.pg_conn.cursor() as cur:
            cur.execute("SELECT value FROM items WHERE id = %s", (item_id,))
            row = cur.fetchone()
        self._inc("db_reads")
        if row is None:
            raise KeyError(f"Item {item_id} was not found")
        return str(row[0])

    def _write_to_db(self, item_id: int, value: str) -> None:
        with self.pg_conn.cursor() as cur:
            cur.execute(
                "UPDATE items SET value = %s, updated_at = NOW() WHERE id = %s",
                (value, item_id),
            )
        self._inc("db_writes")

    def _cache_get(self, item_id: int) -> str | None:
        raw = self.redis.get(self._cache_key(item_id))
        if raw is None:
            self._inc("cache_misses")
            return None
        self._inc("cache_hits")
        if isinstance(raw, bytes):
            return raw.decode("utf-8")
        return str(raw)

    def _cache_set(self, item_id: int, value: str) -> None:
        self.redis.set(self._cache_key(item_id), value, ex=self.cache_ttl_sec)
        self._inc("cache_writes")

    def _cache_invalidate(self, item_id: int) -> None:
        self.redis.delete(self._cache_key(item_id))

    def read(self, item_id: int) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    def write(self, item_id: int, value: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError

    def mark_error(self) -> None:
        self._inc("errors")

    def drain(self) -> None:
        """Used by write-back to flush buffer, noop for others."""

    def snapshot(self) -> Dict[str, float | int]:
        with self._lock:
            stats = StrategyStats(**self.stats.__dict__)

        hit_total = stats.cache_hits + stats.cache_misses
        hit_rate = (stats.cache_hits / hit_total * 100.0) if hit_total else 0.0
        wb_avg_queue = (
            stats.wb_queue_sum / stats.wb_queue_samples if stats.wb_queue_samples else 0.0
        )

        return {
            "reads": stats.reads,
            "writes": stats.writes,
            "cache_hits": stats.cache_hits,
            "cache_misses": stats.cache_misses,
            "db_reads": stats.db_reads,
            "db_writes": stats.db_writes,
            "cache_writes": stats.cache_writes,
            "errors": stats.errors,
            "cache_hit_rate": hit_rate,
            "wb_flush_batches": stats.wb_flush_batches,
            "wb_flushed_items": stats.wb_flushed_items,
            "wb_queue_max": stats.wb_queue_max,
            "wb_queue_avg": wb_avg_queue,
        }

    def close(self) -> None:
        self.pg_conn.close()


class CacheAsideStrategy(BaseStrategy):
    """Lazy loading + write-around."""

    name = "cache_aside"

    def read(self, item_id: int) -> str:
        self._inc("reads")
        cached = self._cache_get(item_id)
        if cached is not None:
            return cached

        value = self._fetch_from_db(item_id)
        self._cache_set(item_id, value)
        return value

    def write(self, item_id: int, value: str) -> None:
        self._inc("writes")
        self._write_to_db(item_id, value)
        self._cache_invalidate(item_id)


class WriteThroughStrategy(BaseStrategy):
    name = "write_through"

    def read(self, item_id: int) -> str:
        self._inc("reads")
        cached = self._cache_get(item_id)
        if cached is not None:
            return cached

        value = self._fetch_from_db(item_id)
        self._cache_set(item_id, value)
        return value

    def write(self, item_id: int, value: str) -> None:
        self._inc("writes")
        self._write_to_db(item_id, value)
        self._cache_set(item_id, value)


class WriteBackStrategy(BaseStrategy):
    name = "write_back"

    def __init__(
        self,
        redis_client: Redis,
        pg_dsn: str,
        cache_ttl_sec: int,
        flush_interval_sec: float,
        batch_size: int,
    ) -> None:
        super().__init__(redis_client=redis_client, pg_dsn=pg_dsn, cache_ttl_sec=cache_ttl_sec)
        self.flush_interval_sec = flush_interval_sec
        self.batch_size = batch_size
        self._pending: Deque[Tuple[int, str]] = deque()
        self._pending_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._flusher = threading.Thread(target=self._flusher_loop, daemon=True)
        self._flusher.start()

    def _pending_size(self) -> int:
        with self._pending_lock:
            return len(self._pending)

    def _pull_batch(self) -> list[Tuple[int, str]]:
        with self._pending_lock:
            items: list[Tuple[int, str]] = []
            while self._pending and len(items) < self.batch_size:
                items.append(self._pending.popleft())
            return items

    def _flusher_loop(self) -> None:
        flush_conn = psycopg.connect(self.pg_dsn, autocommit=True)
        try:
            while not self._stop_event.is_set() or self._pending_size() > 0:
                batch = self._pull_batch()
                if not batch:
                    time.sleep(self.flush_interval_sec)
                    continue

                with flush_conn.cursor() as cur:
                    cur.executemany(
                        "UPDATE items SET value = %s, updated_at = NOW() WHERE id = %s",
                        [(value, item_id) for item_id, value in batch],
                    )

                self._inc("db_writes", len(batch))
                self._inc("wb_flushed_items", len(batch))
                self._inc("wb_flush_batches")
                self._record_queue_size(self._pending_size())
        finally:
            flush_conn.close()

    def read(self, item_id: int) -> str:
        self._inc("reads")
        cached = self._cache_get(item_id)
        if cached is not None:
            return cached

        value = self._fetch_from_db(item_id)
        self._cache_set(item_id, value)
        return value

    def write(self, item_id: int, value: str) -> None:
        self._inc("writes")
        self._cache_set(item_id, value)

        with self._pending_lock:
            self._pending.append((item_id, value))
            queue_size = len(self._pending)
        self._record_queue_size(queue_size)

    def drain(self) -> None:
        deadline = time.time() + 30
        while time.time() < deadline:
            if self._pending_size() == 0:
                return
            time.sleep(0.05)

    def close(self) -> None:
        self._stop_event.set()
        self._flusher.join(timeout=10)
        super().close()
