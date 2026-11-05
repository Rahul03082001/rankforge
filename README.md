# RankForge
### Hybrid search & learning-to-rank, made inspectable.

[![correctness](https://github.com/Rahul03082001/rankforge/actions/workflows/ci.yml/badge.svg)](https://github.com/Rahul03082001/rankforge/actions/workflows/ci.yml)

Compare keyword retrieval, semantic retrieval, reciprocal rank fusion, and supervised XGBoost reranking over the same financial Q&A collection. Open a source document, compare rankings, and inspect measured evaluation results.

**Live demo: [Open RankForge](https://rankforge-hg5yrz427q-ue.a.run.app).** All four modes work over 57,638 FiQA documents. Public HTTPS/API, browser navigation, comparison, evaluation, and fresh-revision checks passed. The local release also passed 13 backend and 5 browser checks. Hosting uses an unupgraded Google Cloud Free Trial, shown as expiring February 2, 2027; no paid upgrade was performed. See [deployment details](docs/DEPLOYMENT.md) and [verification evidence](docs/VERIFICATION.md).

## Architecture

React + TypeScript → same-origin FastAPI → BM25S / Sentence Transformers + FAISS → RRF → XGBoost.

One process loads one immutable bundle. It includes original document text, sorted source IDs, lexical index, exact dense index, offline embedding model, trained ranker, feature metadata, and checksums. The app does not generate answers, use an external database, or claim distributed serving.

## Requirements

Docker with Compose, internet for initial public dataset/model/package downloads, and sufficient disk (allow 8 GB for images, data, and release artifacts). Native Linux ARM64 is verified on Apple Silicon. No x86 emulation is required. Node 22+ is optional for frontend development; production builds it in a container.

Run commands from this repository.

## Small fixture demo

```sh
docker compose build tools
docker compose run --rm tools sh scripts/pipeline.sh fixture
docker compose run --rm -e TEST_BUNDLE=artifacts/fixture-ltr tools pytest -q
docker compose run --rm tools python scripts/package_release.py --bundle artifacts/fixture-ltr
docker compose up --build -d web
```

Open http://localhost:7860. All four modes use genuine retrieval and a trained model. Fixture metrics are **correctness/development examples**, not a FiQA benchmark. The image bundles artifacts and can run offline.

Outputs are immutable: rerunning with the same output directory fails. Use new output paths, or archive an earlier generated output before a deliberate rebuild. The release directory is prepared explicitly, not committed or magically supplied by a remote build.

## Full FiQA experiment

```sh
docker compose run --rm tools python -m rankforge.cli download --data data
docker compose run --rm tools python -m rankforge.cli audit --data data/fiqa
docker compose run --rm tools python -m rankforge.cli index --data data/fiqa --output artifacts/fiqa --revision b207367332321f8e44f96e224ef15bc607f4dbf0
docker compose run --rm tools python -m rankforge.cli train --data data/fiqa --bundle artifacts/fiqa --output artifacts/fiqa-ltr
docker compose run --rm tools python -m rankforge.cli evaluate --data data/fiqa --bundle artifacts/fiqa-ltr --split dev --output reports/fiqa-dev-evaluation.json
docker compose run --rm tools python -m rankforge.cli freeze --bundle artifacts/fiqa-ltr --output reports/fiqa-frozen.json
docker compose run --rm tools python -m rankforge.cli evaluate --data data/fiqa --bundle artifacts/fiqa-ltr --split test --frozen reports/fiqa-frozen.json --output reports/fiqa-test-evaluation.json
```

Or run `docker compose run --rm tools sh scripts/pipeline.sh fiqa` from clean output directories. Indexing is a visible CPU-intensive batch job; it never runs during a web request or service startup.

Training reads only train/dev qrels. The independent audit checks split IDs first. Two tree depths are selected using development nDCG@10. Final test evaluation requires a frozen manifest hash. See [data provenance](docs/DATA.md), [ranking conventions](docs/RANKING.md), and [decisions](docs/DECISIONS.md).

To package the full corpus, archive any earlier generated release folder, then:

```sh
docker compose run --rm tools python scripts/package_release.py --bundle artifacts/fiqa-ltr
docker compose up --build -d web
```

The image uses /app/artifacts/fiqa-ltr internally; its manifest identifies the profile actually packaged.

## Tests and development

```sh
docker compose run --rm tools pytest -q -m 'not integration'
docker compose run --rm -e TEST_BUNDLE=artifacts/fiqa-ltr tools pytest -q -m integration
npm ci --prefix frontend
npm run build --prefix frontend
cd frontend
npx playwright install chromium
npm test
```

Browser tests expect http://127.0.0.1:7860; set BASE_URL to test another deployment. They cover search, keyboard modes, source focus/back, request races, errors, comparison, evaluation, mobile layout, and axe. Manual VoiceOver checks are separate in [docs/ACCESSIBILITY.md](docs/ACCESSIBILITY.md).

For development with a selected bundle:

```sh
docker compose run --rm -p 7860:7860 -e RANKFORGE_BUNDLE=artifacts/fiqa-ltr tools uvicorn rankforge.api:app --host 0.0.0.0 --port 7860
```

In another terminal, `npm run dev --prefix frontend`. Vite proxies APIs. For a production-like preview, build the frontend and use the API port directly.

## API

| Endpoint | Purpose |
| --- | --- |
| /api/search?q=...&mode=hybrid&k=10 | Ranked excerpts; bm25, dense, hybrid, ltr |
| /api/documents/{id} | Complete source text and attribution |
| /api/status | Readiness, modes, corpus/model metadata |
| /api/evaluation | Reports matching the loaded bundle hash |
| /health/live | Process liveness |
| /health/ready | Validated bundle loaded |
| /docs | OpenAPI explorer |

Queries: 1–500 characters, nonblank; result limits: 1–100. Unknown modes are rejected. Missing artifacts/ranker return 503. One inference permit bounds memory; concurrent expensive requests receive 429 with Retry-After. Comparison runs modes sequentially. Server processing time excludes browser/network overhead.

## Latency measurement

```sh
docker compose run --rm tools python scripts/benchmark.py --url http://host.docker.internal:7860 --requests 1000 --concurrency 1 --output reports/benchmark-warm.json
docker compose run --rm tools python scripts/benchmark.py --url http://host.docker.internal:7860 --requests 1000 --concurrency 4 --output reports/benchmark-concurrent.json
```

Closed-loop workloads, four repeated queries, ten warmups. Reports include successful/total QPS, successful-request p50/p95/p99, errors, first request, and bundle identity. These are not open-loop capacity or cold-start measurements. Record Docker resources/startup separately.

## Release and demo

See [deployment](docs/DEPLOYMENT.md) and [five-minute demo](docs/DEMO.md). The public Cloud Run service scales to zero and is capped at one instance. Hosting stops when the unupgraded trial expires or its credits are exhausted. The `correctness` workflow runs on every push and covers backend tests, the frontend build, and the fixture pipeline with browser checks; the full-corpus evaluation workflow is manual.

Application/authored fixture: MIT. Dataset/model licenses are separate. [AI assistance and human review](docs/AI_USAGE.md).
