import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .core import Engine, read_json

DEFAULT_BUNDLE = "artifacts/fiqa-ltr"
ARTIFACT_ERROR = (
    "Search artifacts are missing or incompatible. "
    "Rebuild or select a validated bundle."
)
# Manifest keys safe to expose publicly; everything else stays internal.
STATUS_METADATA_KEYS = [
    "model",
    "revision",
    "provenance",
    "dimension",
    "max_sequence_length",
    "bm25",
    "candidate_count",
    "rrf_constant",
]


class Result(BaseModel):
    id: str
    title: str
    excerpt: str
    score: float
    mode: str


class SearchResponse(BaseModel):
    query: str
    mode: str
    results: list[Result]
    server_ms: float
    bundle_version: str


def create_app(bundle=None, engine=None):
    @asynccontextmanager
    async def lifespan(app):
        app.state.engine = engine
        app.state.error = None
        if app.state.engine is None:
            try:
                path = bundle or os.getenv("RANKFORGE_BUNDLE", DEFAULT_BUNDLE)
                app.state.engine = Engine(path)
            except Exception:
                logging.getLogger("rankforge").error(
                    "Artifact startup failed; validate the selected bundle"
                )
                app.state.error = ARTIFACT_ERROR
        yield

    app = FastAPI(title="RankForge", lifespan=lifespan)

    # One inference at a time bounds memory; extra callers get 429 rather
    # than queueing and exhausting the container.
    gate = threading.BoundedSemaphore(1)

    def current():
        if app.state.engine is None:
            raise HTTPException(503, app.state.error or "Search is loading")
        return app.state.engine

    @app.get("/health/live")
    def live():
        return {"live": True}

    @app.get("/health/ready")
    def ready():
        return {"ready": True, "bundle_version": current().version}

    @app.get("/api/status")
    def status():
        e = app.state.engine
        if e is None:
            return {
                "ready": False,
                "available_modes": [],
                "message": app.state.error,
                "bundle_version": None,
                "documents": 0,
                "metadata": None,
            }
        return {
            "ready": True,
            "available_modes": e.modes,
            "message": app.state.error,
            "bundle_version": e.version,
            "documents": len(e.ids),
            "metadata": {k: e.manifest[k] for k in STATUS_METADATA_KEYS},
        }

    @app.get("/api/search", response_model=SearchResponse)
    def search(
        q: str = Query(min_length=1, max_length=500),
        mode: Literal["bm25", "dense", "hybrid", "ltr"] = "hybrid",
        k: int = Query(default=10, ge=1, le=100),
    ):
        e = current()
        if not q.strip():
            raise HTTPException(422, "Enter a non-blank query")
        if mode not in e.modes:
            raise HTTPException(503, "The learned ranker is not installed in this bundle")
        if not gate.acquire(blocking=False):
            raise HTTPException(
                429, "Search is busy. Please try again.", headers={"Retry-After": "1"}
            )
        try:
            start = time.perf_counter()
            results = e.search(q, mode, k)
            elapsed_ms = (time.perf_counter() - start) * 1000
            return {
                "query": q,
                "mode": mode,
                "results": results,
                "server_ms": round(elapsed_ms, 2),
                "bundle_version": e.version,
            }
        finally:
            gate.release()

    @app.get("/api/documents/{doc_id}")
    def document(doc_id: str):
        e = current()
        if doc_id not in e.documents:
            raise HTTPException(404, "Document not found")
        return {**e.documents[doc_id], "attribution": e.manifest["provenance"]}

    @app.get("/api/evaluation")
    def evaluation():
        e = current()
        directory = Path(os.getenv("RANKFORGE_REPORTS", "reports"))
        reports = [read_json(p) for p in sorted(directory.glob("*evaluation*.json"))]
        # Only reports produced by the exact bundle in memory may be shown.
        return {"reports": [r for r in reports if r.get("bundle_sha256") == e.version]}

    dist = Path(os.getenv("RANKFORGE_FRONTEND", "frontend/dist")).resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str):
        if path.startswith(("api/", "health/")):
            raise HTTPException(404, "Not found")
        target = (dist / path).resolve()
        if target.is_relative_to(dist) and target.is_file():
            return FileResponse(target)
        if not (dist / "index.html").is_file():
            raise HTTPException(503, "Frontend has not been built")
        return FileResponse(dist / "index.html")

    return app


app = create_app()
