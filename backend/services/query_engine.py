"""DuckDB-backed queries over FastPheno Parquet query files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import duckdb

from .. import config
from . import datasets

_SITE_RE = re.compile(r"^[A-Z]{2,4}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_METRIC_RE = re.compile(r"^[A-Za-z0-9_]+$")

UAV_ROW_COLUMNS = [
    "site",
    "year",
    "flight_date",
    "site_treeid",
    "confidence",
    "NDVI_mean",
    "GNDVI_mean",
    "PRI_mean",
    "NDRE_mean",
    "CCI_mean",
    "NIRv_mean",
    "WaterIndex_mean",
]

LIDAR_ROW_COLUMNS = [
    "site",
    "year",
    "flight_date",
    "flight_id",
    "source_file",
    "site_treeid",
    "tree_height_corrected_m",
    "canopy_area_m2",
    "tree_altitude_m",
]

GNSS_ROW_COLUMNS = [
    "site",
    "year",
    "flight_date",
    "flight_id",
    "source_file",
    "site_treeid",
    "treeTop_x",
    "treeTop_y",
    "treeTop_x_std",
    "treeTop_y_std",
]

SPATIAL_DOMAINS = {"lidar", "gnss"}
SPATIAL_ROW_COLUMNS = {
    "lidar": LIDAR_ROW_COLUMNS,
    "gnss": GNSS_ROW_COLUMNS,
}

def warm_query_cache() -> None:
    """Pre-register DuckDB views so first user request is not cold."""
    _ensure_all_views()


def init_duckdb() -> None:
    warm_query_cache()


_views_ready = False


def _validate_weather_site(site: str | None) -> str | None:
    if site is None:
        return None
    site = site.upper()
    allowed = datasets.weather_sites()
    if site not in allowed:
        raise ValueError(f"site must be one of: {', '.join(allowed)}")
    return site


def _weather_sites_for_source(source: str) -> list[str]:
    return datasets.weather_sites_for_source(source)


def _validate_site(site: str | None) -> str | None:
    if site is None:
        return None
    site = site.upper()
    if site not in {"PIK", "PIN"}:
        raise ValueError("site must be PIK or PIN")
    return site


def _validate_date(value: str | None, name: str = "date") -> str | None:
    if value is None:
        return None
    if not _DATE_RE.match(value):
        raise ValueError(f"{name} must be YYYY-MM-DD")
    return value


def _validate_metric(metric: str, allowed: list[str] | None = None) -> str:
    if not _METRIC_RE.match(metric):
        raise ValueError("invalid metric name")
    if allowed and metric not in allowed:
        raise ValueError(f"metric must be one of: {', '.join(allowed)}")
    return metric


def _sql_path(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"data file not found: {path.name}")
    return str(path.resolve())


def _parquet_source(path: Path) -> str:
    return f"read_parquet('{_sql_path(path)}')"


@lru_cache(maxsize=1)
def _connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()


def _ensure_all_views() -> None:
    global _views_ready
    if _views_ready:
        return
    con = _connection()
    for name, path in datasets.TABLE_DOMAINS.items():
        con.execute(
            f"CREATE OR REPLACE VIEW {name} AS "
            f"SELECT * FROM {_parquet_source(path)}"
        )
    for source, path in datasets.WEATHER_PARQUET.items():
        con.execute(
            f"CREATE OR REPLACE VIEW weather_{source} AS "
            f"SELECT * FROM {_parquet_source(path)}"
        )
    con.execute(
        f"CREATE OR REPLACE VIEW uav AS "
        f"SELECT * FROM {_parquet_source(datasets.UAV_PARQUET)}"
    )
    for spatial in ("lidar", "gnss"):
        con.execute(
            f"CREATE OR REPLACE VIEW {spatial} AS "
            f"SELECT * FROM {_parquet_source(datasets.SENSOR_PARQUET[spatial])}"
        )
    _views_ready = True


def _ensure_uav_views() -> None:
    _ensure_all_views()


def _table_relation(domain: str) -> str:
    _ensure_all_views()
    if domain not in datasets.TABLE_DOMAINS:
        raise ValueError(f"no table view for domain {domain}")
    return domain


def _weather_source_view(source: str) -> str:
    return f"weather_{source.lower()}"


def _weather_relation(source: str, site: str | None) -> str:
    _ensure_all_views()
    view = _weather_source_view(source)
    if site:
        site = _validate_weather_site(site)
        if not datasets.weather_has_site(source, site):
            raise ValueError(f"no weather data for site {site} in source {source.lower()}")
        return f"(SELECT * FROM {view} WHERE upper(cast(site_id as varchar)) = '{site}')"
    return view


def _describe_fields(relation: str) -> list[str]:
    rows = _fetch_dicts(f"DESCRIBE SELECT * FROM {relation}")
    return [r["column_name"] for r in rows]


def _uav_years_in_range(date_from: str | None, date_to: str | None) -> list[int]:
    years = sorted(datasets.UAV_DATASETS)
    if not date_from and not date_to:
        return years
    lo_year = int((date_from or date_to)[:4])
    hi_year = int((date_to or date_from)[:4])
    return [y for y in years if lo_year <= y <= hi_year]


def _uav_relation(years: list[int]) -> str:
    _ensure_uav_views()
    all_years = sorted(datasets.UAV_DATASETS)
    if years == all_years:
        return "uav"
    year_list = ", ".join(str(y) for y in years)
    return f"(SELECT * FROM uav WHERE year IN ({year_list}))"


def _uav_select_columns() -> str:
    return ", ".join(_quote_ident(c) for c in UAV_ROW_COLUMNS)



def _spatial_years_for_site(
    domain: str,
    site: str,
    date_from: str | None,
    date_to: str | None,
) -> list[int]:
    site = site.upper()
    available = datasets.spatial_years_for_site(domain, site)
    if not date_from and not date_to:
        return available
    lo_year = int((date_from or date_to)[:4])
    hi_year = int((date_to or date_from)[:4])
    years = [y for y in available if lo_year <= y <= hi_year]
    if not years:
        raise ValueError(f"no {domain} data for site {site} in date range")
    return years


def _spatial_relation(domain: str, site: str, years: list[int]) -> str:
    _ensure_all_views()
    site = site.upper()
    year_list = ", ".join(str(y) for y in years)
    return (
        f"(SELECT * FROM {domain} "
        f"WHERE upper(cast(site as varchar)) = '{site}' AND year IN ({year_list}))"
    )


def _spatial_select_columns(domain: str) -> str:
    return ", ".join(_quote_ident(c) for c in SPATIAL_ROW_COLUMNS[domain])


@lru_cache(maxsize=16)
def _cached_spatial_meta(domain: str, site: str) -> dict[str, Any]:
    return _build_spatial_meta(domain, site=site)


def _build_spatial_meta(domain: str, *, site: str) -> dict[str, Any]:
    _ensure_all_views()
    cfg = datasets.domain_config(domain)
    site = _validate_site(site) or "PIN"
    years = _spatial_years_for_site(domain, site, None, None)
    years_meta: dict[str, Any] = {}
    for y in years:
        row = _fetch_one(
            f"""
            SELECT
                min({_date_expr(cfg.date_field)}) AS min_date,
                max({_date_expr(cfg.date_field)}) AS max_date,
                count(*) AS row_count
            FROM {domain}
            WHERE upper(cast(site as varchar)) = ?
              AND year = ?
              AND {_date_expr(cfg.date_field)} IS NOT NULL
            """,
            [site, y],
        )
        csv_name = datasets.spatial_export_filename(domain, site, y)
        years_meta[str(y)] = {"bounds": row, "file": csv_name}
    bounds = _fetch_one(
        f"""
        SELECT
            min({_date_expr(cfg.date_field)}) AS min_date,
            max({_date_expr(cfg.date_field)}) AS max_date,
            count(*) AS row_count
        FROM {domain}
        WHERE upper(cast(site as varchar)) = ?
          AND year IN ({", ".join(str(y) for y in years)})
          AND {_date_expr(cfg.date_field)} IS NOT NULL
        """,
        [site],
    )
    relation = _spatial_relation(domain, site, years)
    dates = _fetch_dicts(
        f"""
        SELECT DISTINCT cast({_date_expr(cfg.date_field)} as varchar) AS date
        FROM {relation}
        WHERE {_date_expr(cfg.date_field)} IS NOT NULL
        ORDER BY 1
        """
    )
    return {
        "domain": domain,
        "years": years,
        "sites": ["PIK", "PIN"],
        "metrics": cfg.default_metrics,
        "years_meta": years_meta,
        "bounds": bounds,
        "flight_dates": [r["date"] for r in dates],
        "fields": SPATIAL_ROW_COLUMNS[domain],
    }


@lru_cache(maxsize=16)
def _cached_campaign_meta(domain: str, site: str | None) -> dict[str, Any]:
    return _build_campaign_meta(domain, site=site)


def _build_campaign_meta(domain: str, *, site: str | None = None) -> dict[str, Any]:
    cfg = datasets.domain_config(domain)
    relation = _table_relation(domain)
    bounds = _fetch_one(
        f"""
        SELECT
            min({_date_expr(cfg.date_field)}) AS min_date,
            max({_date_expr(cfg.date_field)}) AS max_date,
            count(*) AS row_count
        FROM {relation}
        WHERE {_date_expr(cfg.date_field)} IS NOT NULL
        """
    )
    sites = _fetch_dicts(
        f"""
        SELECT upper(cast({cfg.site_field} as varchar)) AS site, count(*) AS n
        FROM {relation}
        GROUP BY 1 ORDER BY 1
        """
        if cfg.site_field in _describe_fields(relation)
        else f"SELECT 'ALL' AS site, count(*) AS n FROM {relation}"
    )
    result: dict[str, Any] = {
        "domain": domain,
        "file": datasets.TABLE_CSV[domain].name,
        "sites": [r["site"] for r in sites if r["site"] != "ALL"],
        "metrics": cfg.default_metrics,
        "bounds": bounds,
        "fields": _describe_fields(relation),
        "metadata_file": cfg.metadata_file,
    }
    date_params: list[Any] = []
    date_where = f"WHERE {_date_expr(cfg.date_field)} IS NOT NULL"
    if site and cfg.site_field in result["fields"]:
        date_where += f" AND upper(cast({cfg.site_field} as varchar)) = ?"
        date_params.append(site)
    dates = _fetch_dicts(
        f"""
        SELECT DISTINCT cast({_date_expr(cfg.date_field)} as varchar) AS date
        FROM {relation}
        {date_where}
        ORDER BY 1
        """,
        date_params,
    )
    result["available_dates"] = [r["date"] for r in dates]
    if domain == "soil_moisture" and "sensor_id" in result["fields"]:
        sensor_where = date_where
        sensor_params = list(date_params)
        sensors = _fetch_dicts(
            f"""
            SELECT DISTINCT cast(sensor_id as varchar) AS sensor_id
            FROM {relation}
            {sensor_where}
              AND sensor_id IS NOT NULL AND cast(sensor_id as varchar) != ''
            ORDER BY 1
            """,
            sensor_params,
        )
        result["sensor_ids"] = [r["sensor_id"] for r in sensors]
    return result


@lru_cache(maxsize=8)
def _cached_uav_meta(site: str) -> dict[str, Any]:
    return _build_uav_meta(site=site)


def _build_uav_meta(*, site: str | None = None) -> dict[str, Any]:
    cfg = datasets.domain_config("uav")
    _ensure_uav_views()
    years = sorted(datasets.UAV_DATASETS)
    years_meta: dict[str, Any] = {}
    for y in years:
        row = _fetch_one(
            f"""
            SELECT
                min({_date_expr(cfg.date_field)}) AS min_date,
                max({_date_expr(cfg.date_field)}) AS max_date,
                count(*) AS row_count
            FROM uav
            WHERE year = ?
              AND {_date_expr(cfg.date_field)} IS NOT NULL
            """,
            [y],
        )
        sites = _fetch_dicts(
            f"""
            SELECT upper(cast({cfg.site_field} as varchar)) AS site, count(*) AS n
            FROM uav
            WHERE year = ?
            GROUP BY 1 ORDER BY 1
            """,
            [y],
        )
        years_meta[str(y)] = {"bounds": row, "sites": sites, "file": datasets.UAV_CSV[y].name}

    bounds = _fetch_one(
        f"""
        SELECT
            min({_date_expr(cfg.date_field)}) AS min_date,
            max({_date_expr(cfg.date_field)}) AS max_date,
            count(*) AS row_count
        FROM uav
        WHERE {_date_expr(cfg.date_field)} IS NOT NULL
        """
    )
    result: dict[str, Any] = {
        "domain": "uav",
        "years": years,
        "sites": ["PIK", "PIN"],
        "metrics": datasets.UAV_METRICS,
        "years_meta": years_meta,
        "bounds": bounds,
    }
    if site:
        dates = _fetch_dicts(
            f"""
            SELECT DISTINCT cast({_date_expr(cfg.date_field)} as varchar) AS date
            FROM uav
            WHERE upper(cast({cfg.site_field} as varchar)) = ?
              AND {_date_expr(cfg.date_field)} IS NOT NULL
            ORDER BY 1
            """,
            [site],
        )
        result["flight_dates"] = [r["date"] for r in dates]
    return result


def _fetch_dicts(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    con = _connection()
    cur = con.execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def _fetch_one(sql: str, params: list[Any] | None = None) -> dict[str, Any] | None:
    rows = _fetch_dicts(sql, params)
    return rows[0] if rows else None


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _date_expr(field: str) -> str:
    return f"try_cast({field} as date)"


def _build_filters(
    date_field: str,
    site_field: str,
    *,
    site: str | None,
    date_from: str | None,
    date_to: str | None,
    extra: dict[str, Any] | None = None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = [f"{_date_expr(date_field)} IS NOT NULL"]
    params: list[Any] = []
    if site:
        clauses.append(f"upper(cast({site_field} as varchar)) = ?")
        params.append(site)
    if date_from:
        clauses.append(f"{_date_expr(date_field)} >= cast(? as date)")
        params.append(date_from)
    if date_to:
        clauses.append(f"{_date_expr(date_field)} <= cast(? as date)")
        params.append(date_to)
    if extra:
        for field, value in extra.items():
            clauses.append(f"cast({field} as varchar) = ?")
            params.append(str(value))
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    return where, params


SOIL_MOISTURE_INTERVALS = {"hourly", "daily", "weekly", "monthly"}


def _validate_soil_interval(interval: str | None) -> str:
    value = (interval or "daily").lower()
    if value not in SOIL_MOISTURE_INTERVALS:
        raise ValueError("interval must be hourly, daily, weekly, or monthly")
    return value


def _validate_soil_sensor_id(sensor_id: str | None) -> str:
    if not sensor_id or not str(sensor_id).strip():
        raise ValueError("sensor_id is required for soil moisture queries")
    sensor_id = str(sensor_id).strip()
    if not re.match(r"^[A-Za-z0-9_-]+$", sensor_id):
        raise ValueError("invalid sensor_id")
    return sensor_id


def _soil_bucket_expr(interval: str) -> str:
    if interval == "hourly":
        return "date_trunc('hour', try_cast(datetime as timestamp))"
    if interval == "daily":
        return "try_cast(date as date)"
    if interval == "weekly":
        return "date_trunc('week', try_cast(date as date))"
    return "date_trunc('month', try_cast(date as date))"


def _filter_extra(domain: str, sensor_id: str | None) -> dict[str, Any] | None:
    if domain == "soil_moisture" and sensor_id:
        return {"sensor_id": _validate_soil_sensor_id(sensor_id)}
    return None


def _get_soil_moisture_series(
    metric: str,
    *,
    site: str | None,
    sensor_id: str | None,
    interval: str | None,
    date_from: str | None,
    date_to: str | None,
) -> dict[str, Any]:
    cfg = datasets.domain_config("soil_moisture")
    metric = _validate_metric(metric, cfg.default_metrics)
    sensor_id = _validate_soil_sensor_id(sensor_id)
    interval = _validate_soil_interval(interval)
    site = _validate_site(site)
    relation = _table_relation("soil_moisture")
    bucket = _soil_bucket_expr(interval)
    where, params = _build_filters(
        cfg.date_field,
        cfg.site_field,
        site=site,
        date_from=date_from,
        date_to=date_to,
        extra={"sensor_id": sensor_id},
    )
    sql = f"""
        SELECT cast({bucket} as varchar) AS date,
               avg(try_cast({_quote_ident(metric)} as double)) AS mean,
               count(*) AS n
        FROM {relation}{where}
        GROUP BY {bucket}
        ORDER BY {bucket}
    """
    points = _fetch_dicts(sql, params)
    return {
        "domain": "soil_moisture",
        "metric": metric,
        "site": site,
        "sensor_id": sensor_id,
        "interval": interval,
        "points": points,
    }


def _table_max_rows(domain: str) -> int:
    if domain == "soil_moisture":
        return config.SOIL_MOISTURE_MAX_TABLE_ROWS
    return config.CAMPAIGN_MAX_TABLE_ROWS


def _resolve_weather_source(source: str, resolution: str | None = None) -> str:
    src = source.lower()
    res = (resolution or "daily").lower()
    if res not in datasets.WEATHER_RESOLUTIONS:
        raise ValueError("resolution must be daily or hourly")
    if src == "daymet":
        if res == "hourly":
            raise ValueError("hourly resolution is only available for ECCC")
        return "daymet"
    if src in ("eccc", "eccc_hourly"):
        return "eccc_hourly" if res == "hourly" else "eccc"
    if src in ("eccc", "eccc_hourly", "daymet"):
        return src
    raise ValueError("source must be eccc or daymet")


def _resolve_weather_path(source: str, site: str) -> Path:
    source = source.lower()
    if source not in ("eccc", "eccc_hourly", "daymet"):
        raise ValueError("source must be eccc, eccc_hourly, or daymet")
    sites = datasets.weather_sites()
    site = _validate_weather_site(site) or (sites[0] if sites else "PIN")
    filename = datasets.weather_csv_name(source, site)
    return datasets.DATA_DIR / filename


def _resolve_domain_path(domain: str, *, source: str | None = None, site: str | None = None, year: int | None = None) -> Path:
    if domain == "weather":
        site = _validate_weather_site(site)
        if not source:
            raise ValueError("source is required for weather queries")
        if not site:
            raise ValueError("site is required for weather queries")
        return _resolve_weather_path(source, site)
    if domain == "uav":
        if year is None:
            raise ValueError("year is required for uav queries")
        path = datasets.UAV_CSV.get(year)
        if path is None:
            raise ValueError(f"no UAV data for year {year}")
        return path
    path = datasets.DOMAIN_FILES[domain]
    if not isinstance(path, Path):
        raise ValueError("invalid domain path")
    return path


def get_domain_meta(
    domain: str,
    *,
    source: str | None = None,
    resolution: str | None = None,
    site: str | None = None,
    year: int | None = None,
) -> dict[str, Any]:
    cfg = datasets.domain_config(domain)
    if domain == "weather":
        site = _validate_weather_site(site)
    else:
        site = _validate_site(site)

    if domain == "weather":
        bounds: dict[str, Any] = {}
        all_sites = datasets.weather_sites()
        sites_out = all_sites if site is None else [site]
        if source is None:
            sources_out = ["eccc", "eccc_hourly", "daymet"]
        else:
            sources_out = [_resolve_weather_source(source, resolution)]
        for src in sources_out:
            bounds[src] = {}
            src_sites = [s for s in sites_out if datasets.weather_has_site(src, s)]
            for s in src_sites:
                relation = _weather_relation(src, s)
                row = _fetch_one(
                    f"""
                    SELECT
                        min({_date_expr(cfg.date_field)}) AS min_date,
                        max({_date_expr(cfg.date_field)}) AS max_date,
                        count(*) AS row_count
                    FROM {relation}
                    WHERE {_date_expr(cfg.date_field)} IS NOT NULL
                    """
                )
                bounds[src][s] = row
        result: dict[str, Any] = {
            "domain": domain,
            "sources": ["eccc", "daymet"],
            "resolutions": {"eccc": ["daily", "hourly"], "daymet": ["daily"]},
            "sites": all_sites,
            "metrics": datasets.WEATHER_METRICS,
            "bounds": bounds,
            "metadata_file": cfg.metadata_file,
        }
        if source:
            src = _resolve_weather_source(source, resolution)
            res = (resolution or "daily").lower()
            result["source"] = source.lower()
            result["resolution"] = res
            src_sites = _weather_sites_for_source(src)
            if site:
                relation = _weather_relation(src, site)
                dates = _fetch_dicts(
                    f"""
                    SELECT DISTINCT cast({_date_expr(cfg.date_field)} as varchar) AS date
                    FROM {relation}
                    WHERE {_date_expr(cfg.date_field)} IS NOT NULL
                    ORDER BY 1
                    """
                )
                result["available_dates"] = [r["date"] for r in dates]
                result["fields"] = _describe_fields(relation)
            else:
                relation = _weather_relation(src, None)
                dates = _fetch_dicts(
                    f"""
                    SELECT DISTINCT cast({_date_expr(cfg.date_field)} as varchar) AS date
                    FROM {relation}
                    WHERE {_date_expr(cfg.date_field)} IS NOT NULL
                    ORDER BY 1
                    """
                )
                result["available_dates"] = [r["date"] for r in dates]
                result["fields"] = _describe_fields(_weather_source_view(src))
        return result

    if domain == "uav":
        site = _validate_site(site)
        if year is not None:
            _ensure_uav_views()
            years_meta: dict[str, Any] = {}
            y = year
            path = datasets.UAV_CSV[y]
            row = _fetch_one(
                f"""
                SELECT
                    min({_date_expr(cfg.date_field)}) AS min_date,
                    max({_date_expr(cfg.date_field)}) AS max_date,
                    count(*) AS row_count
                FROM uav
                WHERE year = ?
                  AND {_date_expr(cfg.date_field)} IS NOT NULL
                """,
                [y],
            )
            sites = _fetch_dicts(
                f"""
                SELECT upper(cast({cfg.site_field} as varchar)) AS site, count(*) AS n
                FROM uav
                WHERE year = ?
                GROUP BY 1 ORDER BY 1
                """,
                [y],
            )
            years_meta[str(y)] = {"bounds": row, "sites": sites, "file": path.name}
            result: dict[str, Any] = {
                "domain": domain,
                "years": sorted(datasets.UAV_DATASETS),
                "sites": ["PIK", "PIN"],
                "metrics": datasets.UAV_METRICS,
                "years_meta": years_meta,
                "bounds": row,
            }
            if site:
                dates = _fetch_dicts(
                    f"""
                    SELECT DISTINCT cast({_date_expr(cfg.date_field)} as varchar) AS date
                    FROM uav
                    WHERE year = ?
                      AND upper(cast({cfg.site_field} as varchar)) = ?
                      AND {_date_expr(cfg.date_field)} IS NOT NULL
                    ORDER BY 1
                    """,
                    [y, site],
                )
                result["flight_dates"] = [r["date"] for r in dates]
            return result
        if site:
            return _cached_uav_meta(site)
        return _build_uav_meta(site=None)

    if domain in SPATIAL_DOMAINS:
        site = _validate_site(site) or "PIN"
        return _cached_spatial_meta(domain, site)

    if domain in datasets.TABLE_DOMAINS:
        if site:
            return _cached_campaign_meta(domain, site)
        return _build_campaign_meta(domain, site=None)

    raise KeyError(domain)


def get_daily_series(
    domain: str,
    metric: str,
    *,
    source: str | None = None,
    resolution: str | None = None,
    site: str | None = None,
    year: int | None = None,
    sensor_id: str | None = None,
    interval: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    cfg = datasets.domain_config(domain)
    date_from = _validate_date(date_from, "from")
    date_to = _validate_date(date_to, "to")
    if domain != "weather":
        site = _validate_site(site)

    if domain == "weather":
        site = _validate_weather_site(site)
        if not source:
            raise ValueError("source is required")
        resolved = _resolve_weather_source(source, resolution)
        allowed = datasets.WEATHER_METRICS.get(resolved, [])
        metric = _validate_metric(metric, allowed)
        relation = _weather_relation(resolved, site)
        where, params = _build_filters(cfg.date_field, cfg.site_field, site=None, date_from=date_from, date_to=date_to)
        if resolved == "eccc_hourly":
            sql = f"""
                SELECT cast(concat({_date_expr(cfg.date_field)}, ' ', substr(cast(time as varchar), 12, 8)) as varchar) AS date,
                       try_cast({_quote_ident(metric)} as double) AS mean,
                       1 AS n
                FROM {relation}{where}
                ORDER BY {_date_expr(cfg.date_field)}, time
            """
        else:
            sql = f"""
                SELECT cast({_date_expr(cfg.date_field)} as varchar) AS date,
                       try_cast({_quote_ident(metric)} as double) AS mean,
                       1 AS n
                FROM {relation}{where}
                ORDER BY date
            """
        points = _fetch_dicts(sql, params)
        return {
            "domain": domain,
            "metric": metric,
            "source": source.lower(),
            "resolution": (resolution or "daily").lower(),
            "site": site,
            "points": points,
        }

    if domain == "soil_moisture":
        return _get_soil_moisture_series(
            metric,
            site=site,
            sensor_id=sensor_id,
            interval=interval,
            date_from=date_from,
            date_to=date_to,
        )

    if domain in datasets.TABLE_DOMAINS:
        metric = _validate_metric(metric, cfg.default_metrics)
        relation = _table_relation(domain)
        extra = _filter_extra(domain, sensor_id)
        where, params = _build_filters(
            cfg.date_field, cfg.site_field, site=site, date_from=date_from, date_to=date_to, extra=extra
        )
        sql = f"""
            SELECT cast({_date_expr(cfg.date_field)} as varchar) AS date,
                   avg(try_cast({_quote_ident(metric)} as double)) AS mean,
                   count(*) AS n
            FROM {relation}{where}
            GROUP BY 1
            ORDER BY 1
        """
        points = _fetch_dicts(sql, params)
        return {"domain": domain, "metric": metric, "site": site, "sensor_id": sensor_id, "points": points}

    if domain == "uav":
        metric = _validate_metric(metric, datasets.UAV_METRICS)
        years = [year] if year is not None else _uav_years_in_range(date_from, date_to)
        relation = _uav_relation(years)
        where, params = _build_filters(cfg.date_field, cfg.site_field, site=site, date_from=date_from, date_to=date_to)
        sql = f"""
            SELECT cast({_date_expr(cfg.date_field)} as varchar) AS date,
                   avg(try_cast({_quote_ident(metric)} as double)) AS mean,
                   count(*) AS n
            FROM {relation}{where}
            GROUP BY 1
            ORDER BY 1
        """
        points = _fetch_dicts(sql, params)
        return {"domain": domain, "metric": metric, "site": site, "year": year, "points": points}

    if domain in SPATIAL_DOMAINS:
        cfg = datasets.domain_config(domain)
        metric = _validate_metric(metric, cfg.default_metrics)
        site = _validate_site(site) or "PIN"
        years = _spatial_years_for_site(domain, site, date_from, date_to)
        relation = _spatial_relation(domain, site, years)
        where, params = _build_filters(cfg.date_field, cfg.site_field, site=site, date_from=date_from, date_to=date_to)
        sql = f"""
            SELECT cast({_date_expr(cfg.date_field)} as varchar) AS date,
                   avg(try_cast({_quote_ident(metric)} as double)) AS mean,
                   count(*) AS n
            FROM {relation}{where}
            GROUP BY 1
            ORDER BY 1
        """
        points = _fetch_dicts(sql, params)
        return {"domain": domain, "metric": metric, "site": site, "points": points}

    raise KeyError(domain)


def get_rows(
    domain: str,
    *,
    source: str | None = None,
    resolution: str | None = None,
    site: str | None = None,
    year: int | None = None,
    sensor_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = config.DEFAULT_PAGE_SIZE,
    all_rows: bool = False,
) -> dict[str, Any]:
    cfg = datasets.domain_config(domain)
    date_from = _validate_date(date_from, "from")
    date_to = _validate_date(date_to, "to")
    page = max(1, page)
    page_size = min(max(1, page_size), config.MAX_PAGE_SIZE)
    offset = (page - 1) * page_size

    if domain == "weather":
        site = _validate_weather_site(site)
        if not source:
            raise ValueError("source is required")
        resolved = _resolve_weather_source(source, resolution)
        relation = _weather_relation(resolved, site)
        where, params = _build_filters(cfg.date_field, cfg.site_field, site=None, date_from=date_from, date_to=date_to)
        order_by = f"{cfg.date_field}, time" if resolved == "eccc_hourly" else cfg.date_field
        max_rows = config.CAMPAIGN_MAX_TABLE_ROWS
    elif domain == "uav":
        years = [year] if year is not None else _uav_years_in_range(date_from, date_to)
        relation = _uav_relation(years)
        site = _validate_site(site)
        where, params = _build_filters(cfg.date_field, cfg.site_field, site=site, date_from=date_from, date_to=date_to)
        cols = _uav_select_columns()
        order_by = f"{cfg.date_field}, site_treeid"
        max_rows = config.UAV_MAX_TABLE_ROWS
        total_row = _fetch_one(f"SELECT count(*) AS total FROM {relation}{where}", params)
        total = int(total_row["total"]) if total_row else 0
        if all_rows:
            if total > max_rows:
                raise ValueError(f"too many rows ({total}); narrow the date range (max {max_rows})")
            rows = _fetch_dicts(
                f"SELECT {cols} FROM {relation}{where} ORDER BY {order_by}",
                params,
            )
            page_size = total or 1
            page = 1
        else:
            rows = _fetch_dicts(
                f"SELECT {cols} FROM {relation}{where} ORDER BY {order_by} LIMIT ? OFFSET ?",
                [*params, page_size, offset],
            )
        return {
            "domain": domain,
            "rows": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "source": source.lower() if source else None,
            "site": site,
            "year": year,
        }
    elif domain in SPATIAL_DOMAINS:
        site = _validate_site(site) or "PIN"
        years = _spatial_years_for_site(domain, site, date_from, date_to)
        relation = _spatial_relation(domain, site, years)
        where, params = _build_filters(cfg.date_field, cfg.site_field, site=site, date_from=date_from, date_to=date_to)
        cols = _spatial_select_columns(domain)
        order_by = f"{cfg.date_field}, site_treeid"
        max_rows = config.UAV_MAX_TABLE_ROWS
        total_row = _fetch_one(f"SELECT count(*) AS total FROM {relation}{where}", params)
        total = int(total_row["total"]) if total_row else 0
        if all_rows:
            if total > max_rows:
                raise ValueError(f"too many rows ({total}); narrow the date range (max {max_rows})")
            rows = _fetch_dicts(
                f"SELECT {cols} FROM {relation}{where} ORDER BY {order_by}",
                params,
            )
            page_size = total or 1
            page = 1
        else:
            rows = _fetch_dicts(
                f"SELECT {cols} FROM {relation}{where} ORDER BY {order_by} LIMIT ? OFFSET ?",
                [*params, page_size, offset],
            )
        return {
            "domain": domain,
            "rows": rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "source": None,
            "site": site,
            "year": year,
        }
    elif domain in datasets.TABLE_DOMAINS:
        site = _validate_site(site)
        if domain == "soil_moisture":
            sensor_id = _validate_soil_sensor_id(sensor_id)
        relation = _table_relation(domain)
        extra = _filter_extra(domain, sensor_id)
        where, params = _build_filters(
            cfg.date_field, cfg.site_field, site=site, date_from=date_from, date_to=date_to, extra=extra
        )
        order_by = f"{cfg.date_field}, sensor_id, time" if domain == "soil_moisture" else cfg.date_field
        max_rows = _table_max_rows(domain)
    else:
        raise KeyError(domain)

    total_row = _fetch_one(f"SELECT count(*) AS total FROM {relation}{where}", params)
    total = int(total_row["total"]) if total_row else 0
    if all_rows:
        if total > max_rows:
            raise ValueError(f"too many rows ({total}); narrow the date range (max {max_rows})")
        rows = _fetch_dicts(
            f"SELECT * FROM {relation}{where} ORDER BY {order_by}",
            params,
        )
        page_size = total or 1
        page = 1
    else:
        rows = _fetch_dicts(
            f"SELECT * FROM {relation}{where} ORDER BY {order_by} LIMIT ? OFFSET ?",
            [*params, page_size, offset],
        )
    return {
        "domain": domain,
        "rows": rows,
        "total": total,
        "page": page,
        "page_size": page_size,
        "source": source.lower() if source else None,
        "site": site,
        "year": year,
        "sensor_id": sensor_id,
    }


@dataclass(frozen=True)
class ExportSpec:
    select_sql: str
    params: list[Any]
    total: int
    filename: str
    use_server: bool


def _export_filename(
    domain: str,
    *,
    source: str | None = None,
    site: str | None = None,
    year: int | None = None,
    sensor_id: str | None = None,
) -> str:
    if domain == "fluorescence":
        return "fluorescence_indices.csv"
    if domain == "reflectance":
        return "reflectance_indices.csv"
    if domain == "wp":
        return "predawn_wp_2023.csv"
    if domain == "soil_moisture":
        parts = ["soil_moisture"]
        if site:
            parts.append(site.lower())
        if sensor_id:
            parts.append(str(sensor_id))
        return "_".join(parts) + ".csv"
    if domain == "uav":
        return f"uav_reflectance_{year}.csv" if year else "uav_reflectance_all.csv"
    if domain in SPATIAL_DOMAINS:
        site_slug = (site or "all").lower()
        if year:
            return f"uav_{domain}_{site_slug}_{year}.csv"
        return f"uav_{domain}_{site_slug}_all.csv"
    if domain == "weather":
        src = (source or "eccc").lower()
        site_slug = (site or "all").lower()
        return f"weather_{src}_{site_slug}.csv"
    return f"{domain}_export.csv"


def recommend_export_method(domain: str, total: int) -> str:
    if domain in config.SERVER_EXPORT_DOMAINS:
        return "server"
    if total > config.CLIENT_EXPORT_MAX_ROWS:
        return "server"
    return "client"


def prepare_export(
    domain: str,
    *,
    source: str | None = None,
    resolution: str | None = None,
    site: str | None = None,
    year: int | None = None,
    sensor_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> ExportSpec:
    """Build a full-dataset export query over Parquet (no pagination)."""
    cfg = datasets.domain_config(domain)
    date_from = _validate_date(date_from, "from")
    date_to = _validate_date(date_to, "to")
    filename = _export_filename(domain, source=source, site=site, year=year, sensor_id=sensor_id)

    if domain == "weather":
        site = _validate_weather_site(site)
        if not source:
            raise ValueError("source is required")
        resolved = _resolve_weather_source(source, resolution)
        relation = _weather_relation(resolved, site)
        where, params = _build_filters(cfg.date_field, cfg.site_field, site=None, date_from=date_from, date_to=date_to)
        order_by = f"{cfg.date_field}, time" if resolved == "eccc_hourly" else cfg.date_field
        select_list = "*"
    elif domain == "uav":
        years = [year] if year is not None else _uav_years_in_range(date_from, date_to)
        relation = _uav_relation(years)
        site = _validate_site(site)
        where, params = _build_filters(cfg.date_field, cfg.site_field, site=site, date_from=date_from, date_to=date_to)
        select_list = _uav_select_columns()
        order_by = f"{cfg.date_field}, site_treeid"
    elif domain in SPATIAL_DOMAINS:
        site = _validate_site(site) or "PIN"
        if year is not None:
            years = [year]
        else:
            years = _spatial_years_for_site(domain, site, date_from, date_to)
        relation = _spatial_relation(domain, site, years)
        where, params = _build_filters(cfg.date_field, cfg.site_field, site=site, date_from=date_from, date_to=date_to)
        select_list = _spatial_select_columns(domain)
        order_by = f"{cfg.date_field}, site_treeid"
        if year is not None:
            filename = _export_filename(domain, site=site, year=year)
    elif domain in datasets.TABLE_DOMAINS:
        site = _validate_site(site)
        if domain == "soil_moisture":
            sensor_id = sensor_id if sensor_id else None
            if sensor_id:
                sensor_id = _validate_soil_sensor_id(sensor_id)
        relation = _table_relation(domain)
        extra = _filter_extra(domain, sensor_id)
        where, params = _build_filters(
            cfg.date_field, cfg.site_field, site=site, date_from=date_from, date_to=date_to, extra=extra
        )
        select_list = "*"
        order_by = f"{cfg.date_field}, sensor_id, time" if domain == "soil_moisture" else cfg.date_field
    else:
        raise KeyError(domain)

    total_row = _fetch_one(f"SELECT count(*) AS total FROM {relation}{where}", params)
    total = int(total_row["total"]) if total_row else 0
    if total > config.EXPORT_MAX_ROWS:
        raise ValueError(f"too many rows ({total}); narrow filters (max export {config.EXPORT_MAX_ROWS})")

    select_sql = f"SELECT {select_list} FROM {relation}{where} ORDER BY {order_by}"
    use_server = recommend_export_method(domain, total) == "server"
    return ExportSpec(select_sql=select_sql, params=params, total=total, filename=filename, use_server=use_server)


def write_export_csv(spec: ExportSpec, dest: Path) -> Path:
    """Run export query and write CSV with header to dest."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest_sql = str(dest.resolve()).replace("'", "''")
    con = _connection()
    con.execute(
        f"COPY ({spec.select_sql}) TO '{dest_sql}' (HEADER, DELIMITER ',')",
        spec.params,
    )
    return dest
