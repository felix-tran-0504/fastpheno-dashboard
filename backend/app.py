"""FastPheno data API — serves dashboard assets and sensor query endpoints."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, RedirectResponse

from . import config
from .routers import data_files, query
from .services import parquet_store, query_engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    parquet_store.ensure_all()
    query_engine.init_duckdb()
    yield


app = FastAPI(title="FastPheno Data API", version="1.0.0", lifespan=lifespan)

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8090",
        "http://127.0.0.1:8090",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

BLOCKED_STATIC_PREFIXES = ("data/fastpheno", "backend/")

app.include_router(data_files.router)
app.include_router(query.router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "data_dir": str(config.DATA_DIR),
        "parquet_dir": str(config.PARQUET_DIR),
        "parquet_ready": len(parquet_store.missing_parquet()) == 0,
    }


def _safe_static_path(path: str) -> Path | None:
    if not path or path.startswith("."):
        return None
    if any(path.startswith(prefix) for prefix in BLOCKED_STATIC_PREFIXES):
        return None
    target = (config.ROOT / path).resolve()
    if not str(target).startswith(str(config.ROOT.resolve())):
        return None
    if not target.is_file():
        return None
    return target


@app.get("/")
def root():
    return RedirectResponse("/fastpheno-dashboard.html", status_code=302)


@app.get("/{path:path}")
def static_files(path: str):
    if path == "fastpheno-dashboard.html":
        dashboard = config.ROOT / "fastpheno-dashboard.html"
        if dashboard.is_file():
            return FileResponse(dashboard, media_type="text/html")
    target = _safe_static_path(path)
    if not target:
        raise HTTPException(status_code=404)
    media_type, _ = mimetypes.guess_type(str(target))
    return FileResponse(target, media_type=media_type or "application/octet-stream")
