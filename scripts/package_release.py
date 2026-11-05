"""Prepare explicit Docker build assets, including the offline model."""
import argparse
import shutil
from pathlib import Path

from rankforge.core import validate, digest, read_json

p = argparse.ArgumentParser()
p.add_argument("--bundle", required=True)
p.add_argument("--output", default="release")
a = p.parse_args()

manifest = validate(a.bundle)
if not manifest.get("ranker"):
    raise ValueError("Release requires a genuine trained ranker")

out = Path(a.output)
if out.exists():
    raise ValueError("Release directory exists; select another output or archive it first")

shutil.copytree(a.bundle, out / "bundle")
(out / "reports").mkdir()

# Ship only the reports this exact bundle produced.
version = digest(Path(a.bundle) / "manifest.json")
for r in Path("reports").glob("*evaluation*.json"):
    if read_json(r).get("bundle_sha256") == version:
        shutil.copy2(r, out / "reports" / r.name)

print(f"Prepared offline Docker assets at {out}")
