"""Unauthenticated smoke checks; HTTPS required unless explicitly testing locally."""
import argparse
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--url", required=True)
p.add_argument("--allow-http", action="store_true")
p.add_argument("--output", default="reports/public-smoke.json")
a = p.parse_args()
base = a.url.rstrip("/")
if not base.startswith("https://") and not a.allow_http:
    raise ValueError("Public verification requires HTTPS; --allow-http is for local testing only")

def get(path, expected=200):
    try:
        response = urllib.request.urlopen(base + path, timeout=45)
        status = response.status
        body = response.read().decode()
    except urllib.error.HTTPError as exc:
        status, body = exc.code, exc.read().decode()
    assert status == expected, (path, status, expected)
    return body

get("/")
assert json.loads(get("/health/live"))["live"]
assert json.loads(get("/health/ready"))["ready"]
status = json.loads(get("/api/status"))
assert status["ready"]
assert set(status["available_modes"]) == {"bm25", "dense", "hybrid", "ltr"}
checks = {}
for mode in ["bm25", "dense", "hybrid", "ltr"]:
    params = urllib.parse.urlencode({"q": "interest rates", "mode": mode, "k": 3})
    data = json.loads(get("/api/search?" + params))
    assert data["results"] and data["bundle_version"] == status["bundle_version"]
    hit = data["results"][0]
    doc = json.loads(get("/api/documents/" + urllib.parse.quote(hit["id"], safe="")))
    assert doc["id"] == hit["id"] and doc["text"].startswith(hit["excerpt"])
    checks[mode] = {"first_document": hit["id"], "server_ms": data["server_ms"]}
get("/api/search?q=test&mode=invalid", expected=422)
get("/api/documents/not-a-valid-document-id", expected=404)
reports = json.loads(get("/api/evaluation"))["reports"]
assert reports and all(r["bundle_sha256"] == status["bundle_version"] for r in reports)
result = {"verified_at": datetime.now(timezone.utc).isoformat(), "url": base,
          "scope": "public HTTPS" if base.startswith("https://") else "local HTTP only",
          "authenticated": False, "documents": status["documents"],
          "bundle_sha256": status["bundle_version"], "modes": checks,
          "evaluation_reports": len(reports), "result": "passed"}
Path(a.output).parent.mkdir(parents=True, exist_ok=True)
Path(a.output).write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
