# RankForge — decision log

Created: 2026-11-03

These are implementation decisions for **RankForge — Hybrid Search & Learning-to-Rank Platform**. Local implementation, measured experiment evidence, and public deployment are recorded below. Human accessibility review remains pending.

## Maintaining this log

Use design status `Proposed`, `Accepted`, or `Superseded`. Separately record implementation as `Not started`, `Implemented, not verified`, or `Verified`. Accept a design when it is chosen; mark it verified only after the relevant check actually runs.

Record real file paths, test names, commands, results, and commits. Leave unknown values as `Pending`. Preserve prior reasoning when a decision changes: add a new entry and reference it from the old status. Do not invent approvals, issue IDs, collaborators, or measured improvements.

## Index

| ID | Decision | Design status | Implementation |
| --- | --- | --- | --- |
| ADR-001 | Complete hybrid retrieval and learned ranking before distributed extensions | Accepted | Verified |
| ADR-002 | Use one API/container serving a compiled React frontend | Accepted | Verified |
| ADR-003 | Use FiQA documents and official query splits | Accepted | Verified |
| ADR-004 | Use BM25S with fixed preprocessing | Accepted | Verified |
| ADR-005 | Start dense retrieval with a small model and exact FAISS search | Accepted | Verified |
| ADR-006 | Fuse rank positions with reciprocal rank fusion | Accepted | Verified |
| ADR-007 | Train XGBoost on query-grouped retrieved candidates | Accepted | Verified |
| ADR-008 | Ship immutable, compatible index/model artifacts | Accepted | Verified |
| ADR-009 | Evaluate correctness, relevance, and latency separately | Accepted | Verified |
| ADR-010 | Treat accessibility as tested behavior with documented limits | Accepted | Verified |
| ADR-011 | Deploy a portable public Docker app within an approved budget | Accepted | Verified |

## ADR-001: Two complete stages before distributed extensions

- Date/status: 2026-11-03; Accepted; Verified.
- Context: A complete, explainable portfolio project is the immediate goal.
- Options: Build custom C++ storage, distributed serving, and ML simultaneously; finish retrieval and learned ranking first.
- Choice: Stage 1 is a working evaluated search app. Stage 2 adds a real trained reranker. Distributed shards, replication, compression, and hedging follow later.
- Reason: Each stage has a demonstrable user outcome and isolates a smaller set of failure modes.
- Trade-off: This version does not demonstrate distributed serving or C++ implementation. Completion time depends on actual build and debugging work.
- Evidence/commit: Implemented baseline retrieval and real XGBoost in backend/rankforge; full FiQA reports in reports/fiqa-test-evaluation.json. Integration and correctness tests pass; public deployment remains pending. Source commit: 78f060a.

## ADR-002: One deployment origin

- Date/status: 2026-11-03; Accepted; Verified.
- Context: Public deployment should avoid unnecessary services and configuration.
- Options: Separate frontend/backend/database hosting; one FastAPI container serving compiled React assets and APIs.
- Choice: React/TypeScript frontend, Python/FastAPI API, local read-only document metadata, and saved retrieval files in one portable container.
- Reason: A single public origin simplifies routing, deployment, and reproduction.
- Trade-off: This is a single-node service. An external database is deferred because the corpus is fixed; runtime model memory must be measured before selecting workers and hosting.
- Evidence/commit: FastAPI serves the compiled React application and APIs. Dockerfile packages the offline model and bundle; one worker and one inference permit. Final image smoke/memory evidence: docs/VERIFICATION.md. Source commit: 78f060a.

## ADR-003: FiQA with preserved document IDs and official splits

- Date/status: 2026-11-03; Accepted; Verified.
- Context: Ranking needs relevance judgments and repeatable evaluation.
- Options: Synthetic judgments; a public retrieval benchmark with train/development/test qrels.
- Choice: BEIR FiQA-2018, one corpus document per retrieval unit, official query splits, recorded checksum/revision, and dataset attribution.
- Reason: Consistent document IDs preserve the meaning of the judgments and enable like-for-like evaluation.
- Trade-off: FiQA covers archived financial Q&A, not general web search. Missing original URLs/titles remain missing; long-text truncation must be documented. Debug subsets do not establish full-corpus performance.
- Evidence/commit: Official BEIR archive checksum and inventory: docs/DATA.md, data/fiqa/audit.json. Audit found 57,638 documents and disjoint 5,500/500/648 query splits. Source commit: 78f060a.

## ADR-004: Existing BM25 implementation

- Date/status: 2026-11-03; Accepted; Verified.
- Context: A correct lexical baseline is needed before adding ranking complexity.
- Options: Custom C++ index; Java/Lucene tooling; BM25S in the existing Python service.
- Choice: BM25S with explicitly configured variant, parameters, tokenization, stop words, and stemming.
- Reason: Existing indexing/scoring infrastructure keeps the first implementation focused on retrieval integration and evaluation.
- Trade-off: The project uses BM25 software; it does not claim a custom inverted index or custom compression. Published baseline comparisons require matched settings.
- Evidence/commit: tests/test_core.py::test_bm25_lucene_hand_calculation verifies the configured convention. Empty/OOV, stable source mapping, and reload tests pass. See docs/RANKING.md. Source commit: 78f060a.

## ADR-005: Small embedding model with exact dense search

- Date/status: 2026-11-03; Accepted; Verified.
- Context: Semantic retrieval should fit local and modest hosted CPU resources.
- Options: Hosted embedding API; a small local retrieval model; a larger model with accelerator requirements.
- Choice: Start with `sentence-transformers/multi-qa-MiniLM-L6-cos-v1`, pinned to an actual model revision, normalized float32 vectors, and FAISS `IndexFlatIP`.
- Reason: Exact nearest-neighbor search gives a straightforward correctness baseline at FiQA's corpus size.
- Trade-off: Model choice affects relevance and memory/latency. HNSW is deferred until an experiment justifies approximate search. Record any model substitution and rebuild dependent artifacts.
- Evidence/commit: Real model revision b207367332321f8e44f96e224ef15bc607f4dbf0; normalized 384-dimensional IndexFlatIP. Known-vector and real-model integration pass. Release token limit 256; initial fixture used 512. Source commit: 78f060a.

## ADR-006: Reciprocal rank fusion

- Date/status: 2026-11-03; Accepted; Verified.
- Context: BM25 and dense similarity scores have different numerical scales.
- Options: Raw-score addition; fitted score weighting; fusion using rank positions.
- Choice: Retrieve up to 100 candidates per method, deduplicate source IDs, and use RRF with constant 60, one-based ranks, zero contribution for missing ranks, and deterministic ties.
- Reason: Rank fusion provides a clear baseline without learning score calibration from test data.
- Trade-off: RRF discards some score magnitude information; it is not guaranteed to beat both component retrievers on every query.
- Evidence/commit: tests/test_core.py::test_rrf_missing_duplicate_and_ties passes; full-corpus evaluation includes measured hybrid outcomes. Constant 60, 100 candidates, deterministic source-ID ties. Source commit: 78f060a.

## ADR-007: Query-grouped XGBoost reranking

- Date/status: 2026-11-03; Accepted; Verified.
- Context: Learned ranking needs genuine relevance supervision and identical training/serving features.
- Options: Heuristic reranking; a cross-encoder; XGBoost with a small interpretable feature set.
- Choice: `XGBRanker` with `rank:ndcg`, trained on grouped training-query candidates. Use development queries for tuning and frozen test queries for final evaluation.
- Reason: This builds on existing XGBoost knowledge and supports inspecting how lexical and semantic evidence affect rankings.
- Trade-off: Incomplete judgments and groups without retrieved positives limit training. Reordering the same top 100 cannot improve Recall@100. An improvement in nDCG is an experimental outcome, not a promised feature.
- Evidence/commit: Trained on 5,500 train queries; 4,583 useful groups retained and 917 without positives excluded. Depth 5 selected on 500 dev queries. Frozen test nDCG@10 0.3813515 versus hybrid 0.3393844. Recall@100 identical. Leakage and prediction-equivalence tests pass. Source commit: 78f060a.

## ADR-008: Immutable versioned artifacts

- Date/status: 2026-11-03; Accepted; Verified.
- Context: A model paired with the wrong index or document map can return plausible but incorrect results.
- Options: Rebuild everything during startup; reuse mutable files; select a validated immutable artifact bundle.
- Choice: Save corpus identifiers, ordered IDs, tokenizer configuration, embedding revision/dimension, BM25/FAISS artifacts, ranker/feature schema, and checksums together.
- Reason: Explicit compatibility checks make a deployed result traceable and reproducible.
- Trade-off: Releases need artifact distribution and storage. Ephemeral host disk cannot be the only copy. Initial downloads can cause cold-start delay.
- Evidence/commit: Bundles are built in separate temporary directories then renamed after validation. Checksums cover complete file inventory; feature/schema and mapping tests reject mismatch. Release packaging explicitly includes generated assets. Source commit: 78f060a.

## ADR-009: Separate engineering and relevance evidence

- Date/status: 2026-11-03; Accepted; Verified.
- Context: A fast service, a high retrieval metric, and correct code are different claims.
- Options: One headline score; separate unit/integration tests, retrieval evaluation, and latency measurements.
- Choice: Use deterministic correctness fixtures; standard nDCG@10/MRR@10/Recall@100 evaluation; and documented workload/hardware latency tests.
- Reason: Each claim has evidence appropriate to what it asserts.
- Trade-off: More than one report is needed. Small debug subsets and local Docker benchmarks must be labeled as such; CI should not repeat full training on every change.
- Evidence/commit: 13 backend tests pass, including real models. reports/fiqa-{dev,test}-evaluation.json retain per-query results. Latency and image evidence are recorded separately in docs/VERIFICATION.md. Source commit: 78f060a.

## ADR-010: Accessibility backed by specific tests

- Date/status: 2026-11-03; Accepted; Verified.
- Context: The search flow must work for keyboard and assistive-technology users.
- Options: Custom interactive controls with ad hoc behavior; native semantic controls with tested focus/status handling.
- Choice: Native controls, visible focus, keyboard navigation, readable contrast, accessible loading/errors, and live result announcements. Combine Playwright/axe checks with a manual VoiceOver checklist.
- Reason: Accessibility is part of the user experience and directly relevant to the target role.
- Trade-off: Automated checks cannot prove full WCAG conformance. Manual checks remain pending until actually performed.
- Evidence/commit: Native controls, live results, request cancellation, and focus handling implemented. Browser/axe findings corrected. See docs/VERIFICATION.md for final outcomes; manual VoiceOver remains pending. Source commit: 78f060a.

## ADR-011: Portable public deployment with an explicit budget

- Date/status: 2026-11-03; Accepted; Verified.
- Context: The portfolio needs a real public search URL, while hosting resources and costs are not yet chosen.
- Options: A compatible Docker host using an existing account; a Hugging Face Docker Space if eligible; local-only operation until hosting is available.
- Choice: Produce one portable image first, measure resource requirements, and select an authorized host. Complete deployment only after public smoke tests pass.
- Reason: Portability separates application correctness from account/provider constraints.
- Trade-off: Hosting may require an account, billing, or paid resources. Provider eligibility and prices must be verified when a host is selected. A local URL or hosted screenshot is not a live backend.
- Evidence/commit: Portable Docker packaging is implemented. Deployed publicly on 2026-11-04 to Google Cloud Run at https://rankforge-hg5yrz427q-ue.a.run.app, revision `rankforge-00003-nfp`, one CPU and 1 GiB, scale-to-zero, maximum one instance, on an existing unupgraded Free Trial; no paid upgrade was performed. Unauthenticated external checks passed for readiness, all four search modes, source-prefix consistency, expected invalid-query and missing-document responses, and two evaluation reports matching the served bundle c9453e52; the checks were repeated after a fresh revision. Public browser checks passed for keyboard search, source heading focus and back-focus restoration, all four comparison columns, and both benchmark tables. No hosted load-capacity or idle-to-active cold-start measurement is claimed, and the local axe/Playwright results were not rerun remotely. Hosting ends when the trial shown as expiring 2027-02-02 lapses. Evidence: reports/deployment.json, reports/public-smoke.json, reports/public-restart-smoke.json, reports/public-browser-check.json, reports/cloudrun-image-check.json, and docs/VERIFICATION.md. Source commit: 78f060a.

## Future-entry template

```markdown
## ADR-012: <decision title>

- Date/status: <actual date>; Proposed | Accepted | Superseded; implementation status.
- Context: <business or engineering problem>.
- Options: <real alternatives>.
- Choice: <chosen approach>.
- Reason: <why it fits this project's constraints>.
- Trade-off: <costs, limits, and deferred work>.
- Evidence/commit: <actual files, tests, commands, observations, and commit; or Pending>.
```
