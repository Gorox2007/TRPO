from __future__ import annotations

import argparse
import os
import sys
import time

from .bot_service import TelegramBotService
from .cache import RecommendationCache
from .core import DatingCoreService
from .db import DatabaseError, PostgresRepository
from .telegram_api import TelegramApiError, TelegramClient


STARTUP_RETRY_COUNT = 3
STARTUP_RETRY_DELAY_SEC = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage 4 Telegram Dating Bot.")
    parser.add_argument(
        "--token",
        default=os.getenv("TELEGRAM_BOT_TOKEN"),
        help="Telegram token (or use TELEGRAM_BOT_TOKEN env).",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/dating_bot"),
        help="PostgreSQL connection string (or use DATABASE_URL env).",
    )
    parser.add_argument(
        "--schema-path",
        default="db/schema.sql",
        help="Path to SQL schema file.",
    )
    parser.add_argument(
        "--poll-timeout",
        type=int,
        default=int(os.getenv("BOT_POLL_TIMEOUT", "25")),
        help="Telegram getUpdates timeout in seconds.",
    )
    parser.add_argument(
        "--cache-ttl",
        type=int,
        default=int(os.getenv("RECOMMENDATION_CACHE_TTL", "300")),
        help="Recommendation cache TTL in seconds.",
    )
    parser.add_argument(
        "--recommendation-batch-size",
        type=int,
        default=int(os.getenv("RECOMMENDATION_BATCH_SIZE", "10")),
        help="How many ranked candidates to pre-cache per user.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = (args.token or "").strip()
    if not token:
        print("Error: TELEGRAM_BOT_TOKEN is required.", file=sys.stderr)
        return 2
    if token == "your_bot_token":
        print("Error: TELEGRAM_BOT_TOKEN is still set to placeholder 'your_bot_token'.", file=sys.stderr)
        return 2

    try:
        repo = PostgresRepository(database_url=args.database_url, schema_path=args.schema_path)
        repo.initialize()
    except DatabaseError as exc:
        print(f"Database init error: {exc}", file=sys.stderr)
        return 1

    tg = TelegramClient(token=token, timeout_sec=args.poll_timeout)
    try:
        bot_info = _fetch_bot_info_with_retries(tg)
    except KeyboardInterrupt:
        print("\nBot startup cancelled.")
        return 130
    except TelegramApiError as exc:
        if exc.status_code == 404:
            print(
                "Telegram auth error: Bot API returned 404 Not Found.\n"
                "Usually this means TELEGRAM_BOT_TOKEN is invalid, truncated, or belongs to another bot.\n"
                "Set the real token from BotFather and run again.",
                file=sys.stderr,
            )
            return 1
        print(f"Telegram startup error: {exc}", file=sys.stderr)
        return 1

    cache = RecommendationCache(ttl_sec=args.cache_ttl)
    core = DatingCoreService(
        repo=repo,
        cache=cache,
        recommendation_batch_size=args.recommendation_batch_size,
    )
    service = TelegramBotService(tg=tg, core=core)

    username = bot_info.get("username") or "<unknown>"
    print(f"Stage 4 bot is running as @{username}. Press Ctrl+C to stop.")
    try:
        service.run_forever()
    except KeyboardInterrupt:
        print("\nBot stopped.")
        return 0
    except TelegramApiError as exc:
        print(f"Telegram error: {exc}", file=sys.stderr)
        return 1

def _fetch_bot_info_with_retries(tg: TelegramClient) -> dict[str, object]:
    last_error: TelegramApiError | None = None
    for attempt in range(1, STARTUP_RETRY_COUNT + 1):
        try:
            return tg.get_me()
        except TelegramApiError as exc:
            last_error = exc
            if not exc.retriable or attempt == STARTUP_RETRY_COUNT:
                break
            print(
                f"Telegram startup warning: {exc}. Retry {attempt}/{STARTUP_RETRY_COUNT} in {STARTUP_RETRY_DELAY_SEC} sec.",
                file=sys.stderr,
            )
            time.sleep(STARTUP_RETRY_DELAY_SEC)
    assert last_error is not None
    raise last_error


if __name__ == "__main__":
    raise SystemExit(main())
