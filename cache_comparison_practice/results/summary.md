# Cache Comparison Summary

## Benchmark Config

- Generated at (UTC): `2026-04-30T08:11:48Z`
- Dataset size: `5000`
- Duration per run: `20.0 sec`
- Target RPS: `400`
- Total requests per run: `8000`
- Cache TTL: `120 sec`
- Write-back flush: interval `0.3 sec`, batch `200`

## Main Results

| Scenario | Strategy | Throughput (req/sec) | Avg latency (ms) | P95 latency (ms) | DB ops | DB reads | DB writes | Cache hit rate (%) | Errors |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| read-heavy | cache_aside | 399.88 | 0.95 | 1.70 | 5378 | 3778 | 1600 | 40.97 | 0 |
| read-heavy | write_through | 399.82 | 0.90 | 1.68 | 4743 | 3143 | 1600 | 50.89 | 0 |
| read-heavy | write_back | 400.00 | 0.78 | 1.61 | 4743 | 3143 | 1600 | 50.89 | 0 |
| balanced | cache_aside | 399.68 | 1.16 | 1.91 | 6995 | 2995 | 4000 | 25.12 | 0 |
| balanced | write_through | 399.57 | 1.07 | 1.88 | 5999 | 1999 | 4000 | 50.02 | 0 |
| balanced | write_back | 400.00 | 0.74 | 1.63 | 5999 | 1999 | 4000 | 50.02 | 0 |
| write-heavy | cache_aside | 399.75 | 1.29 | 1.90 | 7816 | 1416 | 6400 | 11.50 | 0 |
| write-heavy | write_through | 399.61 | 1.24 | 1.91 | 7202 | 802 | 6400 | 49.88 | 0 |
| write-heavy | write_back | 400.02 | 0.67 | 1.46 | 7202 | 802 | 6400 | 49.88 | 0 |

## Write-Back Buffer Behavior

| Scenario | Throughput (req/sec) | Queue max | Queue avg | Flushed items | Flush batches |
|---|---:|---:|---:|---:|---:|
| read-heavy | 400.00 | 35 | 12.03 | 1600 | 88 |
| balanced | 400.00 | 70 | 28.38 | 4000 | 141 |
| write-heavy | 400.02 | 104 | 45.69 | 6400 | 159 |

## Auto Conclusions

- Best for read-heavy: `write_back` (max throughput, tiebreak by latency).
- Best for balanced: `write_back` (max throughput, tiebreak by latency).
- Best for write-heavy: `write_back` (max throughput, tiebreak by latency).
- For write-back, monitor queue growth (`Queue max/avg`): the larger the queue, the stronger delayed DB sync effect.
