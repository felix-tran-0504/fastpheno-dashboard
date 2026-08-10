"""Pigments campaign listing and zip download endpoints."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse

from ..services import pigments

router = APIRouter(prefix="/api/pigments", tags=["pigments"])


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/meta")
def pigments_meta(site: str | None = Query(None, description="PIK, PIN, or omit for all")):
    try:
        return pigments.get_meta(site=site)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/campaigns")
def pigments_campaigns(
    site: str | None = Query(None, description="PIK, PIN, or omit for all"),
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
):
    try:
        campaigns = pigments.list_campaigns(site=site)
        matched = pigments.filter_campaigns(campaigns, date_from=date_from, date_to=date_to)
        return {"campaigns": matched, "total": len(matched)}
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/download")
def pigments_download(
    background_tasks: BackgroundTasks,
    site: str | None = Query(None, description="PIK, PIN, or omit for all"),
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
):
    try:
        zip_path, filename = pigments.build_zip(site=site, date_from=date_from, date_to=date_to)
    except Exception as exc:
        raise _http_error(exc) from exc

    def _cleanup(path: Path) -> None:
        try:
            os.unlink(path)
        except OSError:
            pass

    background_tasks.add_task(_cleanup, zip_path)
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=filename,
    )
