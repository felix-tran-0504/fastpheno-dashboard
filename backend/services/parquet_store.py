"""Build Parquet query files from FastPheno CSV exports."""

from __future__ import annotations

from pathlib import Path

import duckdb

from .. import config
from . import datasets


def parquet_path_for(csv_path: Path) -> Path:
    return datasets.parquet_for(csv_path)


def _needs_rebuild(csv_path: Path, parquet_path: Path, *, force: bool) -> bool:
    if force or not parquet_path.is_file():
        return True
    if not csv_path.is_file():
        return False
    return csv_path.stat().st_mtime > parquet_path.stat().st_mtime


def build_one(csv_path: Path, *, force: bool = False) -> Path | None:
    """Convert one CSV to Parquet. Returns output path, or None if CSV is missing."""
    if not csv_path.is_file():
        return None
    parquet_path = parquet_path_for(csv_path)
    if not _needs_rebuild(csv_path, parquet_path, force=force):
        return parquet_path

    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    csv_sql = str(csv_path.resolve()).replace("'", "''")
    pq_sql = str(parquet_path.resolve()).replace("'", "''")
    con = duckdb.connect()
    con.execute(
        f"""
        COPY (SELECT * FROM read_csv_auto('{csv_sql}', header=true))
        TO '{pq_sql}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )
    return parquet_path


def build_all(*, force: bool = False) -> list[Path]:
    """Build Parquet files for every registered CSV source."""
    built: list[Path] = []
    for csv_path in datasets.all_csv_sources():
        out = build_one(csv_path, force=force)
        if out is not None:
            built.append(out)
    return built


def missing_parquet() -> list[Path]:
    """CSV sources that exist but have no Parquet file yet."""
    missing: list[Path] = []
    for csv_path in datasets.all_csv_sources():
        if not csv_path.is_file():
            continue
        if not parquet_path_for(csv_path).is_file():
            missing.append(csv_path)
    return missing


def stale_parquet() -> list[Path]:
    """CSV sources newer than their Parquet file."""
    stale: list[Path] = []
    for csv_path in datasets.all_csv_sources():
        parquet_path = parquet_path_for(csv_path)
        if _needs_rebuild(csv_path, parquet_path, force=False):
            stale.append(csv_path)
    return stale


def ensure_all(*, force: bool = False) -> list[Path]:
    """
    Ensure Parquet query files exist and are up to date.
    Builds missing or stale files; raises if a required CSV has no export.
    """
    if force:
        return build_all(force=True)

    to_build = missing_parquet() + stale_parquet()
    if to_build:
        build_all(force=False)

    still_missing: list[str] = []
    for csv_path in datasets.all_csv_sources():
        if not csv_path.is_file():
            still_missing.append(csv_path.name)
            continue
        if not parquet_path_for(csv_path).is_file():
            still_missing.append(csv_path.name)

    if still_missing:
        names = ", ".join(sorted(set(still_missing)))
        raise FileNotFoundError(
            f"Missing Parquet query files for: {names}. "
            f"Run: python3 scripts/build_parquet.py"
        )
    return [parquet_path_for(p) for p in datasets.all_csv_sources() if p.is_file()]
