#!/usr/bin/env python3
"""Minimal RabbitMQ vs Redis benchmark for required practice tasks."""

from __future__ import annotations

import argparse
import csv
import json
import math
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, List

try:
    import pika
    import redis
except ImportError as exc:  # pragma: no cover - startup guard
    raise SystemExit("Install dependencies first: pip install -r requirements.txt") from exc


BROKERS = ("rabbitmq", "redis")
MESSAGE_SIZES = (128, 1024, 10 * 1024, 100 * 1024)
RATE_LEVELS = (1000, 5000, 10000)


@dataclass(frozen=True)
class RunConfig:
    broker: str
    scenario: str
    message_size: int
    target_rate: int
    duration_sec: int


@dataclass
class RunResult:
    broker: str
    scenario: str
    message_size: int
    target_rate: int
    duration_sec: int
    sent: int
    processed: int
    errors: int
    lost: int
    produced_mps: float
    processed_mps: float
    avg_latency_ms: float
    p95_latency_ms: float
    max_latency_ms: float
    degraded: bool


class SharedStats:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.sent = 0
        self.send_errors = 0
        self.processed = 0
        self.consume_errors = 0
        self.latencies_ms: List[float] = []

    def inc_sent(self) -> None:
        with self.lock:
            self.sent += 1

    def inc_send_error(self) -> None:
        with self.lock:
            self.send_errors += 1

    def add_processed(self, latency_ms: float) -> None:
        with self.lock:
            self.processed += 1
            self.latencies_ms.append(latency_ms)

    def inc_consume_error(self) -> None:
        with self.lock:
            self.consume_errors += 1

    def snapshot(self) -> tuple[int, int, int, int, List[float]]:
        with self.lock:
            return (
                self.sent,
                self.send_errors,
                self.processed,
                self.consume_errors,
                list(self.latencies_ms),
            )

    def backlog(self) -> int:
        with self.lock:
            return self.sent - self.processed


def percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    values_sorted = sorted(values)
    index = max(0, math.ceil((p / 100.0) * len(values_sorted)) - 1)
    return values_sorted[index]


def parse_latency_ms(raw_body: bytes) -> float:
    payload = json.loads(raw_body.decode("utf-8"))
    sent_ts_ms = float(payload["sent_ts_ms"])
    latency = (time.time() * 1000.0) - sent_ts_ms
    return max(0.0, latency)


def producer_worker(
    send_fn: Callable[[bytes], None],
    payload: str,
    target_rate: int,
    duration_sec: int,
    stats: SharedStats,
) -> None:
    interval = 1.0 / target_rate if target_rate > 0 else 0.0
    finish_at = time.perf_counter() + duration_sec
    next_tick = time.perf_counter()

    while time.perf_counter() < finish_at:
        if interval > 0:
            now = time.perf_counter()
            if now < next_tick:
                time.sleep(next_tick - now)
            else:
                lag = now - next_tick
                if lag > interval:
                    next_tick = now
            next_tick += interval

        body = json.dumps(
            {"sent_ts_ms": time.time() * 1000.0, "payload": payload},
            separators=(",", ":"),
        ).encode("utf-8")
        try:
            send_fn(body)
            stats.inc_sent()
        except Exception:
            stats.inc_send_error()


def wait_for_drain(stats: SharedStats, drain_timeout_sec: int) -> None:
    deadline = time.time() + drain_timeout_sec
    while time.time() < deadline:
        if stats.backlog() <= 0:
            return
        time.sleep(0.1)


def finalize_result(config: RunConfig, stats: SharedStats) -> RunResult:
    sent, send_errors, processed, consume_errors, latencies_ms = stats.snapshot()
    errors = send_errors + consume_errors
    lost = max(sent - processed, 0)
    produced_mps = sent / config.duration_sec if config.duration_sec else 0.0
    processed_mps = processed / config.duration_sec if config.duration_sec else 0.0
    avg_latency_ms = sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0.0
    p95_latency_ms = percentile(latencies_ms, 95.0)
    max_latency_ms = max(latencies_ms) if latencies_ms else 0.0

    degraded = bool(lost > 0 or errors > 0 or processed_mps < (config.target_rate * 0.95))

    return RunResult(
        broker=config.broker,
        scenario=config.scenario,
        message_size=config.message_size,
        target_rate=config.target_rate,
        duration_sec=config.duration_sec,
        sent=sent,
        processed=processed,
        errors=errors,
        lost=lost,
        produced_mps=produced_mps,
        processed_mps=processed_mps,
        avg_latency_ms=avg_latency_ms,
        p95_latency_ms=p95_latency_ms,
        max_latency_ms=max_latency_ms,
        degraded=degraded,
    )


def run_rabbitmq(config: RunConfig, args: argparse.Namespace) -> RunResult:
    stats = SharedStats()
    queue_name = f"bench_rabbitmq_{int(time.time() * 1000)}"
    payload = "x" * config.message_size
    stop_event = threading.Event()

    producer_connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=args.rabbit_host, port=args.rabbit_port, heartbeat=0)
    )
    producer_channel = producer_connection.channel()
    producer_channel.queue_declare(queue=queue_name, durable=False, auto_delete=True)
    producer_channel.queue_purge(queue=queue_name)

    def send_fn(body: bytes) -> None:
        producer_channel.basic_publish(exchange="", routing_key=queue_name, body=body)

    def consumer_worker() -> None:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=args.rabbit_host, port=args.rabbit_port, heartbeat=0)
        )
        channel = connection.channel()
        channel.queue_declare(queue=queue_name, durable=False, auto_delete=True)
        try:
            while not stop_event.is_set():
                method, _, body = channel.basic_get(queue=queue_name, auto_ack=False)
                if method is None:
                    time.sleep(0.001)
                    continue
                try:
                    stats.add_processed(parse_latency_ms(body))
                except Exception:
                    stats.inc_consume_error()
                finally:
                    channel.basic_ack(delivery_tag=method.delivery_tag)
        finally:
            channel.close()
            connection.close()

    consumer_thread = threading.Thread(target=consumer_worker, daemon=True)
    consumer_thread.start()

    producer_worker(send_fn, payload, config.target_rate, config.duration_sec, stats)
    wait_for_drain(stats, args.drain_timeout_sec)

    stop_event.set()
    consumer_thread.join(timeout=5)

    producer_channel.close()
    producer_connection.close()
    return finalize_result(config, stats)


def run_redis(config: RunConfig, args: argparse.Namespace) -> RunResult:
    stats = SharedStats()
    queue_name = f"bench_redis_{int(time.time() * 1000)}"
    payload = "x" * config.message_size
    stop_event = threading.Event()

    producer_client = redis.Redis(host=args.redis_host, port=args.redis_port, decode_responses=False)
    consumer_client = redis.Redis(host=args.redis_host, port=args.redis_port, decode_responses=False)
    producer_client.delete(queue_name)

    def send_fn(body: bytes) -> None:
        producer_client.lpush(queue_name, body)

    def consumer_worker() -> None:
        while not stop_event.is_set():
            item = consumer_client.brpop(queue_name, timeout=1)
            if item is None:
                continue
            _, body = item
            try:
                stats.add_processed(parse_latency_ms(body))
            except Exception:
                stats.inc_consume_error()

    consumer_thread = threading.Thread(target=consumer_worker, daemon=True)
    consumer_thread.start()

    producer_worker(send_fn, payload, config.target_rate, config.duration_sec, stats)
    wait_for_drain(stats, args.drain_timeout_sec)

    stop_event.set()
    consumer_thread.join(timeout=5)
    producer_client.delete(queue_name)
    return finalize_result(config, stats)


def wait_for_rabbitmq(host: str, port: int, timeout_sec: int = 45) -> None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=host, port=port, heartbeat=0)
            )
            connection.close()
            return
        except Exception:
            time.sleep(1)
    raise RuntimeError("RabbitMQ is unavailable. Start docker compose first.")


def wait_for_redis(host: str, port: int, timeout_sec: int = 45) -> None:
    client = redis.Redis(host=host, port=port, decode_responses=False)
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        try:
            if client.ping():
                return
        except Exception:
            time.sleep(1)
    raise RuntimeError("Redis is unavailable. Start docker compose first.")


def build_plan(duration_sec: int, base_rate: int) -> List[RunConfig]:
    plan: List[RunConfig] = []
    for broker in BROKERS:
        plan.append(
            RunConfig(
                broker=broker,
                scenario="base",
                message_size=1024,
                target_rate=base_rate,
                duration_sec=duration_sec,
            )
        )
        for message_size in MESSAGE_SIZES:
            plan.append(
                RunConfig(
                    broker=broker,
                    scenario="size",
                    message_size=message_size,
                    target_rate=base_rate,
                    duration_sec=duration_sec,
                )
            )
        for target_rate in RATE_LEVELS:
            plan.append(
                RunConfig(
                    broker=broker,
                    scenario="rate",
                    message_size=1024,
                    target_rate=target_rate,
                    duration_sec=duration_sec,
                )
            )
    return plan


def write_csv(results: List[RunResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for row in results:
            writer.writerow(asdict(row))


def get_degradation_point(results: List[RunResult], broker: str) -> str:
    rate_rows = sorted(
        (row for row in results if row.broker == broker and row.scenario == "rate"),
        key=lambda row: row.target_rate,
    )
    for row in rate_rows:
        if row.degraded:
            return f"{row.target_rate} msg/s"
    return "not reached in tested range"


def write_summary(results: List[RunResult], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines: List[str] = []
    lines.append("# Benchmark Summary")
    lines.append("")
    lines.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append(
        "| broker | scenario | size (B) | rate (msg/s) | sent | processed | errors | "
        "lost | processed msg/s | avg latency ms | p95 latency ms | max latency ms | degraded |"
    )
    lines.append(
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"
    )
    for row in results:
        lines.append(
            f"| {row.broker} | {row.scenario} | {row.message_size} | {row.target_rate} | "
            f"{row.sent} | {row.processed} | {row.errors} | {row.lost} | "
            f"{row.processed_mps:.2f} | {row.avg_latency_ms:.2f} | {row.p95_latency_ms:.2f} | "
            f"{row.max_latency_ms:.2f} | {row.degraded} |"
        )
    lines.append("")
    lines.append("## Degradation Point (single instance)")
    lines.append("")
    lines.append(f"- RabbitMQ: {get_degradation_point(results, 'rabbitmq')}")
    lines.append(f"- Redis: {get_degradation_point(results, 'redis')}")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Minimal benchmark RabbitMQ vs Redis.")
    parser.add_argument("--duration-sec", type=int, default=20, help="Duration for each run.")
    parser.add_argument("--base-rate", type=int, default=2000, help="Base message rate.")
    parser.add_argument(
        "--drain-timeout-sec",
        type=int,
        default=8,
        help="Seconds to wait for queue drain after producer stop.",
    )
    parser.add_argument("--rabbit-host", default="localhost")
    parser.add_argument("--rabbit-port", type=int, default=5672)
    parser.add_argument("--redis-host", default="localhost")
    parser.add_argument("--redis-port", type=int, default=6379)
    parser.add_argument("--output-dir", default="results")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    wait_for_rabbitmq(args.rabbit_host, args.rabbit_port)
    wait_for_redis(args.redis_host, args.redis_port)

    plan = build_plan(duration_sec=args.duration_sec, base_rate=args.base_rate)
    results: List[RunResult] = []

    for index, config in enumerate(plan, start=1):
        print(
            f"[{index}/{len(plan)}] broker={config.broker}, scenario={config.scenario}, "
            f"size={config.message_size}, rate={config.target_rate}"
        )
        if config.broker == "rabbitmq":
            result = run_rabbitmq(config, args)
        else:
            result = run_redis(config, args)
        results.append(result)
        print(
            f"  sent={result.sent}, processed={result.processed}, errors={result.errors}, "
            f"lost={result.lost}, p95={result.p95_latency_ms:.2f}ms"
        )

    output_dir = Path(args.output_dir)
    write_csv(results, output_dir / "raw_results.csv")
    write_summary(results, output_dir / "summary.md")
    print(f"Done. Results saved to: {output_dir.resolve()}")


if __name__ == "__main__":
    main()
