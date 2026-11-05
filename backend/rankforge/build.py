import os
import shutil
import tempfile
from pathlib import Path

import bm25s
import faiss
import numpy as np

from .core import (
    BM25,
    CANDIDATE_COUNT,
    FEATURES,
    MODEL,
    MODEL_REVISION,
    RRF_CONSTANT,
    TOKEN_PATTERN,
    Engine,
    digest,
    read_json,
    seal,
    write_json,
)
from .data import load_data

MAX_SEQUENCE_LENGTH = 256
ENCODE_BATCH_SIZE = 64


def _build_encoder(temp, revision):
    """Load the pinned model and save it into the bundle for offline serving."""
    from sentence_transformers import SentenceTransformer

    print(f"Loading {MODEL}@{revision}", flush=True)
    encoder = SentenceTransformer(
        MODEL,
        revision=revision,
        device="cpu",
        model_kwargs={"attn_implementation": "sdpa"},
    )
    encoder.max_seq_length = MAX_SEQUENCE_LENGTH
    encoder.save(str(temp / "model"))
    return encoder


def build(data, output, revision=None, encoder=None):
    output = Path(output)
    if output.exists():
        raise ValueError("Output already exists; choose a new immutable bundle path")
    output.parent.mkdir(parents=True, exist_ok=True)

    # Build into a temporary directory and rename only after validation, so a
    # failed run can never leave a half-written bundle behind.
    temp = Path(tempfile.mkdtemp(prefix=".building-", dir=output.parent))
    try:
        docs, _ = load_data(data)
        ids = sorted(docs)
        texts = [docs[i]["text"] for i in ids]
        write_json(temp / "documents.json", docs)
        write_json(temp / "ids.json", ids)

        bm = bm25s.BM25(**BM25)
        bm.index(bm25s.tokenize(texts, stopwords=[], token_pattern=TOKEN_PATTERN))
        bm.save(str(temp / "bm25"))

        if encoder is None:
            revision = revision or MODEL_REVISION
            encoder = _build_encoder(temp, revision)
            kind = "sentence-transformers"
        else:
            kind = "test-vectors"

        vectors = encoder.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=True,
            batch_size=ENCODE_BATCH_SIZE,
        )
        vectors = np.asarray(vectors, dtype="float32")
        faiss.normalize_L2(vectors)
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        faiss.write_index(index, str(temp / "dense.faiss"))

        provenance = read_json(Path(data) / "provenance.json")
        metadata = {
            "features": FEATURES,
            "bm25": BM25,
            "token_pattern": TOKEN_PATTERN,
            "candidate_count": CANDIDATE_COUNT,
            "rrf_constant": RRF_CONSTANT,
            "model": MODEL,
            "revision": revision,
            "encoder": kind,
            "dimension": vectors.shape[1],
            "max_sequence_length": getattr(encoder, "max_seq_length", None),
            "documents": len(ids),
            "provenance": provenance,
            "corpus_sha256": digest(Path(data) / "corpus.jsonl"),
            "ranker": None,
        }
        seal(temp, metadata)

        # Prove the sealed bundle loads before publishing it.
        Engine(temp, encoder=encoder)
        os.rename(temp, output)
        print(f"Validated bundle: {output}", flush=True)
    except BaseException:
        shutil.rmtree(temp)
        raise
