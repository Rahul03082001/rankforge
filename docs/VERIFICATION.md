# Verified release — local 2026-11-03, public 2026-11-04

## Application and correctness
- React/TypeScript production build: passed, including the Node 22 Docker build.
- Frontend dependency audit after updating Vite/Playwright: zero reported vulnerabilities.
- pytest: **13 passed** in 10.22 seconds; two dependency deprecation warnings. Includes real full-corpus embedding/ranker integration; hand-calculated BM25; known FAISS vectors; missing ranks/ties; stable mapping and reindexing; split separation and guarded training label reads; shared feature/prediction equivalence; artifact corruption/schema/mapping checks; API validation/readiness; bounded concurrent requests.
- Playwright Chromium: **4 passed** on the fixture application. **5 passed on the final full-corpus production image in 5.8 seconds**, including a missing-artifact/null-metadata regression. Includes keyboard search/modes, source focus/back, stale responses, errors, comparison/evaluation, mobile overflow, and axe.
- Public GitHub Actions execution: not run. Workflow files provided.
- Manual VoiceOver/zoom audit: pending human review; no blanket WCAG conformance claim.
- Git repository initialized; no commit or remote publication.

## Full FiQA experiment
57,638 source documents; 5,500 train / 500 dev / 648 test queries. Official split IDs disjoint, source IDs valid.

Model revision: b207367332321f8e44f96e224ef15bc607f4dbf0. Dense dimension 384; 256-token truncation; exact normalized inner product. Full indexing completed in 23m46s on the local CPU configuration, excluding download/build time.

Training retained 4,583 groups, excluding 917 with no retrieved positive; zero excluded for lack of label contrast. Depth 5 selected using dev nDCG@10 .3966946 versus .3960183 for depth 3. Test labels were opened by evaluation only after freeze.

| Mode | Test nDCG@10 | Test MRR@10 | Test Recall@100 |
| --- | ---: | ---: | ---: |
| BM25 | 0.233734 | 0.288965 | 0.506752 |
| Dense | 0.359883 | 0.437885 | 0.675021 |
| Hybrid | 0.339384 | 0.414493 | 0.685606 |
| LTR | 0.381351 | 0.458118 | 0.685606 |

Full aggregate/per-query reports: reports/fiqa-dev-evaluation.json and reports/fiqa-test-evaluation.json. No significance assessment; no claim of improvement on every query. Hybrid underperforms dense on nDCG here. Fixture metrics are separately labeled correctness examples.

Frozen bundle SHA-256:
c9453e52b2c88ac41813ec0e71ec875b6311eb9405759f297bc826b896e39330

## Packaging and restart
- Multi-stage Docker build succeeded on native linux/arm64, Python 3.11, one non-root runtime worker.
- Bundle approximately 259 MiB; image approximately 2.48 GB (uncompressed reported image size).
- Production image ran with **network disabled and no mounted files**; loaded all 57,638 documents and all four modes and returned an LTR result.
- docker compose restart → readiness: **4.074 seconds**, including Docker restart overhead. Same bundle identity and all modes after restart. reports/restart.json.
- Port 7860; healthy container running locally. Public Cloud Run deployment was added November 4; see below.
- Observed server memory during warm benchmark: **588.3 MiB**, not a worst-case peak. Docker allocated 10 CPUs / 7.748 GiB; OMP_NUM_THREADS=4. Another unrelated container was running; numbers are local measurements.
- Choose hosted resources with headroom; the observed resident footprint is not a guaranteed hosting minimum.

## Closed-loop request benchmark
1,000 warm LTR requests, concurrency 1, four-query cycle after ten warmups:
- 54.89 successful requests/second.
- p50 13.17 ms; p95 31.04 ms; p99 45.51 ms end-to-end from a second Docker container.
- Zero errors; 1,000 successful latency samples.
- First request 61.59 ms, not model cold-start latency.
- reports/benchmark-warm.json.

Concurrency 4, 1,000 requests without client backoff:
- 992 rejected requests, 8 successes; 99.2% error rate. HTTP status counts: {'200': 8, '429': 992}.
- Total response throughput includes fast rejections and is **not successful search capacity**.
- Too few successes for meaningful tail estimates; the updated report suppresses p95/p99 rather than presenting unstable tails.
- This small service admits one inference at a time and returns 429/Retry-After when busy. High-concurrency hosting needs additional admission/queueing and capacity work.
- reports/benchmark-concurrent.json.

## Remaining release work
Clarification of the model weight license (see DATA.md), manual accessibility, and human source review remain. Public deployment and its checks are now complete as described below.

Final image ID: sha256:cf41c0af697208b79a6c91195dcc067f478c760c16405c22d02ab44f711a1798 (native ARM64).

## Public Cloud Run release — 2026-11-04

- Live: https://rankforge-hg5yrz427q-ue.a.run.app
- Final ready revision `rankforge-00002-gfh`, serving 100% of traffic; one CPU, 1 GiB memory, HTTP concurrency eight, minimum zero/maximum one instance, startup CPU boost, request-based billing. Existing unupgraded free trial; no paid billing upgrade.
- CPU-only AMD64 image built and checked locally with emulation, then rebuilt and checked natively in Cloud Shell. All four inference modes passed offline under a 1 GiB/no-swap limit.
- External unauthenticated checks passed initially and after a fresh revision: homepage, readiness, all four search modes, source-prefix consistency, expected invalid-query/missing-document responses, and two reports matching the same immutable bundle.
- Public browser checks passed for keyboard search, source heading focus and back-focus restoration, all four comparison columns, and dev/test evaluation tables. Screenshot: reports/public-search.jpg. The automated axe/Playwright results above are local results; they were not rerun remotely.
- An initial request encountered a Cloud Run available-instance queue timeout. Enabled startup CPU boost and changed HTTP concurrency from one to eight, retaining the single search-inference permit. Checks passed after the new revision was ready.
- Evidence: reports/deployment.json, reports/public-smoke.json, reports/public-restart-smoke.json, reports/public-browser-check.json, reports/cloudrun-image-check.json. No new hosted load-capacity or idle-to-active cold-start benchmark is claimed.
