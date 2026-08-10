"""DuckDB-backed queries over FastPheno Parquet query files."""

from __future__ import annotations

import re
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
    for name, path in datasets.WEATHER_VIEWS.items():
        con.execute(
            f"CREATE OR REPLACE VIEW {name} AS "
            f"SELECT * FROM {_parquet_source(path)}"
        )
    for year, path in datasets.UAV_DATASETS.items():
        con.execute(
            f"CREATE OR REPLACE VIEW uav_{year} AS "
            f"SELECT * FROM {_parquet_source(path)}"
        )
    for kind, site_years in datasets.UAV_SPATIAL.items():
        for (site, year), path in site_years.items():
            view = f"{kind}_{site.lower()}_{year}"
            con.execute(
                f"CREATE OR REPLACE VIEW {view} AS "
                f"SELECT * FROM {_parquet_source(path)}"
            )
    _views_ready = True


def _ensure_uav_views() -> None:
    _ensure_all_views()


def _table_relation(domain: str) -> str:
    _ensure_all_views()
    if domain not in datasets.TABLE_DOMAINS:
        raise ValueError(f"no table view for domain {domain}")
    return domain


def _weather_view_name(source: str, site: str) -> str:
    return f"weather_{source.lower()}_{site.lower()}"


def _weather_relation(source: str, site: str | None) -> str:
    _ensure_all_views()
    src = source.lower()
    if site:
        return _weather_view_name(src, site)
    parts = [
        f"SELECT *, upper('{s}') AS site_id FROM {_weather_view_name(src, s)}"
        for s in ("PIK", "PIN")
    ]
    return f"({' UNION ALL '.join(parts)})"


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
    if len(years) == 1:
        return f"uav_{years[0]}"
    parts = [f"SELECT * FROM uav_{y}" for y in years]
    return f"({' UNION ALL '.join(parts)})"


def _uav_select_columns() -> str:
    return ", ".join(_quote_ident(c) for c in UAV_ROW_COLUMNS)


def _spatial_view_name(domain: str, site: str, year: int) -> str:
    return f"{domain}_{site.lower()}_{year}"


def _spatial_years_for_site(
    domain: str,
    site: str,
    date_from: str | None,
    date_to: str | None,
) -> list[int]:
    site = site.upper()
    available = sorted(y for (s, y) in datasets.UAV_SPATIAL.get(domain, {}) if s == site)
    if not available:
        raise FileNotFoundError(f"no {domain} data for site {site}")
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
    if len(years) == 1:
        return _spatial_view_name(domain, site, years[0])
    parts = [f"SELECT * FROM {_spatial_view_name(domain, site, y)}" for y in years]
    return f"({' UNION ALL '.join(parts)})"


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
        relation = _spatial_view_name(domain, site, y)
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
        csv_name = datasets.DATA_DIR / f"uav_{domain}_{site.lower()}_{y}.csv"
        years_meta[str(y)] = {"bounds": row, "file": csv_name.name}
    bounds = _fetch_one(
        f"""
        SELECT
            min(min_date) AS min_date,
            max(max_date) AS max_date,
            sum(row_count) AS row_count
        FROM (
            {" UNION ALL ".join(
                f"SELECT min({_date_expr(cfg.date_field)}) AS min_date, "
                f"max({_date_expr(cfg.date_field)}) AS max_date, count(*) AS row_count "
                f"FROM {_spatial_view_name(domain, site, y)} "
                f"WHERE {_date_expr(cfg.date_field)} IS NOT NULL"
                for y in years
            )}
        ) t
        """
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
            FROM uav_{y}
            WHERE {_date_expr(cfg.date_field)} IS NOT NULL
            """
        )
        sites = _fetch_dicts(
            f"""
            SELECT upper(cast({cfg.site_field} as varchar)) AS site, count(*) AS n
            FROM uav_{y}
            GROUP BY 1 ORDER BY 1
            """
        )
        years_meta[str(y)] = {"bounds": row, "sites": sites, "file": datasets.UAV_CSV[y].name}

    bounds = _fetch_one(
        f"""
        SELECT
            min(min_date) AS min_date,
            max(max_date) AS max_date,
            sum(row_count) AS row_count
        FROM (
            {" UNION ALL ".join(
                f"SELECT min({_date_expr(cfg.date_field)}) AS min_date, "
                f"max({_date_expr(cfg.date_field)}) AS max_date, count(*) AS row_count "
                f"FROM uav_{y} WHERE {_date_expr(cfg.date_field)} IS NOT NULL"
                for y in years
            )}
        ) t
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
        union = " UNION ALL ".join(
            f"""
            SELECT cast({_date_expr(cfg.date_field)} as varchar) AS date
            FROM uav_{y}
            WHERE upper(cast({cfg.site_field} as varchar)) = ?
              AND {_date_expr(cfg.date_field)} IS NOT NULL
            """
            for y in years
        )
        dates = _fetch_dicts(
            f"SELECT DISTINCT date FROM ({union}) t ORDER BY 1",
            [site] * len(years),
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


def _resolve_weather_path(source: str, site: str) -> Path:
    source = source.lower()
    if source not in datasets.WEATHER_SOURCES:
        raise ValueError("source must be eccc or daymet")
    site = _validate_site(site) or "PIN"
    return datasets.WEATHER_SOURCES[source][site]


def _resolve_domain_path(domain: str, *, source: str | None = None, site: str | None = None, year: int | None = None) -> Path:
    if domain == "weather":
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
    site: str | None = None,
    year: int | None = None,
) -> dict[str, Any]:
    cfg = datasets.domain_config(domain)
    site = _validate_site(site)

    if domain == "weather":
        bounds: dict[str, Any] = {}
        sites_out = ["PIK", "PIN"] if site is None else [site]
        sources_out = ["eccc", "daymet"] if source is None else [source.lower()]
        for src in sources_out:
            bounds[src] = {}
            for s in sites_out:
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
            "sites": ["PIK", "PIN"],
            "metrics": datasets.WEATHER_METRICS,
            "bounds": bounds,
            "metadata_file": cfg.metadata_file,
        }
        if source:
            src = source.lower()
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
                union = " UNION ALL ".join(
                    f"""
                    SELECT cast({_date_expr(cfg.date_field)} as varchar) AS date
                    FROM {_weather_view_name(src, s)}
                    WHERE {_date_expr(cfg.date_field)} IS NOT NULL
                    """
                    for s in ("PIK", "PIN")
                )
                dates = _fetch_dicts(f"SELECT DISTINCT date FROM ({union}) t ORDER BY 1")
                result["available_dates"] = [r["date"] for r in dates]
                result["fields"] = _describe_fields(_weather_view_name(src, "PIK"))
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
                FROM uav_{y}
                WHERE {_date_expr(cfg.date_field)} IS NOT NULL
                """
            )
            sites = _fetch_dicts(
                f"""
                SELECT upper(cast({cfg.site_field} as varchar)) AS site, count(*) AS n
                FROM uav_{y}
                GROUP BY 1 ORDER BY 1
                """
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
                    FROM uav_{y}
                    WHERE upper(cast({cfg.site_field} as varchar)) = ?
                      AND {_date_expr(cfg.date_field)} IS NOT NULL
                    ORDER BY 1
                    """,
                    [site],
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
        if not source:
            raise ValueError("source is required")
        allowed = datasets.WEATHER_METRICS.get(source.lower(), [])
        metric = _validate_metric(metric, allowed)
        relation = _weather_relation(source, site)
        where, params = _build_filters(cfg.date_field, cfg.site_field, site=None, date_from=date_from, date_to=date_to)
        sql = f"""
            SELECT cast({_date_expr(cfg.date_field)} as varchar) AS date,
                   try_cast({_quote_ident(metric)} as double) AS mean,
                   1 AS n
            FROM {relation}{where}
            ORDER BY date
        """
        points = _fetch_dicts(sql, params)
        return {"domain": domain, "metric": metric, "source": source.lower(), "site": site, "points": points}

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
        if not source:
            raise ValueError("source is required")
        relation = _weather_relation(source, site)
        where, params = _build_filters(cfg.date_field, cfg.site_field, site=None, date_from=date_from, date_to=date_to)
        order_by = cfg.date_field
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
