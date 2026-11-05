"""Closed-loop HTTP benchmark; cold request separated from warmed requests."""
import argparse
import concurrent.futures
import json
import platform
import time
from collections import Counter
from pathlib import Path

import httpx
import numpy as np

QUERIES = [
    "interest rates and bond prices",
    "index fund expenses",
    "retirement savings",
    "mortgage interest",
]
WARMUP_REQUESTS = 10
# Percentiles beyond the median need a reasonable sample to mean anything.
MIN_TAIL_SAMPLES = 100

p = argparse.ArgumentParser()
p.add_argument("--url", default="http://localhost:7860")
p.add_argument("--requests", type=int, default=1000)
p.add_argument("--concurrency", type=int, default=1)
p.add_argument("--output", default="reports/benchmark.json")
a = p.parse_args()

client = httpx.Client(base_url=a.url, timeout=60)
status = client.get("/api/status").json()


def one(i):
    """Issue one LTR search and return (milliseconds, status code)."""
    start = time.perf_counter()
    try:
        params = {"q": QUERIES[i % len(QUERIES)], "mode": "ltr"}
        code = client.get("/api/search", params=params).status_code
    except httpx.HTTPError:
        code = 0
    return (time.perf_counter() - start) * 1000, code


cold = one(0)
for i in range(WARMUP_REQUESTS):
    one(i)

start = time.perf_counter()
with concurrent.futures.ThreadPoolExecutor(max_workers=a.concurrency) as pool:
    rows = list(pool.map(one, range(a.requests)))
elapsed = time.perf_counter() - start

success = [ms for ms, code in rows if code == 200]
errors = len(rows) - len(success)
has_tail = len(success) >= MIN_TAIL_SAMPLES

latency = {}
if success:
    latency = {
        "p50": float(np.percentile(success, 50)),
        "p95": float(np.percentile(success, 95)) if has_tail else None,
        "p99": float(np.percentile(success, 99)) if has_tail else None,
    }

report = {
    "workload": "closed-loop; fixed four-query cycle; LTR; ten warmups",
    "requests": a.requests,
    "concurrency": a.concurrency,
    "elapsed_seconds": elapsed,
    # Achieved QPS counts fast rejections too, so it is not search capacity.
    "achieved_qps": a.requests / elapsed,
    "successful_qps": len(success) / elapsed,
    "errors": errors,
    "error_rate": errors / len(rows),
    "latency_sample_count": len(success),
    "status_counts": dict(Counter(str(code) for _, code in rows)),
    "tail_estimate_note": (
        "100 or more successful latency samples"
        if has_tail
        else "p95/p99 suppressed when fewer than 100 successes"
    ),
    "first_request_ms": cold[0],
    "first_request_status": cold[1],
    "cold_start_note": (
        "First request in this process, not measured container startup. "
        "Model startup measured separately."
    ),
    "latency_success_ms": latency,
    "corpus_documents": status["documents"],
    "bundle_version": status["bundle_version"],
    "client_hardware": platform.platform(),
    "server_hardware": "Record Docker CPU/memory allocation in release notes",
}

Path(a.output).parent.mkdir(parents=True, exist_ok=True)
Path(a.output).write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
