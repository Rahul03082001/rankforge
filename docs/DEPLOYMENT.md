# Public deployment — live

RankForge is publicly available at **https://rankforge-hg5yrz427q-ue.a.run.app**.

| Item | Verified status |
| --- | --- |
| Provider | Google Cloud Run, us-east1 |
| Project | <project-id> |
| Service / current revision | rankforge / rankforge-00003-nfp |
| Public access | HTTPS, no login required |
| Corpus and search | 57,638 FiQA documents; BM25, dense, hybrid, actual trained XGBoost LTR |
| Bundle SHA-256 | c9453e52b2c88ac41813ec0e71ec875b6311eb9405759f297bc826b896e39330 |
| Runtime | Linux AMD64, one CPU, 1 GiB RAM, one worker |
| Scaling | Minimum zero; maximum one instance; request-based billing |
| HTTP concurrency | Eight requests; the application still permits only one search inference at a time |
| Startup | CPU boost enabled; /health/ready startup probe |
| Runtime identity | rankforge-runtime, created without project roles |
| Billing | Existing unupgraded Free Trial; no paid upgrade performed |
| Trial expiry shown in console | February 2, 2027 |
| Alternate Google URL | https://rankforge-<project-number>.us-east1.run.app |

## Verification

- Built the CPU-only AMD64 image locally. All four real search modes passed offline under one CPU and 1 GiB/no-swap; local execution used emulation.
- Uploaded only the allowlisted 45-file application release, including the validated offline bundle and matching reports. Archive SHA-256 matched in Cloud Shell.
- Rebuilt natively in the authorized Cloud Shell and repeated offline inference before pushing to the project's private Artifact Registry repository.
- Unauthenticated external HTTPS checks passed before and after deploying a fresh revision: readiness, 57,638-document status, all four retrieval modes, complete source text, matching evaluation reports, and expected 422/404 errors.
- Public browser acceptance passed: keyboard search, source heading focus, back-to-results focus restoration, all four comparison columns, and both evaluation tables.
- The initial restart-check revision `rankforge-00002-gfh` became ready and served 100% of traffic. Its bundle checksum is unchanged. This verifies a new instance starting from the packaged release; it does not establish a long-term uptime guarantee or measure a later idle-to-active cold start.

Evidence: `reports/deployment.json`, `reports/public-smoke.json`, `reports/public-restart-smoke.json`, `reports/public-browser-check.json`, `reports/cloudrun-image-check.json`, and `reports/public-search.jpg`.

The initial configuration allowed only one HTTP request and disabled startup CPU boost. A public browser request returned HTTP 500; Cloud Logging reported that it waited too long for an available instance. The service was updated to HTTP concurrency eight with startup CPU boost, retaining the one-instance limit. Public API and browser checks passed after the new revision became ready.

## Benchmark page rename — November 4, 2026

Renamed the navigation, breadcrumb, and page heading to **Benchmark result**, with an explanation that the tables contain saved development/test averages and that current-query rankings appear in Search explorer or Compare modes. The reviewed frontend source SHA-256 matched in Cloud Shell before building.

Revision `rankforge-00003-nfp` serves 100% of traffic using image `us-east1-docker.pkg.dev/<project-id>/rankforge/web:benchmark-9a8fc57a`. Existing runtime settings were retained. The local production build, public API checks for all four search modes, and public browser inspection of the renamed page and both benchmark tables passed. Bundle SHA-256 is unchanged.

Evidence: `reports/public-benchmark-rename-smoke.json`, `reports/public-benchmark-browser-check.json`, and `reports/public-benchmark-result.jpg`.

## Cost and availability

The user requested no additional hosting charges. The console showed $300 of Free Trial credit before deployment. No paid account upgrade was performed, and the separate Google AI Pro monthly credit claim has not been verified.

Google states that an unupgraded Free Trial does not bill the user. Resources stop when the credit is exhausted or the trial expires. This deployment is therefore time-limited free hosting, not perpetual free hosting. Do not upgrade billing without explicit user approval.

https://docs.cloud.google.com/free/docs/free-cloud-features

Scale-to-zero reduces idle consumption, but the first request after inactivity can be slower while the model loads. Maximum instance limits and budget alerts are not monetary spending caps. Startup CPU boost consumes trial credit while starting. Artifact Registry storage can also consume credit. A later paid account needs its own approved cost controls.

## Rebuild and redeploy

`Dockerfile.cloudrun` uses PyTorch 2.6.0's official CPU wheel and XGBoost CPU 2.1.4. It includes the existing model, indexes, original texts, and ranker; there are no startup downloads or training. The original ARM64 local Dockerfile remains available for local development.

Create a new staging directory (the script refuses to overwrite an existing one):

```sh
docker compose run --rm tools python scripts/prepare_host_upload.py --provider cloudrun --output .deploy/cloudrun-next
```

Upload only that staged release to the authorized Google Cloud Shell. From its root:

```sh
bash scripts/deploy_cloudrun.sh <project-id> us-east1
```

The script enables the required APIs, uses a private image repository and dedicated runtime identity, builds and verifies the image, publishes Cloud Run, and checks the actual returned HTTPS endpoint. It never upgrades billing. For new accounts, verify free-trial status or approved costs before running it. Use a new image tag when changing application source so rollback remains reproducible; the current script tag is derived from the bundle hash.

Recheck from outside Google Cloud:

```sh
python3 scripts/public_smoke.py --url https://rankforge-hg5yrz427q-ue.a.run.app
```

## Remaining non-deployment review

- Human VoiceOver/zoom review remains pending. Automated accessibility and keyboard tests passed locally; public keyboard/source navigation was checked. No WCAG certification is claimed.
- The selected model's upstream weight license remains unspecified; see DATA.md. No license clarification was obtained during deployment.
- Source has not been committed or pushed to a Git repository. Deployment used an explicit application archive.

Railway was an earlier candidate, but no Railway resource or paid subscription was created. The 512 MiB test failed at startup, so that resource tier was not used.
