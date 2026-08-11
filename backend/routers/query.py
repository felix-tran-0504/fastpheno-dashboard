"""JSON query endpoints for FastPheno sensor data."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import FileResponse

from ..services import datasets, query_engine

router = APIRouter(prefix="/api/query", tags=["query"])


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=f"Unknown domain: {exc}")
    if isinstance(exc, ValueError):
        return HTTPException(status_code=422, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/datasets")
def list_datasets():
    return {"datasets": datasets.list_public_datasets()}


@router.get("/{domain}/meta")
def domain_meta(
    domain: str,
    source: str | None = Query(None, description="Weather source: eccc or daymet"),
    resolution: str | None = Query(None, description="Weather resolution: daily or hourly (ECCC only)"),
    site: str | None = Query(None, description="PIK or PIN"),
    year: int | None = Query(None, description="UAV year (2022 or 2023)"),
):
    try:
        return query_engine.get_domain_meta(domain, source=source, resolution=resolution, site=site, year=year)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/{domain}/daily")
def domain_daily(
    domain: str,
    metric: str = Query(..., description="Metric column to aggregate or plot"),
    source: str | None = Query(None, description="Weather source: eccc or daymet"),
    resolution: str | None = Query(None, description="Weather resolution: daily or hourly (ECCC only)"),
    site: str | None = Query(None, description="PIK or PIN"),
    year: int | None = Query(None, description="UAV year"),
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    sensor_id: str | None = Query(None, description="Soil moisture sensor ID (e.g. b11)"),
    interval: str | None = Query(None, description="Soil moisture aggregation: hourly, daily, weekly, monthly"),
):
    try:
        return query_engine.get_daily_series(
            domain,
            metric,
            source=source,
            resolution=resolution,
            site=site,
            year=year,
            sensor_id=sensor_id,
            interval=interval,
            date_from=date_from,
            date_to=date_to,
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/{domain}/export.csv")
def domain_export_csv(
    background_tasks: BackgroundTasks,
    domain: str,
    source: str | None = Query(None, description="Weather source: eccc or daymet"),
    resolution: str | None = Query(None, description="Weather resolution: daily or hourly (ECCC only)"),
    site: str | None = Query(None, description="PIK or PIN"),
    year: int | None = Query(None, description="UAV / spatial year"),
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    sensor_id: str | None = Query(None, description="Soil moisture sensor ID (e.g. b11)"),
):
    try:
        spec = query_engine.prepare_export(
            domain,
            source=source,
            resolution=resolution,
            site=site,
            year=year,
            date_from=date_from,
            date_to=date_to,
            sensor_id=sensor_id,
        )
        tmp_fd, tmp_name = tempfile.mkstemp(suffix=".csv")
        os.close(tmp_fd)
        tmp = Path(tmp_name)
        query_engine.write_export_csv(spec, tmp)

        def _cleanup(path: Path) -> None:
            try:
                os.unlink(path)
            except OSError:
                pass

        background_tasks.add_task(_cleanup, tmp)
        return FileResponse(
            tmp,
            media_type="text/csv",
            filename=spec.filename,
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/{domain}/export/meta")
def domain_export_meta(
    domain: str,
    source: str | None = Query(None, description="Weather source: eccc or daymet"),
    resolution: str | None = Query(None, description="Weather resolution: daily or hourly (ECCC only)"),
    site: str | None = Query(None, description="PIK or PIN"),
    year: int | None = Query(None, description="UAV / spatial year"),
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    sensor_id: str | None = Query(None, description="Soil moisture sensor ID (e.g. b11)"),
):
    try:
        spec = query_engine.prepare_export(
            domain,
            source=source,
            resolution=resolution,
            site=site,
            year=year,
            date_from=date_from,
            date_to=date_to,
            sensor_id=sensor_id,
        )
        return {
            "domain": domain,
            "total": spec.total,
            "filename": spec.filename,
            "method": "server" if spec.use_server else "client",
        }
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/{domain}/rows")
def domain_rows(
    domain: str,
    source: str | None = Query(None, description="Weather source: eccc or daymet"),
    resolution: str | None = Query(None, description="Weather resolution: daily or hourly (ECCC only)"),
    site: str | None = Query(None, description="PIK or PIN"),
    year: int | None = Query(None, description="UAV year"),
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    sensor_id: str | None = Query(None, description="Soil moisture sensor ID (e.g. b11)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    all_rows: bool = Query(False, alias="all"),
):
    try:
        return query_engine.get_rows(
            domain,
            source=source,
            resolution=resolution,
            site=site,
            year=year,
            date_from=date_from,
            date_to=date_to,
            sensor_id=sensor_id,
            page=page,
            page_size=page_size,
            all_rows=all_rows,
        )
    except Exception as exc:
        raise _http_error(exc) from exc
