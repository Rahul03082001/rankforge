import math

import bm25s
import faiss
import numpy as np
import pytest
from fastapi.testclient import TestClient

from rankforge.core import (
    BM25,
    FEATURES,
    Engine,
    features,
    fuse,
    lexical_scores,
    read_json,
    seal,
    validate,
    write_json,
)
from rankforge.data import fixture, audit
from rankforge.build import build
from rankforge.api import create_app


class FakeEncoder:
    """Explicit unit-test double; never used by the production CLI."""

    def encode(self, texts, **kwargs):
        vectors = [
            [1, 0, 0] if "savings" in t.lower() else [0, 1, 0]
            for t in texts
        ]
        return np.array(vectors, dtype="float32")


@pytest.fixture
def bundle(tmp_path):
    data = tmp_path / "data"
    fixture(data)
    path = tmp_path / "bundle"
    build(data, path, encoder=FakeEncoder())
    return data, path


def test_bm25_lucene_hand_calculation():
    corpus = ["cat cat dog", "dog", "bird"]
    bm = bm25s.BM25(**BM25)
    bm.index(bm25s.tokenize(corpus, stopwords=[]))

    # BM25S Lucene convention omits the (k1+1) numerator multiplier.
    idf = math.log(1 + (3 - 1 + 0.5) / (1 + 0.5))
    average_length = 5 / 3
    expected = idf * 2 / (2 + 1.5 * (0.25 + 0.75 * 3 / average_length))

    assert bm.get_scores(["cat"])[0] == pytest.approx(expected, rel=1e-6)
    assert np.all(bm.get_scores(["zzzzz"]) == 0)
    assert np.all(lexical_scores(bm, "!!!") == 0)


def test_known_faiss_vectors():
    index = faiss.IndexFlatIP(2)
    index.add(np.array([[1, 0], [0, 1], [-1, 0]], dtype="float32"))

    scores, positions = index.search(np.array([[1, 0]], dtype="float32"), 3)

    assert positions.tolist() == [[0, 1, 2]]
    assert scores.tolist() == [[1, 0, -1]]


def test_rrf_missing_duplicate_and_ties():
    result = dict(fuse(["a", "a", "b"], ["c", "b"]))

    # A repeated ID scores once per ranking, at its first position.
    assert result["a"] == 1 / 61
    assert result["b"] == 1 / 63 + 1 / 62
    # Equal fused scores fall back to lexicographic source ID.
    assert fuse(["b"], ["a"]) == [("a", 1 / 61), ("b", 1 / 61)]


def test_mapping_reload_and_rebuild(bundle, tmp_path):
    data, path = bundle
    engine = Engine(path, encoder=FakeEncoder())

    assert engine.ids == sorted(engine.documents)
    assert engine.search("compound", "bm25", 10)[0]["id"] == "savings"
    assert engine.search("zzzzz", "bm25", 10) == []
    assert engine.search("!!!", "hybrid", 10) == []

    # A second build of the same data must be interchangeable with the first.
    new = tmp_path / "second"
    build(data, new, encoder=FakeEncoder())
    rebuilt = Engine(new, encoder=FakeEncoder())

    assert engine.ids == rebuilt.ids
    assert engine.search("savings", "hybrid", 10) == rebuilt.search("savings", "hybrid", 10)

    with pytest.raises(ValueError, match="exists"):
        build(data, new, encoder=FakeEncoder())


def test_split_separation_and_mapping(bundle):
    data, _ = bundle

    assert audit(data)["splits"] == {"train": 8, "dev": 2, "test": 2}

    with (data / "qrels/dev.tsv").open("a") as f:
        f.write("tr1\tsavings\t1\n")
    with pytest.raises(AssertionError, match="Overlapping"):
        audit(data)


def test_shared_features_missing_rank_is_not_missing_score():
    documents = {"x": {"text": "savings savings account"}}

    x = features(
        "savings money", ["x"], documents,
        {"x": 0.3}, {"x": -0.2},
        {}, {"x": 2}, {"x": 1 / 62},
    )

    # An absent BM25 rank contributes 0, while a negative cosine stays negative.
    np.testing.assert_allclose(x[0], [0.3, -0.2, 0, 0.5, 1 / 62, 3, 0.5])


def test_checksum_and_version(bundle):
    _, path = bundle
    manifest = read_json(path / "manifest.json")

    manifest["schema"] = 99
    write_json(path / "manifest.json", manifest)
    with pytest.raises(ValueError, match="schema"):
        validate(path)

    manifest["schema"] = 1
    write_json(path / "manifest.json", manifest)
    with (path / "ids.json").open("a") as f:
        f.write(" ")
    with pytest.raises(ValueError, match="checksum"):
        validate(path)


def test_mapping_mismatch_even_with_fresh_checksum(bundle):
    _, path = bundle

    # Resealing repairs the checksums, so only the mapping check can catch this.
    ids = read_json(path / "ids.json")
    ids.reverse()
    write_json(path / "ids.json", ids)
    seal(path, read_json(path / "manifest.json"))

    with pytest.raises(ValueError, match="mapping"):
        Engine(path, encoder=FakeEncoder())


def test_api_validation_and_readiness(bundle):
    _, path = bundle

    with TestClient(create_app(engine=Engine(path, encoder=FakeEncoder()))) as c:
        assert c.get("/health/ready").status_code == 200

        rejected = ["q=", "q=++", "q=a&mode=unknown", "q=a&k=101", "q=" + "a" * 501]
        for query in rejected:
            assert c.get("/api/search?" + query).status_code == 422

        # This bundle has no ranker, so the learned mode is unavailable.
        assert c.get("/api/search?q=savings&mode=ltr").status_code == 503

        body = c.get("/api/search?q=compound&mode=bm25").json()
        assert body["results"][0]["id"] == "savings"
        assert c.get("/api/documents/savings").json()["text"].startswith("A savings")
        assert c.get("/api/documents/unknown").status_code == 404
        assert c.get("/api/not-real").status_code == 404

    with TestClient(create_app(bundle="/missing")) as c:
        assert c.get("/health/live").status_code == 200
        assert c.get("/health/ready").status_code == 503
        assert c.get("/api/status").json()["available_modes"] == []


def test_standard_metrics():
    from rankforge.experiment import metrics

    result = metrics([("q", "a", 1)], {"q": [("b", 10), ("a", 9)]})["aggregate"]

    assert result["nDCG@10"] == pytest.approx(1 / math.log2(3))
    assert result["RR@10"] == 0.5
    assert result["R@100"] == 1


def test_training_reads_no_test_labels_and_reloads_shared_features(
    bundle, tmp_path, monkeypatch
):
    from rankforge import experiment

    data, path = bundle
    calls = []
    original = experiment.qrels

    def guarded_qrels(data, split):
        assert split in ["train", "dev"], "Training attempted to load test labels"
        calls.append(split)
        return original(data, split)

    monkeypatch.setattr(experiment, "qrels", guarded_qrels)
    monkeypatch.setattr(
        experiment,
        "Engine",
        lambda p, encoder=None: Engine(p, encoder=encoder or FakeEncoder()),
    )

    output = tmp_path / "trained"
    experiment.train(data, path, output)

    engine = Engine(output, encoder=FakeEncoder())
    rankings, ids, x = engine.prepare("compound interest")

    assert calls == ["train", "dev"]
    assert engine.ranker is not None
    assert {i for i, _ in rankings["hybrid"]} == {i for i, _ in rankings["ltr"]}
    assert engine.manifest["ranker"]["features"] == FEATURES

    # Serving ranking must be exactly the shared feature function's model prediction.
    expected = sorted(
        zip(ids, map(float, engine.ranker.predict(x))),
        key=lambda r: (-r[1], r[0]),
    )
    assert rankings["ltr"] == expected


def test_concurrency_is_bounded_and_recovers(bundle):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    _, path = bundle
    engine = Engine(path, encoder=FakeEncoder())
    entered, release = threading.Event(), threading.Event()
    original = engine.search

    def blocking(*args):
        entered.set()
        assert release.wait(timeout=5)
        return original(*args)

    engine.search = blocking

    with TestClient(create_app(engine=engine)) as c, ThreadPoolExecutor() as pool:
        first = pool.submit(c.get, "/api/search?q=compound&mode=bm25")
        assert entered.wait(timeout=5)

        # The permit is held, so a second caller is rejected rather than queued.
        second = c.get("/api/search?q=compound&mode=bm25")
        assert second.status_code == 429
        assert second.headers["Retry-After"] == "1"

        release.set()
        assert first.result().status_code == 200
        # The permit is returned, so the service recovers.
        assert c.get("/api/search?q=compound&mode=bm25").status_code == 200
