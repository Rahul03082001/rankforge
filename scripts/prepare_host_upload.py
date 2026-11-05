"""Stage an explicit, self-contained upload; never upload the whole workspace."""
import argparse
import shutil
from pathlib import Path
from rankforge.core import validate, digest, read_json, write_json

# Shared by every provider ignore-file this script writes.
IGNORE_PATTERNS = ".git\n**/node_modules\n**/__pycache__\n**/.DS_Store\n.env*\n"

p = argparse.ArgumentParser()
p.add_argument("--bundle", default="artifacts/fiqa-ltr")
p.add_argument("--output", default=".deploy/railway")
p.add_argument("--provider", choices=["railway", "cloudrun"], default="railway")
a = p.parse_args()
root = Path(__file__).resolve().parents[1]
bundle = (root / a.bundle).resolve()
out = (root / a.output).resolve()
if not out.is_relative_to(root / ".deploy"):
    raise ValueError("Staging output must be under this project's .deploy directory")
if out.exists():
    raise ValueError("Staged upload already exists; choose a new output path")
manifest = validate(bundle)
if not manifest.get("ranker"):
    raise ValueError("Public release requires the actual trained ranker")
version = digest(bundle / "manifest.json")
out.mkdir(parents=True)
files = ["Dockerfile", "requirements.lock", "railway.json", "LICENSE", "docs/DATA.md",
         "frontend/package.json", "frontend/package-lock.json", "frontend/tsconfig.json",
         "frontend/vite.config.ts", "frontend/index.html"]
files += [str(p.relative_to(root)) for p in sorted((root / "backend").rglob("*.py"))]
frontend_sources = sorted((root / "frontend/src").rglob("*"))
files += [str(p.relative_to(root)) for p in frontend_sources if p.is_file()]
for name in files:
    source = root / name
    if source.is_symlink():
        raise ValueError("Symlinks are not accepted in upload sources")
    target = out / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
if a.provider == "cloudrun":
    shutil.copy2(root / "Dockerfile.cloudrun", out / "Dockerfile")
    (out / "railway.json").unlink()
    (out / "scripts").mkdir(exist_ok=True)
    for script in ["deploy_cloudrun.sh", "public_smoke.py"]:
        shutil.copy2(root / "scripts" / script, out / "scripts" / script)
for name in [*manifest["files"], "manifest.json"]:
    target = out / "release/bundle" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(bundle / name, target)
for report in sorted((root / "reports").glob("*evaluation*.json")):
    if read_json(report).get("bundle_sha256") == version:
        target = out / "release/reports" / report.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(report, target)
(out / ".dockerignore").write_text(IGNORE_PATTERNS)
(out / ".railwayignore").write_text(IGNORE_PATTERNS)
if a.provider == "cloudrun":
    (out / ".railwayignore").unlink()
    (out / ".gcloudignore").write_text(IGNORE_PATTERNS)
validate(out / "release/bundle")
inventory = {str(p.relative_to(out)): digest(p) for p in sorted(out.rglob("*")) if p.is_file()}
size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
write_json(root / "reports/host-upload.json", {
    "status": "prepared locally; not uploaded", "provider_candidate": a.provider,
    "directory": str(out.relative_to(root)), "bundle_sha256": version,
    "total_bytes": size, "files": inventory})
print(f"Validated {len(inventory)} upload files ({size / 1024**2:.1f} MiB). No upload performed.")
