"""Dataset registry for FastPheno query API."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import config
from . import parquet_registry

_SPATIAL_CSV_RE = re.compile(r"^uav_(lidar|gnss)_(pik|pin)_(\d{4})\.csv$", re.I)
_WEATHER_DAILY_RE = re.compile(r"^([A-Z0-9]+)_daily_2010-2024\.csv$", re.I)

DATA_DIR = config.DATA_DIR
PARQUET_DIR = config.PARQUET_DIR

# One Parquet file per sensor (weather has three source-specific files).
SENSOR_PARQUET: dict[str, Path] = {
    "fluorescence": PARQUET_DIR / "fluorescence.parquet",
    "reflectance": PARQUET_DIR / "reflectance.parquet",
    "wp": PARQUET_DIR / "wp.parquet",
    "soil_moisture": PARQUET_DIR / "soil_moisture.parquet",
    "weather_eccc": PARQUET_DIR / "weather_eccc.parquet",
    "weather_eccc_hourly": PARQUET_DIR / "weather_eccc_hourly.parquet",
    "weather_daymet": PARQUET_DIR / "weather_daymet.parquet",
    "uav": PARQUET_DIR / "uav.parquet",
    "lidar": PARQUET_DIR / "lidar.parquet",
    "gnss": PARQUET_DIR / "gnss.parquet",
}


def parquet_for(csv_path: Path) -> Path:
    """Legacy 1:1 CSV→Parquet path (used for catalog CSV names only)."""
    return PARQUET_DIR / f"{csv_path.stem}.parquet"


@dataclass(frozen=True)
class DomainConfig:
    id: str
    title: str
    date_field: str
    site_field: str
    default_metrics: list[str]
    metadata_file: str | None = None


def discover_weather_sites_from_csv() -> list[str]:
    """Site IDs from exported ECCC daily CSVs (parquet build / prep only)."""
    sites: list[str] = []
    for path in DATA_DIR.glob("*_daily_2010-2024.csv"):
        match = _WEATHER_DAILY_RE.match(path.name)
        if match:
            sites.append(match.group(1).upper())
    return sorted(set(sites))


def discover_weather_sites() -> list[str]:
    """Runtime site list: Parquet when available, else CSV filenames on disk."""
    return parquet_registry.weather_sites()


def build_weather_csv() -> dict[str, dict[str, Path]]:
    sites = discover_weather_sites_from_csv()
    eccc = {s: DATA_DIR / f"{s}_daily_2010-2024.csv" for s in sites}
    hourly = {
        s: DATA_DIR / f"{s}_hourly_2022-2024.csv"
        for s in sites
        if (DATA_DIR / f"{s}_hourly_2022-2024.csv").is_file()
    }
    daymet = {
        s: DATA_DIR / f"{s}_daymet_daily_2010-2024.csv"
        for s in sites
        if (DATA_DIR / f"{s}_daymet_daily_2010-2024.csv").is_file()
    }
    return {"eccc": eccc, "eccc_hourly": hourly, "daymet": daymet}


# CSV paths for parquet build, catalog filenames, and static downloads (may be absent at runtime).
WEATHER_CSV = build_weather_csv()

WEATHER_METRICS = {
    "eccc": [
        "temp", "max_temp", "min_temp", "precip_amt", "total_rain", "total_snow",
        "wind_spd", "wind_dir", "vpd", "heat_deg_days", "cool_deg_days",
        "temp_interp", "wind_spd_interp",
    ],
    "eccc_hourly": [
        "temp", "temp_dew", "rel_hum", "precip_amt", "pressure", "wind_spd", "wind_dir",
        "vpd", "visib", "hmdx", "wind_chill",
        "temp_interp", "temp_dew_interp", "rel_hum_interp", "wind_spd_interp",
        "pressure_interp", "hmdx_interp", "wind_chill_interp",
    ],
    "daymet": [
        "temp", "tmax_c", "tmin_c", "prcp_mm_day", "vpd_kpa", "par_w_m2",
        "par_mol_m2_day", "srad_w_m2", "vp_Pa",
    ],
}

WEATHER_RESOLUTIONS = {"daily", "hourly"}


def _weather_csv_name(source: str, site: str) -> str:
    src = source.lower()
    if src == "eccc":
        return f"{site}_daily_2010-2024.csv"
    if src == "eccc_hourly":
        return f"{site}_hourly_2022-2024.csv"
    if src == "daymet":
        return f"{site}_daymet_daily_2010-2024.csv"
    return f"{site}_{src}.csv"


def weather_sites() -> list[str]:
    """Runtime Climate site IDs (Parquet-first, CSV fallback)."""
    return parquet_registry.weather_sites()


def weather_sites_for_source(source: str) -> list[str]:
    return parquet_registry.weather_sites_for_source(source)


def spatial_years_for_site(domain: str, site: str) -> list[int]:
    return parquet_registry.spatial_years_for_site(domain, site)


def spatial_export_filename(domain: str, site: str, year: int) -> str:
    return parquet_registry.spatial_export_filename(domain, site, year)


def clear_parquet_discovery_cache() -> None:
    parquet_registry.clear_discovery_cache()


def weather_csv_name(source: str, site: str) -> str:
    return _weather_csv_name(source, site)


def weather_has_site(source: str, site: str) -> bool:
    return parquet_registry.weather_has_site(source, site)


UAV_CSV = {
    2022: DATA_DIR / "uav_reflectance_2022.csv",
    2023: DATA_DIR / "uav_reflectance_2023.csv",
}

UAV_METRICS = [
    "NDVI_mean", "GNDVI_mean", "PRI_mean", "NDRE_mean", "CCI_mean",
    "NIRv_mean", "WaterIndex_mean",
]

LIDAR_METRICS = [
    "tree_height_corrected_m",
    "canopy_area_m2",
    "tree_altitude_m",
]

GNSS_METRICS = [
    "treeTop_x",
    "treeTop_y",
    "treeTop_x_std",
    "treeTop_y_std",
]

SOIL_MOISTURE_METRICS = ["vwc", "st"]

TABLE_CSV = {
    "fluorescence": DATA_DIR / "fluorescence_indices.csv",
    "reflectance": DATA_DIR / "reflectance_indices.csv",
    "wp": DATA_DIR / "predawn_wp_2023.csv",
    "soil_moisture": DATA_DIR / "soil_moisture.csv",
}

# Parquet paths used by DuckDB views / query engine (one file per sensor)
TABLE_DOMAINS: dict[str, Path] = {
    "fluorescence": SENSOR_PARQUET["fluorescence"],
    "reflectance": SENSOR_PARQUET["reflectance"],
    "wp": SENSOR_PARQUET["wp"],
    "soil_moisture": SENSOR_PARQUET["soil_moisture"],
}

WEATHER_PARQUET: dict[str, Path] = {
    "eccc": SENSOR_PARQUET["weather_eccc"],
    "eccc_hourly": SENSOR_PARQUET["weather_eccc_hourly"],
    "daymet": SENSOR_PARQUET["weather_daymet"],
}

UAV_PARQUET = SENSOR_PARQUET["uav"]
LIDAR_PARQUET = SENSOR_PARQUET["lidar"]
GNSS_PARQUET = SENSOR_PARQUET["gnss"]

# Year -> CSV path (catalog / downloads); queries read consolidated UAV_PARQUET.
UAV_DATASETS = UAV_CSV


def _discover_spatial_csvs(kind: str) -> dict[tuple[str, int], Path]:
    """Map (site, year) -> CSV path for uav_lidar_* / uav_gnss_* exports."""
    out: dict[tuple[str, int], Path] = {}
    for csv_path in sorted(DATA_DIR.glob(f"uav_{kind}_*.csv")):
        match = _SPATIAL_CSV_RE.match(csv_path.name)
        if not match or match.group(1).lower() != kind:
            continue
        site = match.group(2).upper()
        year = int(match.group(3))
        out[(site, year)] = csv_path
    return out


UAV_SPATIAL: dict[str, dict[tuple[str, int], Path]] = {
    "lidar": _discover_spatial_csvs("lidar"),
    "gnss": _discover_spatial_csvs("gnss"),
}


def spatial_catalog(domain: str) -> dict[tuple[str, int], str]:
    """(site, year) -> export CSV filename for lidar/gnss (Parquet-first)."""
    domain = domain.lower()
    out: dict[tuple[str, int], str] = {}
    for site, year in parquet_registry.spatial_site_years(domain):
        csv_path = UAV_SPATIAL.get(domain, {}).get((site, year))
        name = csv_path.name if csv_path else parquet_registry.spatial_export_filename(domain, site, year)
        out[(site, year)] = name
    return out

DOMAINS: dict[str, DomainConfig] = {
    "weather": DomainConfig(
        id="weather",
        title="Climate / weather",
        date_field="date",
        site_field="site_id",
        default_metrics=WEATHER_METRICS["eccc"],
        metadata_file="weather.md",
    ),
    "fluorescence": DomainConfig(
        id="fluorescence",
        title="Chlorophyll fluorescence",
        date_field="date",
        site_field="site",
        default_metrics=["QY_max", "NPQ_Lss", "QY_Lss", "Rfd"],
        metadata_file="fluorescence_pin_2023.md",
    ),
    "reflectance": DomainConfig(
        id="reflectance",
        title="Leaf reflectance",
        date_field="date",
        site_field="site",
        default_metrics=["NDVI", "PRI", "GNDVI", "NDRE", "EVI"],
        metadata_file="reflectance_pin_2023.md",
    ),
    "wp": DomainConfig(
        id="wp",
        title="Predawn water potential",
        date_field="date",
        site_field="site",
        default_metrics=["wp_pd"],
        metadata_file="predawn_wp_pin_2023.md",
    ),
    "uav": DomainConfig(
        id="uav",
        title="UAV hyperspectral reflectance",
        date_field="flight_date",
        site_field="site",
        default_metrics=UAV_METRICS,
        metadata_file="uav_hyp_spec.md",
    ),
    "lidar": DomainConfig(
        id="lidar",
        title="UAV LiDAR structure",
        date_field="flight_date",
        site_field="site",
        default_metrics=LIDAR_METRICS,
        metadata_file="uav_lidar.md",
    ),
    "gnss": DomainConfig(
        id="gnss",
        title="UAV tree geolocation",
        date_field="flight_date",
        site_field="site",
        default_metrics=GNSS_METRICS,
        metadata_file="uav_gnss.md",
    ),
    "soil_moisture": DomainConfig(
        id="soil_moisture",
        title="Soil moisture",
        date_field="date",
        site_field="site",
        default_metrics=SOIL_MOISTURE_METRICS,
        metadata_file="soil_moisture.md",
    ),
}

DOMAIN_FILES: dict[str, Path | dict[Any, Path]] = {
    "fluorescence": TABLE_CSV["fluorescence"],
    "reflectance": TABLE_CSV["reflectance"],
    "wp": TABLE_CSV["wp"],
    "soil_moisture": TABLE_CSV["soil_moisture"],
    "uav": UAV_CSV,
    "weather": WEATHER_CSV,
}


def uav_spatial_csvs() -> list[Path]:
    """LiDAR / GNSS exports: uav_{lidar|gnss}_{pik|pin}_{year}.csv"""
    return sorted(DATA_DIR.glob("uav_lidar_*.csv")) + sorted(DATA_DIR.glob("uav_gnss_*.csv"))


def parquet_build_targets() -> list[tuple[str, Path, list[Path]]]:
    """Consolidated Parquet targets: (name, output_path, source_csvs)."""
    return [
        ("fluorescence", SENSOR_PARQUET["fluorescence"], [TABLE_CSV["fluorescence"]]),
        ("reflectance", SENSOR_PARQUET["reflectance"], [TABLE_CSV["reflectance"]]),
        ("wp", SENSOR_PARQUET["wp"], [TABLE_CSV["wp"]]),
        ("soil_moisture", SENSOR_PARQUET["soil_moisture"], [TABLE_CSV["soil_moisture"]]),
        ("weather_eccc", SENSOR_PARQUET["weather_eccc"], list(WEATHER_CSV["eccc"].values())),
        ("weather_eccc_hourly", SENSOR_PARQUET["weather_eccc_hourly"], list(WEATHER_CSV["eccc_hourly"].values())),
        ("weather_daymet", SENSOR_PARQUET["weather_daymet"], list(WEATHER_CSV["daymet"].values())),
        ("uav", SENSOR_PARQUET["uav"], list(UAV_CSV.values())),
        ("lidar", SENSOR_PARQUET["lidar"], sorted(DATA_DIR.glob("uav_lidar_*.csv"))),
        ("gnss", SENSOR_PARQUET["gnss"], sorted(DATA_DIR.glob("uav_gnss_*.csv"))),
    ]


def all_csv_sources() -> list[Path]:
    """Every CSV export referenced by a consolidated Parquet target."""
    paths: list[Path] = []
    for _, _, csvs in parquet_build_targets():
        paths.extend(csvs)
    return paths


def domain_config(domain: str) -> DomainConfig:
    if domain not in DOMAINS:
        raise KeyError(domain)
    return DOMAINS[domain]


def list_public_datasets() -> list[dict[str, Any]]:
    items = []
    for domain_id, cfg in DOMAINS.items():
        entry: dict[str, Any] = {
            "id": domain_id,
            "title": cfg.title,
            "date_field": cfg.date_field,
            "site_field": cfg.site_field,
            "metrics": cfg.default_metrics,
            "metadata_file": cfg.metadata_file,
        }
        files = DOMAIN_FILES.get(domain_id)
        if domain_id == "weather":
            entry["sources"] = {
                source: {
                    site: _weather_csv_name(source, site)
                    for site in weather_sites_for_source(source)
                }
                for source in ("eccc", "eccc_hourly", "daymet")
            }
        elif domain_id == "uav":
            entry["years"] = {year: path.name for year, path in files.items()}
        elif domain_id in ("lidar", "gnss"):
            entry["files"] = {
                f"{site}_{year}": name
                for (site, year), name in sorted(spatial_catalog(domain_id).items())
            }
        elif files is not None and isinstance(files, Path):
            entry["file"] = files.name
        items.append(entry)
    return items
