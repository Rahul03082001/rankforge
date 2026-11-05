"""Local production-container startup/restart check; never targets unrelated containers."""
import json
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "http://127.0.0.1:7860"
READY_TIMEOUT_SECONDS = 50
EXPECTED_DOCUMENTS = 57638
EXPECTED_MODES = ["bm25", "dense", "hybrid", "ltr"]


def status():
    with urllib.request.urlopen(BASE + "/api/status", timeout=3) as r:
        return json.load(r)


def wait_until_ready(deadline):
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(BASE + "/health/ready", timeout=2) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(0.25)
    raise RuntimeError("Production restart did not become ready")


before = status()
start = time.perf_counter()
subprocess.run(["docker", "compose", "restart", "web"], check=True)
wait_until_ready(time.monotonic() + READY_TIMEOUT_SECONDS)
after = status()

# The restarted container must serve the same artifacts, not merely come up.
assert before["bundle_version"] == after["bundle_version"]
assert after["documents"] == EXPECTED_DOCUMENTS
assert after["available_modes"] == EXPECTED_MODES

record = {
    "restart_to_ready_seconds": time.perf_counter() - start,
    "same_bundle": True,
    "bundle_version": after["bundle_version"],
    "documents": after["documents"],
    "available_modes": after["available_modes"],
    "measurement": (
        "docker compose restart invocation through successful readiness poll; "
        "includes Docker restart overhead"
    ),
}
Path("reports/restart.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2))
