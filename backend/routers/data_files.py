"""Serve derived FastPheno CSV and markdown files."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from .. import config

router = APIRouter(prefix="/api/data/fastpheno", tags=["data"])


@router.get("/{filename}")
def get_data_file(filename: str):
    safe = Path(filename).name
    if safe != filename or not safe:
        raise HTTPException(status_code=400, detail="Invalid path")
    target = (config.DATA_DIR / safe).resolve()
    if not str(target).startswith(str(config.DATA_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    media_type, _ = mimetypes.guess_type(str(target))
    return FileResponse(target, media_type=media_type or "application/octet-stream")
