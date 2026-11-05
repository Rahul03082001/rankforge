# Retrieval and ranking conventions

Executable constants: backend/rankforge/core.py. Readable configuration: configs/retrieval.json. Changing tokenizer, score convention, model, truncation, or candidate policy requires rebuilding dependent artifacts.

## Lexical
BM25S 0.2.6, Lucene variant, k1=1.5, b=0.75. Lowercase ASCII alphanumeric regex [a-z0-9]+, no stop words, no stemming. Both query and document use this processing. Punctuation-only queries return no results. The exact score convention is:

log(1 + (N-df+0.5)/(df+0.5)) * tf / (tf + k1*(1-b+b*length/average_length))

BM25S omits the global (k1+1) multiplier used in some presentations. A hand-calculated test checks this convention. Zero scores are excluded; ties use lexicographic source IDs.

## Dense
sentence-transformers/multi-qa-MiniLM-L6-cos-v1 at b207367332321f8e44f96e224ef15bc607f4dbf0, 384 dimensions. The model card uses the same unprefixed encoding for questions/passages. Float32, L2-normalized vectors with FAISS IndexFlatIP give exact cosine ranking.

Release builds truncate at 256 model tokens including special tokens. This CPU/memory trade-off is saved in the model/manifest. Complete text remains available; BM25 indexes complete text. The initial fixture used the original 512-token limit, truthfully recorded in its manifest.

Search requests 101 positions; if the 100th/101st scores tie, all positions are considered to resolve the cutoff by source ID. This is an exact baseline, not an approximate index.

## Fusion and features
Retrieve up to 100 per source. Deduplicate by ID and sum 1/(60+rank), one-based ranks, zero for absent sources. Retain 100. Constant 60 is not tuned on test labels.

Shared training/serving features in order:
1. Actual BM25 score.
2. Actual dense cosine, reconstructed from the index even when absent from dense top 100.
3. Reciprocal BM25 rank, zero when absent.
4. Reciprocal dense rank, zero when absent.
5. RRF score.
6. Lexical document token count.
7. Unique query-term overlap fraction.

Ranks and raw similarities have different missing-value meanings. Labels/query IDs are not predictive features. Feature schema and source bundle identity are saved. The ranker is genuine XGBoost JSON.

## Training and evaluation
Retrieved candidates are grouped in sorted training-query ID order. Unjudged documents receive zero, a limitation of incomplete judgments. Groups without a retrieved positive or useful label contrast are excluded and recorded. No known positives are injected.

Depths 3 and 5 are compared using dev nDCG@10. Fixed: 80 trees, learning rate .05, seed 42, histogram trees, four CPU threads, rank:ndcg. Train/dev qrels are hashed; training never opens test qrels.

ir_measures calculates nDCG@10, reciprocal rank@10 (shown as MRR@10), Recall@100, relevance >=1. Rank-position scores preserve deterministic tie order. Reports retain per-query metrics, IDs, corpus/split counts, artifact hash, qrels hash, and model revision. UI reports must match the loaded bundle. Frozen test results must not guide tuning reported as the same experiment.

LTR reorders hybrid's 100 candidates: Recall@100 must match. Higher quality is a hypothesis, not a promise.
