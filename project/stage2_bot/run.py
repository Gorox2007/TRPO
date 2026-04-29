from __future__ import annotations

import argparse
import os
import sys

from .bot_service import TelegramBotService
from .cache import RecommendationCache
from .core import DatingCoreService
from .db import DatabaseError, PostgresRepository
from .telegram_api import TelegramApiError, TelegramClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Stage 3 Telegram Dating Bot.")
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
    if not args.token:
        print("Error: TELEGRAM_BOT_TOKEN is required.", file=sys.stderr)
        return 2

    try:
        repo = PostgresRepository(database_url=args.database_url, schema_path=args.schema_path)
        repo.initialize()
    except DatabaseError as exc:
        print(f"Database init error: {exc}", file=sys.stderr)
        return 1

    tg = TelegramClient(token=args.token, timeout_sec=args.poll_timeout)
    cache = RecommendationCache(ttl_sec=args.cache_ttl)
    core = DatingCoreService(
        repo=repo,
        cache=cache,
        recommendation_batch_size=args.recommendation_batch_size,
    )
    service = TelegramBotService(tg=tg, core=core)

    print("Stage 3 bot is running. Press Ctrl+C to stop.")
    try:
        service.run_forever()
    except KeyboardInterrupt:
        print("\nBot stopped.")
        return 0
    except TelegramApiError as exc:
        print(f"Telegram error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
