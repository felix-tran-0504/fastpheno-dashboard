"""Discover sites and coverage from consolidated Parquet query files."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import duckdb

from .. import config

PARQUET_DIR = config.PARQUET_DIR

WEATHER_PARQUETS: dict[str, Path] = {
    "eccc": PARQUET_DIR / "weather_eccc.parquet",
    "eccc_hourly": PARQUET_DIR / "weather_eccc_hourly.parquet",
    "daymet": PARQUET_DIR / "weather_daymet.parquet",
}

SPATIAL_PARQUETS: dict[str, Path] = {
    "lidar": PARQUET_DIR / "lidar.parquet",
    "gnss": PARQUET_DIR / "gnss.parquet",
}

_WEATHER_SITE_COL = "site_id"
_SPATIAL_SITE_COL = "site"


def _sql_path(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def clear_discovery_cache() -> None:
    """Drop cached Parquet discovery results (call after rebuild)."""
    _distinct_sites_from_parquet.cache_clear()
    _spatial_site_years_from_parquet.cache_clear()


@lru_cache(maxsize=16)
def _distinct_sites_from_parquet(parquet_key: str, column: str) -> tuple[str, ...]:
    path = Path(parquet_key)
    if not path.is_file():
        return ()
    con = duckdb.connect()
    rows = con.execute(
        f"""
        SELECT DISTINCT upper(cast({_quote_ident(column)} as varchar)) AS site
        FROM read_parquet('{_sql_path(path)}')
        WHERE {_quote_ident(column)} IS NOT NULL
        ORDER BY 1
        """
    ).fetchall()
    return tuple(r[0] for r in rows if r[0])


@lru_cache(maxsize=4)
def _spatial_site_years_from_parquet(parquet_key: str) -> tuple[tuple[str, int], ...]:
    path = Path(parquet_key)
    if not path.is_file():
        return ()
    con = duckdb.connect()
    rows = con.execute(
        f"""
        SELECT DISTINCT
            upper(cast({_quote_ident(_SPATIAL_SITE_COL)} as varchar)) AS site,
            cast(year as integer) AS year
        FROM read_parquet('{_sql_path(path)}')
        WHERE {_quote_ident(_SPATIAL_SITE_COL)} IS NOT NULL
          AND year IS NOT NULL
        ORDER BY 1, 2
        """
    ).fetchall()
    return tuple((str(r[0]), int(r[1])) for r in rows if r[0])


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def weather_sites() -> list[str]:
    """Site IDs for Climate (primary list from ECCC daily Parquet)."""
    sites = list(_distinct_sites_from_parquet(str(WEATHER_PARQUETS["eccc"]), _WEATHER_SITE_COL))
    if sites:
        return sites
    return _weather_sites_from_csv_fallback()


def weather_sites_for_source(source: str) -> list[str]:
    """Site IDs present in a weather Parquet file (eccc, eccc_hourly, daymet)."""
    path = WEATHER_PARQUETS.get(source.lower())
    if path is None:
        return []
    sites = list(_distinct_sites_from_parquet(str(path), _WEATHER_SITE_COL))
    if sites:
        return sites
    return _weather_sites_for_csv_source(source)


def weather_has_site(source: str, site: str) -> bool:
    return site.upper() in weather_sites_for_source(source)


def spatial_site_years(domain: str) -> list[tuple[str, int]]:
    """(site, year) pairs for lidar or gnss from Parquet, else CSV filenames on disk."""
    domain = domain.lower()
    path = SPATIAL_PARQUETS.get(domain)
    if path is None:
        return []
    pairs = list(_spatial_site_years_from_parquet(str(path)))
    if pairs:
        return pairs
    return _spatial_site_years_from_csv(domain)


def spatial_years_for_site(domain: str, site: str) -> list[int]:
    site = site.upper()
    years = sorted(y for s, y in spatial_site_years(domain) if s == site)
    if not years:
        raise FileNotFoundError(f"no {domain} data for site {site}")
    return years


def spatial_export_filename(domain: str, site: str, year: int) -> str:
    """Canonical condensed CSV name for catalog / download links."""
    return f"uav_{domain}_{site.lower()}_{year}.csv"


# --- CSV fallbacks (build pipeline and deployments that still ship CSVs) ---

_WEATHER_DAILY_RE = re.compile(r"^([A-Z0-9]+)_daily_2010-2024\.csv$", re.I)
_SPATIAL_CSV_RE = re.compile(r"^uav_(lidar|gnss)_(pik|pin)_(\d{4})\.csv$", re.I)
_DATA_DIR = config.DATA_DIR


def _weather_sites_from_csv_fallback() -> list[str]:
    sites: list[str] = []
    for path in _DATA_DIR.glob("*_daily_2010-2024.csv"):
        match = _WEATHER_DAILY_RE.match(path.name)
        if match:
            sites.append(match.group(1).upper())
    return sorted(set(sites))


def _weather_sites_for_csv_source(source: str) -> list[str]:
    src = source.lower()
    all_sites = _weather_sites_from_csv_fallback()
    if src == "eccc":
        return all_sites
    if src == "eccc_hourly":
        return sorted(
            s for s in all_sites
            if (_DATA_DIR / f"{s}_hourly_2022-2024.csv").is_file()
        )
    if src == "daymet":
        return sorted(
            s for s in all_sites
            if (_DATA_DIR / f"{s}_daymet_daily_2010-2024.csv").is_file()
        )
    return []


def _spatial_site_years_from_csv(domain: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    for csv_path in sorted(_DATA_DIR.glob(f"uav_{domain}_*.csv")):
        match = _SPATIAL_CSV_RE.match(csv_path.name)
        if not match or match.group(1).lower() != domain:
            continue
        out.append((match.group(2).upper(), int(match.group(3))))
    return out
