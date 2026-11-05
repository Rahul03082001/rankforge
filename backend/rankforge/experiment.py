import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import ir_measures
from ir_measures import nDCG, RR, Recall
from xgboost import XGBRanker

from .core import Engine, FEATURES, digest, read_json, write_json, seal
from .data import load_data, qrels

MEASURES = [nDCG @ 10, RR @ 10, Recall @ 100]

CANDIDATE_DEPTHS = [3, 5]
RANKER_SEED = 42
RANKER_PARAMETERS = {
    "objective": "rank:ndcg",
    "n_estimators": 80,
    "learning_rate": 0.05,
    "random_state": RANKER_SEED,
    "n_jobs": 4,
    "tree_method": "hist",
}
CANDIDATE_POLICY = (
    "100 per retriever; RRF 60; LTR reorders top 100 hybrid; "
    "positive relevance >=1"
)


def metrics(labels, rankings):
    judgments = [ir_measures.Qrel(q, d, r) for q, d, r in labels]

    # Rank-position scores preserve deterministic tie ordering for the evaluator.
    runs = []
    for q, rows in rankings.items():
        for rank, (d, _) in enumerate(rows):
            runs.append(ir_measures.ScoredDoc(q, d, float(len(rows) - rank)))

    ids = sorted({q for q, _, _ in labels})
    per_query = {q: {str(m): 0.0 for m in MEASURES} for q in ids}
    for item in ir_measures.iter_calc(MEASURES, judgments, runs):
        per_query[item.query_id][str(item.measure)] = item.value

    means = {
        str(m): float(np.mean([per_query[q][str(m)] for q in ids]))
        for m in MEASURES
    }
    return {"aggregate": means, "per_query": per_query}


def query_vectors(engine, queries, ids):
    return engine.encoder.encode(
        [queries[q] for q in ids],
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=True,
        batch_size=64,
    )


def _training_groups(engine, queries, train_ids, lookup):
    """Build query-grouped feature blocks, recording why groups are dropped.

    A group is only useful when it holds a retrieved positive and at least two
    distinct labels; otherwise there is nothing for a ranker to order.
    """
    arrays, targets, groups = [], [], []
    excluded = {"no_positive": [], "no_comparison": []}

    for q, vector in zip(train_ids, query_vectors(engine, queries, train_ids)):
        _, ids, x = engine.prepare(queries[q], vector)
        y = [lookup.get((q, i), 0) for i in ids]
        if not any(y):
            excluded["no_positive"].append(q)
        elif len(set(y)) < 2:
            excluded["no_comparison"].append(q)
        else:
            arrays.append(x)
            targets.extend(y)
            groups.append(len(y))

    return arrays, targets, groups, excluded


def _select_depth(x, targets, groups, development, dev):
    """Fit one ranker per candidate depth and keep the best on dev nDCG@10."""
    trials, best, best_score = [], None, -1

    for depth in CANDIDATE_DEPTHS:
        model = XGBRanker(max_depth=depth, **RANKER_PARAMETERS)
        model.fit(x, np.array(targets), group=groups)

        rankings = {}
        for q, (_, ids, f) in dev.items():
            scores = map(float, model.predict(f))
            rankings[q] = sorted(zip(ids, scores), key=lambda r: (-r[1], r[0]))

        score = metrics(development, rankings)["aggregate"]["nDCG@10"]
        trials.append({"max_depth": depth, "dev_nDCG@10": score})
        print(f"depth={depth} development nDCG@10={score:.5f}", flush=True)

        if score > best_score:
            best, best_score = model, score

    return best, trials


def train(data, bundle, output):
    output = Path(output)
    if output.exists():
        raise ValueError("Choose a new immutable output bundle")

    engine = Engine(bundle)
    _, queries = load_data(data)
    if digest(Path(data) / "corpus.jsonl") != engine.manifest["corpus_sha256"]:
        raise ValueError("Training corpus differs from index")

    labels = qrels(data, "train")
    development = qrels(data, "dev")
    train_ids = sorted({q for q, _, _ in labels})
    dev_ids = sorted({q for q, _, _ in development})
    if set(train_ids) & set(dev_ids):
        raise ValueError("Training/development overlap")

    lookup = {(q, d): r for q, d, r in labels}
    arrays, targets, groups, excluded = _training_groups(
        engine, queries, train_ids, lookup
    )
    if not groups:
        raise ValueError("No useful training groups")

    x = np.concatenate(arrays)
    dev = {
        q: engine.prepare(queries[q], v)
        for q, v in zip(dev_ids, query_vectors(engine, queries, dev_ids))
    }
    best, trials = _select_depth(x, targets, groups, development, dev)

    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=".training-", dir=output.parent))
    try:
        shutil.copytree(bundle, temp, dirs_exist_ok=True)
        best.save_model(temp / "ranker.json")

        metadata = dict(engine.manifest)
        metadata.pop("files")
        metadata["ranker"] = {
            "features": FEATURES,
            "schema": 1,
            "seed": RANKER_SEED,
            "parameters": {
                k: v
                for k, v in best.get_params().items()
                if v is not None and k != "missing"
            },
            "train_queries": len(train_ids),
            "retained_groups": len(groups),
            "dev_queries": len(dev_ids),
            "excluded": excluded,
            "trials": trials,
            "train_qrels_sha256": digest(Path(data) / "qrels/train.tsv"),
            "dev_qrels_sha256": digest(Path(data) / "qrels/dev.tsv"),
            "unjudged_label": 0,
            "base_bundle": engine.version,
        }
        seal(temp, metadata)

        # Reload from disk and confirm the saved ranker predicts identically.
        reloaded = Engine(temp, encoder=engine.encoder)
        np.testing.assert_allclose(
            best.predict(x[:100]), reloaded.ranker.predict(x[:100])
        )
        os.rename(temp, output)
        print(f"Trained and validated: {output}", flush=True)
    except BaseException:
        shutil.rmtree(temp)
        raise


def evaluate(data, bundle, split, output, frozen=None):
    engine = Engine(bundle)
    if digest(Path(data) / "corpus.jsonl") != engine.manifest["corpus_sha256"]:
        raise ValueError("Evaluation corpus differs from index")

    # Test labels may only be opened against a bundle that was frozen first.
    if split == "test":
        if frozen is None or read_json(frozen)["bundle_sha256"] != engine.version:
            raise ValueError("Test evaluation requires a matching frozen release file")

    _, queries = load_data(data)
    labels = qrels(data, split)
    ids = sorted({q for q, _, _ in labels})

    rankings = {m: {} for m in engine.modes}
    vectors = query_vectors(engine, queries, ids)
    for n, (q, v) in enumerate(zip(ids, vectors), 1):
        results = engine.prepare(queries[q], v)[0]
        for m in rankings:
            rankings[m][q] = results[m]
        if n % 100 == 0:
            print(f"Evaluated {n}/{len(ids)} queries", flush=True)

    report = {
        "created": datetime.now(timezone.utc).isoformat(),
        "profile": engine.manifest["provenance"]["profile"],
        "split": split,
        "queries": len(ids),
        "query_ids": ids,
        "documents": len(engine.ids),
        "bundle_sha256": engine.version,
        "model_revision": engine.manifest["revision"],
        "qrels_sha256": digest(Path(data) / "qrels" / (split + ".tsv")),
        "candidate_policy": CANDIDATE_POLICY,
        "metrics": {m: metrics(labels, r) for m, r in rankings.items()},
    }
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    write_json(output, report)
    print(json_summary(report), flush=True)


def json_summary(report):
    aggregates = {m: r["aggregate"] for m, r in report["metrics"].items()}
    return json.dumps(aggregates, indent=2)
