"""Build consolidated Parquet query files from FastPheno CSV exports."""

from __future__ import annotations

from pathlib import Path

import duckdb

from .. import config
from . import datasets


def _sql_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def _needs_rebuild(csv_paths: list[Path], parquet_path: Path, *, force: bool) -> bool:
    existing = [p for p in csv_paths if p.is_file()]
    if not existing:
        return False
    if force or not parquet_path.is_file():
        return True
    pq_mtime = parquet_path.stat().st_mtime
    return any(p.stat().st_mtime > pq_mtime for p in existing)


def _union_csv_sql(csv_paths: list[Path]) -> str:
    existing = [p for p in csv_paths if p.is_file()]
    if not existing:
        raise FileNotFoundError("no source CSV files found for parquet target")
    parts = [
        f"SELECT * FROM read_csv_auto('{_sql_path(path)}', header=true)"
        for path in existing
    ]
    if len(parts) == 1:
        return parts[0]
    return " UNION ALL BY NAME ".join(parts)


def build_target(name: str, out_path: Path, csv_paths: list[Path], *, force: bool = False) -> Path | None:
    """Union source CSVs into one consolidated Parquet file."""
    existing = [p for p in csv_paths if p.is_file()]
    if not existing:
        return None
    if not _needs_rebuild(existing, out_path, force=force):
        return out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)
    union_sql = _union_csv_sql(existing)
    pq_sql = _sql_path(out_path)
    con = duckdb.connect()
    con.execute(
        f"""
        COPY ({union_sql})
        TO '{pq_sql}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
    )
    return out_path


def _cleanup_legacy_parquets() -> None:
    """Remove old per-CSV Parquet files superseded by consolidated sensor files."""
    keep = {target[1].resolve() for target in datasets.parquet_build_targets()}
    if not datasets.PARQUET_DIR.is_dir():
        return
    for path in datasets.PARQUET_DIR.glob("*.parquet"):
        if path.resolve() not in keep:
            path.unlink(missing_ok=True)


def build_all(*, force: bool = False) -> list[Path]:
    """Build consolidated Parquet files (one per sensor)."""
    built: list[Path] = []
    for name, out_path, csv_paths in datasets.parquet_build_targets():
        result = build_target(name, out_path, csv_paths, force=force)
        if result is not None:
            built.append(result)
    _cleanup_legacy_parquets()
    datasets.clear_parquet_discovery_cache()
    return built


def missing_parquet() -> list[str]:
    """Consolidated targets that exist on disk as CSV but have no Parquet file yet."""
    missing: list[str] = []
    for name, out_path, csv_paths in datasets.parquet_build_targets():
        if not any(p.is_file() for p in csv_paths):
            continue
        if not out_path.is_file():
            missing.append(name)
    return missing


def stale_parquet() -> list[str]:
    """Consolidated targets whose source CSV is newer than the Parquet file."""
    stale: list[str] = []
    for name, out_path, csv_paths in datasets.parquet_build_targets():
        existing = [p for p in csv_paths if p.is_file()]
        if not existing:
            continue
        if _needs_rebuild(existing, out_path, force=False):
            stale.append(name)
    return stale


def ensure_all(*, force: bool = False) -> list[Path]:
    """
    Ensure consolidated Parquet query files exist and are up to date.
    Builds missing or stale files; raises if a required CSV has no export.
    """
    if force:
        return build_all(force=True)

    if missing_parquet() or stale_parquet():
        build_all(force=False)

    still_missing = missing_parquet()
    if still_missing:
        names = ", ".join(sorted(still_missing))
        raise FileNotFoundError(
            f"Missing Parquet query files for: {names}. "
            f"Run: python3 scripts/build_parquet.py"
        )
    datasets.clear_parquet_discovery_cache()
    return [out_path for _, out_path, csv_paths in datasets.parquet_build_targets() if out_path.is_file()]


# Backward-compatible alias used by prepare_fastpheno_data weather-only path.
def build_one(csv_path: Path, *, force: bool = False) -> Path | None:
    """Rebuild every consolidated target that includes this CSV."""
    rebuilt: list[Path] = []
    for name, out_path, csv_paths in datasets.parquet_build_targets():
        if csv_path not in csv_paths:
            continue
        result = build_target(name, out_path, csv_paths, force=force)
        if result is not None:
            rebuilt.append(result)
    return rebuilt[0] if rebuilt else None
