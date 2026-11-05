#!/usr/bin/env bash
# Run from the explicitly staged release in an authorized Google Cloud Shell.
# This uses the existing billing account; it never upgrades a free trial.
set -euo pipefail
rankforge_project="${1:?Supply the authorized Google Cloud project ID}"
rankforge_region="${2:-us-east1}"
rankforge_bundle="c9453e52b2c88ac41813ec0e71ec875b6311eb9405759f297bc826b896e39330"
rankforge_image="${rankforge_region}-docker.pkg.dev/${rankforge_project}/rankforge/web:${rankforge_bundle:0:12}"
rankforge_identity="rankforge-runtime@${rankforge_project}.iam.gserviceaccount.com"

test "$(sha256sum release/bundle/manifest.json | cut -d ' ' -f1)" = "$rankforge_bundle"
gcloud services enable run.googleapis.com artifactregistry.googleapis.com iam.googleapis.com --project="$rankforge_project" --quiet
if ! gcloud artifacts repositories describe rankforge --location="$rankforge_region" --project="$rankforge_project" >/dev/null 2>&1; then
  gcloud artifacts repositories create rankforge --repository-format=docker --location="$rankforge_region" --project="$rankforge_project" --description="RankForge application images" --quiet
fi
if ! gcloud iam service-accounts describe "$rankforge_identity" --project="$rankforge_project" >/dev/null 2>&1; then
  gcloud iam service-accounts create rankforge-runtime --display-name="RankForge runtime (no project roles)" --project="$rankforge_project" --quiet
fi

# Build natively in Cloud Shell and verify actual inference before publishing.
docker build --platform linux/amd64 -t "$rankforge_image" .
docker run --rm --network none --memory 1g --memory-swap 1g --cpus 1 --entrypoint python "$rankforge_image" -c 'from rankforge.core import Engine; import os; e=Engine(os.environ["RANKFORGE_BUNDLE"]); assert len(e.ids)==57638; assert set(e.modes)=={"bm25","dense","hybrid","ltr"}; [print(mode, e.search("how to diversify investments", mode, 3)[0]["id"]) for mode in e.modes]; print("Verified",e.version)'
gcloud auth configure-docker "${rankforge_region}-docker.pkg.dev" --quiet
docker push "$rankforge_image"

gcloud run deploy rankforge \
  --project="$rankforge_project" --region="$rankforge_region" \
  --image="$rankforge_image" --service-account="$rankforge_identity" \
  --allow-unauthenticated --ingress=all --port=8080 \
  --cpu=1 --memory=1Gi --concurrency=8 --min=0 --max=1 --max-instances=1 \
  --cpu-throttling --cpu-boost --execution-environment=gen2 --timeout=120 \
  --startup-probe='httpGet.path=/health/ready,httpGet.port=8080,periodSeconds=10,timeoutSeconds=5,failureThreshold=24' \
  --labels=app=rankforge --quiet
gcloud run services describe rankforge --project="$rankforge_project" --region="$rankforge_region" --format=json > cloudrun-service.json
rankforge_url="$(gcloud run services describe rankforge --project="$rankforge_project" --region="$rankforge_region" --format='value(status.url)')"
python3 scripts/public_smoke.py --url "$rankforge_url" --output public-smoke.json
printf 'RankForge deployed and checked: %s\n' "$rankforge_url"
