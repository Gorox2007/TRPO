#!/usr/bin/env python3
"""Unified cache strategy benchmark for cache comparison practice."""

from __future__ import annotations

import argparse
import csv
import math
import random
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Dict, List, Sequence

import psycopg
from redis import Redis

from app.cache_strategies import (
    CACHE_KEY_PREFIX,
    CacheAsideStrategy,
    WriteBackStrategy,
    WriteThroughStrategy,
)


@dataclass(frozen=True)
class Scenario:
    name: str
    read_ratio: float


@dataclass(frozen=True)
class Operation:
    kind: str
    item_id: int
    value: str | None = None


@dataclass
class RunResult:
    ts_utc: str
    strategy: str
    scenario: str
    read_ratio: float
    total_requests: int
    planned_duration_sec: float
    actual_duration_sec: float
    throughput_rps: float
    avg_latency_ms: float
    p95_latency_ms: float
    db_reads: int
    db_writes: int
    db_total_ops: int
    cache_hits: int
    cache_misses: int
    cache_hit_rate: float
    errors: int
    wb_queue_max: int
    wb_queue_avg: float
    wb_flush_batches: int
    wb_flushed_items: int


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(name="read-heavy", read_ratio=0.80),
    Scenario(name="balanced", read_ratio=0.50),
    Scenario(name="write-heavy", read_ratio=0.20),
)

STRATEGIES: tuple[str, ...] = ("cache_aside", "write_through", "write_back")


def percentile(values: Sequence[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = max(0, math.ceil((p / 100.0) * len(sorted_values)) - 1)
    return float(sorted_values[index])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cache strategy benchmark")
    parser.add_argument(
        "--pg-dsn",
        default="postgresql://postgres:postgres@localhost:55432/cache_practice",
        help="PostgreSQL DSN",
    )
    parser.add_argument("--redis-host", default="localhost", help="Redis host")
    parser.add_argument("--redis-port", type=int, default=56379, help="Redis port")
    parser.add_argument("--redis-db", type=int, default=0, help="Redis DB index")
    parser.add_argument("--dataset-size", type=int, default=5000, help="Amount of rows in DB")
    parser.add_argument(
        "--duration-sec",
        type=float,
        default=20.0,
        help="Planned duration of each run in seconds",
    )
    parser.add_argument(
        "--target-rps",
        type=int,
        default=400,
        help="Target request rate used to build operation list",
    )
    parser.add_argument("--cache-ttl-sec", type=int, default=120, help="Cache TTL")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument(
        "--write-back-flush-interval-sec",
        type=float,
        default=0.3,
        help="Write-back flush interval",
    )
    parser.add_argument(
        "--write-back-batch-size",
        type=int,
        default=200,
        help="Write-back batch size",
    )
    return parser.parse_args()


def ensure_schema(pg_dsn: str) -> None:
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )


def reset_state(pg_dsn: str, redis_client: Redis, dataset_size: int) -> None:
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE items")
            cur.execute(
                """
                INSERT INTO items (id, value, updated_at)
                SELECT i, 'value-' || i::text, NOW()
                FROM generate_series(1, %s) AS s(i)
                """,
                (dataset_size,),
            )

    delete_cache_prefix(redis_client, f"{CACHE_KEY_PREFIX}*")


def delete_cache_prefix(redis_client: Redis, pattern: str) -> None:
    cursor = 0
    while True:
        cursor, keys = redis_client.scan(cursor=cursor, match=pattern, count=1000)
        if keys:
            redis_client.delete(*keys)
        if cursor == 0:
            break


def build_operations(
    *,
    total_requests: int,
    scenario: Scenario,
    dataset_size: int,
    seed: int,
) -> List[Operation]:
    rnd = random.Random(seed)
    read_count = int(total_requests * scenario.read_ratio)
    write_count = total_requests - read_count

    operations: List[Operation] = []
    for _ in range(read_count):
        operations.append(Operation(kind="read", item_id=rnd.randint(1, dataset_size)))
    for idx in range(write_count):
        operations.append(
            Operation(
                kind="write",
                item_id=rnd.randint(1, dataset_size),
                value=f"{scenario.name}-update-{seed}-{idx}",
            )
        )

    rnd.shuffle(operations)
    return operations


def create_strategy(strategy_name: str, args: argparse.Namespace, redis_client: Redis):
    if strategy_name == "cache_aside":
        return CacheAsideStrategy(redis_client, args.pg_dsn, args.cache_ttl_sec)
    if strategy_name == "write_through":
        return WriteThroughStrategy(redis_client, args.pg_dsn, args.cache_ttl_sec)
    if strategy_name == "write_back":
        return WriteBackStrategy(
            redis_client=redis_client,
            pg_dsn=args.pg_dsn,
            cache_ttl_sec=args.cache_ttl_sec,
            flush_interval_sec=args.write_back_flush_interval_sec,
            batch_size=args.write_back_batch_size,
        )
    raise ValueError(f"Unknown strategy {strategy_name}")


def run_operations(strategy, operations: List[Operation], duration_sec: float) -> tuple[float, List[float]]:
    latencies_ms: List[float] = []
    if not operations:
        return 0.0, latencies_ms

    target_interval = duration_sec / len(operations)
    start = time.perf_counter()
    next_tick = start

    for op in operations:
        now = time.perf_counter()
        if now < next_tick:
            time.sleep(next_tick - now)
        else:
            next_tick = now

        op_start = time.perf_counter()
        try:
            if op.kind == "read":
                strategy.read(op.item_id)
            else:
                strategy.write(op.item_id, op.value or "")
        except Exception:
            strategy.mark_error()
        latencies_ms.append((time.perf_counter() - op_start) * 1000.0)
        next_tick += target_interval

    client_elapsed = time.perf_counter() - start
    strategy.drain()
    return client_elapsed, latencies_ms


def run_single(
    *,
    strategy_name: str,
    scenario: Scenario,
    operations: List[Operation],
    args: argparse.Namespace,
    redis_client: Redis,
) -> RunResult:
    reset_state(args.pg_dsn, redis_client, args.dataset_size)
    strategy = create_strategy(strategy_name, args, redis_client)
    actual_duration_sec = 0.0
    latencies_ms: List[float] = []

    try:
        actual_duration_sec, latencies_ms = run_operations(strategy, operations, args.duration_sec)
    finally:
        strategy.close()
    stats: Dict[str, float | int] = strategy.snapshot()

    avg_latency_ms = (sum(latencies_ms) / len(latencies_ms)) if latencies_ms else 0.0
    throughput_rps = len(operations) / actual_duration_sec if actual_duration_sec else 0.0

    return RunResult(
        ts_utc=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        strategy=strategy_name,
        scenario=scenario.name,
        read_ratio=scenario.read_ratio,
        total_requests=len(operations),
        planned_duration_sec=args.duration_sec,
        actual_duration_sec=actual_duration_sec,
        throughput_rps=throughput_rps,
        avg_latency_ms=avg_latency_ms,
        p95_latency_ms=percentile(latencies_ms, 95.0),
        db_reads=int(stats["db_reads"]),
        db_writes=int(stats["db_writes"]),
        db_total_ops=int(stats["db_reads"] + stats["db_writes"]),
        cache_hits=int(stats["cache_hits"]),
        cache_misses=int(stats["cache_misses"]),
        cache_hit_rate=float(stats["cache_hit_rate"]),
        errors=int(stats["errors"]),
        wb_queue_max=int(stats["wb_queue_max"]),
        wb_queue_avg=float(stats["wb_queue_avg"]),
        wb_flush_batches=int(stats["wb_flush_batches"]),
        wb_flushed_items=int(stats["wb_flushed_items"]),
    )


def save_csv(results: List[RunResult], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    if not results:
        return

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for result in results:
            writer.writerow(asdict(result))


def best_for_scenario(results: List[RunResult], scenario_name: str) -> str:
    scenario_rows = [r for r in results if r.scenario == scenario_name]
    if not scenario_rows:
        return "n/a"

    winner = sorted(
        scenario_rows,
        key=lambda r: (r.throughput_rps, -r.avg_latency_ms),
        reverse=True,
    )[0]
    return winner.strategy


def save_summary(results: List[RunResult], summary_path: Path, args: argparse.Namespace) -> None:
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    lines: List[str] = []
    lines.append("# Cache Comparison Summary")
    lines.append("")
    lines.append("## Benchmark Config")
    lines.append("")
    generated_at = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    lines.append(f"- Generated at (UTC): `{generated_at}`")
    lines.append(f"- Dataset size: `{args.dataset_size}`")
    lines.append(f"- Duration per run: `{args.duration_sec} sec`")
    lines.append(f"- Target RPS: `{args.target_rps}`")
    lines.append(f"- Total requests per run: `{int(args.duration_sec * args.target_rps)}`")
    lines.append(f"- Cache TTL: `{args.cache_ttl_sec} sec`")
    lines.append(
        "- Write-back flush: "
        f"interval `{args.write_back_flush_interval_sec} sec`, batch `{args.write_back_batch_size}`"
    )
    lines.append("")

    lines.append("## Main Results")
    lines.append("")
    lines.append(
        "| Scenario | Strategy | Throughput (req/sec) | Avg latency (ms) | P95 latency (ms) | "
        "DB ops | DB reads | DB writes | Cache hit rate (%) | Errors |"
    )
    lines.append("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")

    for row in results:
        lines.append(
            f"| {row.scenario} | {row.strategy} | {row.throughput_rps:.2f} | "
            f"{row.avg_latency_ms:.2f} | {row.p95_latency_ms:.2f} | {row.db_total_ops} | "
            f"{row.db_reads} | {row.db_writes} | {row.cache_hit_rate:.2f} | {row.errors} |"
        )

    lines.append("")
    lines.append("## Write-Back Buffer Behavior")
    lines.append("")
    lines.append(
        "| Scenario | Throughput (req/sec) | Queue max | Queue avg | Flushed items | Flush batches |"
    )
    lines.append("|---|---:|---:|---:|---:|---:|")
    for row in results:
        if row.strategy != "write_back":
            continue
        lines.append(
            f"| {row.scenario} | {row.throughput_rps:.2f} | {row.wb_queue_max} | "
            f"{row.wb_queue_avg:.2f} | {row.wb_flushed_items} | {row.wb_flush_batches} |"
        )

    lines.append("")
    lines.append("## Auto Conclusions")
    lines.append("")
    lines.append(
        f"- Best for read-heavy: `{best_for_scenario(results, 'read-heavy')}` "
        "(max throughput, tiebreak by latency)."
    )
    lines.append(
        f"- Best for balanced: `{best_for_scenario(results, 'balanced')}` "
        "(max throughput, tiebreak by latency)."
    )
    lines.append(
        f"- Best for write-heavy: `{best_for_scenario(results, 'write-heavy')}` "
        "(max throughput, tiebreak by latency)."
    )
    lines.append(
        "- For write-back, monitor queue growth (`Queue max/avg`): "
        "the larger the queue, the stronger delayed DB sync effect."
    )

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    total_requests = int(args.duration_sec * args.target_rps)
    if total_requests <= 0:
        raise SystemExit("Total requests must be > 0 (check --duration-sec and --target-rps)")

    ensure_schema(args.pg_dsn)
    redis_client = Redis(host=args.redis_host, port=args.redis_port, db=args.redis_db, decode_responses=False)

    operations_by_scenario: Dict[str, List[Operation]] = {}
    for index, scenario in enumerate(SCENARIOS, start=1):
        operations_by_scenario[scenario.name] = build_operations(
            total_requests=total_requests,
            scenario=scenario,
            dataset_size=args.dataset_size,
            seed=args.seed + index,
        )

    results: List[RunResult] = []
    for scenario in SCENARIOS:
        for strategy_name in STRATEGIES:
            print(
                f"[run] scenario={scenario.name} strategy={strategy_name} "
                f"requests={len(operations_by_scenario[scenario.name])}"
            )
            row = run_single(
                strategy_name=strategy_name,
                scenario=scenario,
                operations=operations_by_scenario[scenario.name],
                args=args,
                redis_client=redis_client,
            )
            print(
                f"      throughput={row.throughput_rps:.2f} req/sec "
                f"avg={row.avg_latency_ms:.2f}ms db_ops={row.db_total_ops} "
                f"hit_rate={row.cache_hit_rate:.2f}% errors={row.errors}"
            )
            results.append(row)

    out_dir = Path(__file__).resolve().parent / "results"
    csv_path = out_dir / "raw_results.csv"
    summary_path = out_dir / "summary.md"

    save_csv(results, csv_path)
    save_summary(results, summary_path, args)

    print(f"\nSaved: {csv_path}")
    print(f"Saved: {summary_path}")


if __name__ == "__main__":
    main()
