# RankForge — AI assistance and human review

Record actual development assistance, not a retrospective claim that every part was generated or reviewed. This file supports explaining how AI improved the development workflow and how its output was checked.

## Planning entry — 2026-11-03

- Tool: ChatGPT.
- Task: Prepare the RankForge build prompt, proposed architecture, deployment requirements, and starter documentation.
- Output: This prompt kit. It is a specification, not implemented source code.
- Verification: Technical references were consulted and the kit's files were checked for internal consistency. Application tests, training, benchmarks, manual accessibility checks, and deployment have not run.
- Human review: Pending review by Rahul before or during implementation.
- Measured time savings: Not measured.

## Entry template

### <actual date> — <development task>

- AI tool/model, if known:
- What I asked it to do:
- Files or changes it proposed:
- What I accepted and why:
- What I changed or rejected and why:
- Actual tests or manual checks performed:
- Observed issue and correction, if any:
- Relevant commit or issue, if it exists:
- Remaining uncertainty:

Prefer a few concrete examples over a list of tools. Useful entries include detecting a query-split leak, fixing an incorrect RRF implementation, correcting an artifact-ID mapping, or repairing a keyboard interaction—but only record such incidents if they actually occur. Do not invent bugs, review effort, collaborators, or productivity percentages.

### 2026-11-03 — Implement and verify RankForge

- Tool: Codex in the desktop app. No subagents used; model identifier not independently inspected.
- Request: Build the project from RankForge_Prompt_Kit into the separate empty platform directory.
- Changes: React/TypeScript interface; FastAPI API; BM25S, Sentence Transformers/FAISS, RRF, and XGBoost; artifact CLI; train/dev/test experiment pipeline; pytest/Playwright/axe checks; Docker/CI; documentation.
- Verification: Real public FiQA archive downloaded and checksummed; official split mapping audited. Full corpus indexed using pinned model. Actual XGBoost trained; two depths selected on dev; test evaluated only after manifest freeze. Full reports are saved, not inferred.
- Observed corrections: BM25S rejects empty token lists, so the application guards them. A fixture expectation wrongly assumed the savings document must beat a shorter document for the single term “savings”; replaced that expectation with the discriminating “compound” query, preserving the hand-calculated score test. The evaluator's logging integration conflicted with root exception logging; switched to a named logger. XGBoost default NaN metadata broke JSON API status; serialized selected parameters and returned explicit public status metadata. Browser tests exposed contrast failures and focus timing before React had committed the document view; fixed colors and moved focus to a post-render effect.
- Actual checks: 13 backend checks pass including the real full-corpus embedding/ranker integration, training label-read guard, bounded concurrency, save/load predictions, corruption and split separation. Browser runs identified failures and were repeated after corrections; final outcomes are in VERIFICATION.md.
- Measured experiment: Test nDCG@10: BM25 .2337338, dense .3598827, hybrid .3393844, LTR .3813515. LTR/hybrid Recall@100 .6856058. These results are specific to this configuration; statistical significance has not been assessed.
- Choices: Native ARM64 containers, one worker, one bounded inference permit, 256-token release truncation, exact dense baseline. Initial 512-token full index attempt stopped before completion; only the completed 256-token corpus is reported.
- Human acceptance/review: Pending Rahul's review. No independent human code review, VoiceOver review, commit, public deployment, or measured productivity/time-saving claim.
- Remaining uncertainty: Provider account/budget and public deployment; manual accessibility; incomplete relevance judgments and possible embedding-pretraining overlap.

- Attribution verification correction: an initial documentation draft incorrectly described the model weights as Apache-2.0. Direct model metadata and its upstream missing-license discussion did not support that claim; corrected DATA.md to unspecified and recorded clarification before public release.

- Final UI review: caught a null metadata crash when artifacts are unavailable; made status metadata nullable, displayed the service reason, and added a browser regression. Final production-image browser suite: 5 passed in 5.8 seconds. Desktop and mobile screenshots inspected.

### 2026-11-03 — Public deployment preparation and free hosting assessment
- User requested public deployment and clarified a preference for free hosting.
- Prepared explicit allowlisted upload staging, Railway candidate configuration, and unauthenticated smoke-check script. Staging validation covered 44 files / 259.7 MiB; no upload or paid resource created.
- Smoke-check script passed against local production, including all four modes and source/evaluation consistency.
- Verified current provider documentation. Tested the current image under a 512 MiB/no-swap limit: startup OOM, exit 137. Kept the original service running.
- Oracle Always Free is a resource-compatible option, subject to account verification, capacity, and idle-resource policies. Account access remains missing. Manual VoiceOver explained as a human screen-reader usability check, not a deployment gate.

### 2026-11-04 — Google Cloud deployment
- User activated Google Cloud and authorized Cloud Shell credential access for deploying RankForge. The console showed an unupgraded $300 Free Trial expiring February 2, 2027. No paid upgrade was requested or performed.
- Added a Cloud Run Dockerfile using CPU-only PyTorch and XGBoost at the existing versions, explicit upload staging, and a deployment script with scale-to-zero and one-instance limits. The app runtime identity receives no project roles.
- Built the AMD64 image locally and checked all four actual search modes offline with 1 GiB/no-swap and one CPU. The same 57,638-document bundle hash was verified. This local check used emulation; the deployment script repeats it natively in Cloud Shell before publishing.
- Uploaded only the allowlisted 45-file release archive, 206,227,042 compressed bytes, and verified its SHA-256 in Cloud Shell. Google Cloud setup and the native build have started; public URL and final verification are pending.

- Deployment completed: https://rankforge-hg5yrz427q-ue.a.run.app, final revision rankforge-00002-gfh. Native offline inference and unauthenticated external API checks passed, including a fresh revision with the same bundle hash. Public browser search, comparison, source focus/back, and both evaluation tables passed.
- Corrected an initial Cloud Run queue timeout by enabling startup CPU boost and changing HTTP concurrency from one to eight; the bounded one-search inference gate remains. No paid billing upgrade. Deployment settings and evidence are recorded in DEPLOYMENT.md and reports/deployment.json.

### 2026-11-04 — Benchmark result clarification
- User requested renaming Evaluation to Benchmark result to distinguish saved benchmark metrics from current-query rankings. Updated navigation, breadcrumb, page heading, explanatory copy, existing browser-test locator, and demo notes.
- Local production build passed; local and public browser checks confirmed the renamed page and both development/test tables. Public API smoke checks passed for all four search modes after deploying revision rankforge-00003-nfp. The dataset/model bundle hash and runtime limits were retained. No paid account upgrade was performed.
