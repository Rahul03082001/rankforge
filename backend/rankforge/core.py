"""Shared retrieval and feature code. No relevance labels enter this module."""
import hashlib
import json
import re
from pathlib import Path

import bm25s
import faiss
import numpy as np

SCHEMA = 1
FEATURES = [
    "bm25",
    "cosine",
    "reciprocal_bm25_rank",
    "reciprocal_dense_rank",
    "rrf",
    "document_tokens",
    "query_overlap",
]
TOKEN_PATTERN = r"[a-z0-9]+"
BM25 = {"method": "lucene", "k1": 1.5, "b": 0.75}
MODEL = "sentence-transformers/multi-qa-MiniLM-L6-cos-v1"
MODEL_REVISION = "b207367332321f8e44f96e224ef15bc607f4dbf0"

# Candidates kept per retriever, and the reciprocal-rank-fusion constant.
# validate() rejects any bundle whose manifest disagrees with these values,
# so fuse() and prepare() must read them from here rather than repeat literals.
CANDIDATE_COUNT = 100
RRF_CONSTANT = 60

REQUIRED_FILES = {
    "documents.json",
    "ids.json",
    "dense.faiss",
    "bm25/params.index.json",
}


def tokens(text):
    return re.findall(TOKEN_PATTERN, text.lower())


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    text = json.dumps(value, indent=2, sort_keys=True, allow_nan=False)
    Path(path).write_text(text + "\n")


def inventory(path):
    """Checksum every bundle file except the manifest that records them."""
    path = Path(path)
    return {
        str(p.relative_to(path)): digest(p)
        for p in sorted(path.rglob("*"))
        if p.is_file() and p.name != "manifest.json"
    }


def seal(path, metadata):
    path = Path(path)
    metadata = dict(metadata)
    metadata["schema"] = SCHEMA
    metadata["files"] = inventory(path)
    write_json(path / "manifest.json", metadata)
    return metadata


def validate(path):
    path = Path(path)
    m = read_json(path / "manifest.json")

    if m["schema"] != SCHEMA or m["features"] != FEATURES:
        raise ValueError("Incompatible artifact or feature schema")

    if (
        m["bm25"] != BM25
        or m["token_pattern"] != TOKEN_PATTERN
        or m["candidate_count"] != CANDIDATE_COUNT
        or m["rrf_constant"] != RRF_CONSTANT
    ):
        raise ValueError("Incompatible retrieval configuration")

    if not REQUIRED_FILES.issubset(m["files"]):
        raise ValueError("Incomplete bundle")

    ranker = m.get("ranker")
    if ranker and (ranker["schema"] != 1 or ranker["features"] != FEATURES):
        raise ValueError("Incompatible ranker feature schema")

    actual_files = {
        str(p.relative_to(path))
        for p in path.rglob("*")
        if p.is_file() and p.name != "manifest.json"
    }
    if actual_files != set(m["files"]):
        raise ValueError("Artifact inventory mismatch")

    if ranker and "ranker.json" not in m["files"]:
        raise ValueError("Missing ranker checksum")

    root = path.resolve()
    for name, checksum in m["files"].items():
        p = (path / name).resolve()
        if not p.is_relative_to(root) or not p.is_file() or digest(p) != checksum:
            raise ValueError("Artifact checksum mismatch: " + name)

    return m


def lexical_scores(index, query):
    terms = tokens(query)
    if not terms:
        return np.zeros(index.scores["num_docs"], dtype=np.float32)
    return index.get_scores(terms)


def fuse(*rankings):
    """Reciprocal rank fusion over one-based ranks, deduplicating each input."""
    result = {}
    for ranking in rankings:
        seen = set()
        for rank, doc_id in enumerate(ranking, 1):
            if doc_id in seen:
                continue
            result[doc_id] = result.get(doc_id, 0.0) + 1.0 / (RRF_CONSTANT + rank)
            seen.add(doc_id)
    return sorted(result.items(), key=lambda x: (-x[1], x[0]))


def features(query, candidate_ids, documents, raw_bm25, raw_dense,
             bm_ranks, dense_ranks, rrf):
    """Build the feature matrix shared by training and serving.

    A missing rank means the retriever never returned the document, which is
    different from a low raw score; absent ranks contribute zero.
    """
    query_terms = set(tokens(query))
    rows = []
    for i in candidate_ids:
        document_terms = tokens(documents[i]["text"])
        overlap = len(query_terms & set(document_terms)) / max(1, len(query_terms))
        rows.append([
            raw_bm25[i],
            raw_dense[i],
            1 / bm_ranks[i] if i in bm_ranks else 0,
            1 / dense_ranks[i] if i in dense_ranks else 0,
            rrf[i],
            len(document_terms),
            overlap,
        ])
    return np.asarray(rows, dtype=np.float32)


class Engine:
    def __init__(self, path, encoder=None):
        self.path = Path(path)
        self.manifest = validate(path)
        self.version = digest(self.path / "manifest.json")
        self.ids = read_json(self.path / "ids.json")
        self.documents = read_json(self.path / "documents.json")

        if len(set(self.ids)) != len(self.ids) or self.ids != sorted(self.documents):
            raise ValueError("Invalid document ID mapping")
        self.positions = {v: i for i, v in enumerate(self.ids)}

        self.bm25 = bm25s.BM25.load(str(self.path / "bm25"), load_corpus=False)
        self.dense = faiss.read_index(str(self.path / "dense.faiss"))

        if (
            self.dense.ntotal != len(self.ids)
            or self.dense.d != self.manifest["dimension"]
            or len(self.ids) != self.manifest["documents"]
        ):
            raise ValueError("Index dimensions or mapping mismatch")
        if self.bm25.scores["num_docs"] != len(self.ids):
            raise ValueError("BM25 mapping mismatch")

        self.encoder = encoder if encoder is not None else self._load_encoder()
        self.ranker = self._load_ranker()

    def _load_encoder(self):
        if self.manifest["encoder"] != "sentence-transformers":
            raise ValueError("Test-vector artifacts cannot serve semantic search")
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(
            str(self.path / "model"), device="cpu", local_files_only=True
        )

    def _load_ranker(self):
        if not self.manifest.get("ranker"):
            return None
        from xgboost import XGBRanker

        ranker = XGBRanker()
        ranker.load_model(self.path / "ranker.json")
        if ranker.n_features_in_ != len(FEATURES):
            raise ValueError("Ranker feature count mismatch")
        return ranker

    @property
    def modes(self):
        base = ["bm25", "dense", "hybrid"]
        return base + (["ltr"] if self.ranker is not None else [])

    def _lexical_candidates(self, lexical):
        """Top lexical positions by score, breaking ties on source ID."""
        hits = np.flatnonzero(lexical > 0)
        ordered = sorted(hits, key=lambda i: (-float(lexical[i]), self.ids[i]))
        return ordered[:CANDIDATE_COUNT]

    def _dense_candidates(self, vector):
        """Exact search; sort all boundary ties by source ID for stable ordering."""
        depth = min(CANDIDATE_COUNT + 1, len(self.ids))
        similarities, positions = self.dense.search(vector, depth)

        boundary_ties = (
            len(self.ids) > CANDIDATE_COUNT
            and similarities[0][CANDIDATE_COUNT - 1] == similarities[0][CANDIDATE_COUNT]
        )
        if boundary_ties:
            similarities, positions = self.dense.search(vector, len(self.ids))

        pairs = zip(positions[0], similarities[0])
        ordered = sorted(pairs, key=lambda x: (-float(x[1]), self.ids[x[0]]))
        return ordered[:CANDIDATE_COUNT]

    def prepare(self, query, vector=None):
        lexical = lexical_scores(self.bm25, query)
        order = self._lexical_candidates(lexical)
        bm_ids = [self.ids[i] for i in order]

        if vector is None:
            vector = self.encoder.encode(
                [query], normalize_embeddings=True, convert_to_numpy=True
            )
        vector = np.asarray(vector, dtype="float32").reshape(1, -1)

        dense_order = self._dense_candidates(vector)
        dense_ids = [self.ids[i] for i, _ in dense_order]

        fused = fuse(bm_ids, dense_ids)[:CANDIDATE_COUNT]
        candidate_ids = [i for i, _ in fused]

        raw_bm = {i: float(lexical[self.positions[i]]) for i in candidate_ids}
        raw_dense = {
            i: float(np.dot(self.dense.reconstruct(self.positions[i]), vector[0]))
            for i in candidate_ids
        }
        x = features(
            query,
            candidate_ids,
            self.documents,
            raw_bm,
            raw_dense,
            {i: r for r, i in enumerate(bm_ids, 1)},
            {i: r for r, i in enumerate(dense_ids, 1)},
            dict(fused),
        )

        rankings = {
            "bm25": [(self.ids[i], float(lexical[i])) for i in order],
            "dense": [(self.ids[i], float(s)) for i, s in dense_order],
            "hybrid": fused,
        }
        if self.ranker is not None and candidate_ids:
            scores = map(float, self.ranker.predict(x))
            rankings["ltr"] = sorted(
                zip(candidate_ids, scores), key=lambda r: (-r[1], r[0])
            )
        return rankings, candidate_ids, x

    def _excerpt(self, doc_id, score, mode):
        document = self.documents[doc_id]
        return {
            "id": doc_id,
            "title": document["title"],
            "excerpt": document["text"][:450],
            "score": score,
            "mode": mode,
        }

    def search(self, query, mode, k):
        if mode not in self.modes:
            raise ValueError("Requested model is unavailable")
        if not tokens(query):
            return []

        if mode == "bm25":
            # Lexical-only requests skip embedding and fusion entirely.
            scores = lexical_scores(self.bm25, query)
            hits = np.flatnonzero(scores > 0)
            positions = sorted(hits, key=lambda i: (-float(scores[i]), self.ids[i]))[:k]
            ranking = [(self.ids[i], float(scores[i])) for i in positions]
        else:
            ranking = self.prepare(query)[0][mode][:k]

        return [self._excerpt(doc_id, score, mode) for doc_id, score in ranking]
