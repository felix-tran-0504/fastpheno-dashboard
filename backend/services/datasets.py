"""Dataset registry for FastPheno query API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .. import config

DATA_DIR = config.DATA_DIR
PARQUET_DIR = config.PARQUET_DIR


def parquet_for(csv_path: Path) -> Path:
    """Map a CSV export to its Parquet query file."""
    return PARQUET_DIR / f"{csv_path.stem}.parquet"


@dataclass(frozen=True)
class DomainConfig:
    id: str
    title: str
    date_field: str
    site_field: str
    default_metrics: list[str]
    metadata_file: str | None = None


WEATHER_CSV = {
    "eccc": {
        "PIK": DATA_DIR / "PIK_daily_2010-2024.csv",
        "PIN": DATA_DIR / "PIN_daily_2010-2024.csv",
    },
    "daymet": {
        "PIK": DATA_DIR / "PIK_daymet_daily_2010-2024.csv",
        "PIN": DATA_DIR / "PIN_daymet_daily_2010-2024.csv",
    },
}

WEATHER_METRICS = {
    "eccc": [
        "temp", "max_temp", "min_temp", "precip_amt", "total_rain", "total_snow",
        "wind_spd", "wind_dir", "vpd", "heat_deg_days", "cool_deg_days",
        "temp_interp", "wind_spd_interp",
    ],
    "daymet": [
        "temp", "tmax_c", "tmin_c", "prcp_mm_day", "vpd_kpa", "par_w_m2",
        "par_mol_m2_day", "srad_w_m2", "vp_Pa",
    ],
}

UAV_CSV = {
    2022: DATA_DIR / "uav_reflectance_2022.csv",
    2023: DATA_DIR / "uav_reflectance_2023.csv",
}

UAV_METRICS = [
    "NDVI_mean", "GNDVI_mean", "PRI_mean", "NDRE_mean", "CCI_mean",
    "NIRv_mean", "WaterIndex_mean",
]

TABLE_CSV = {
    "fluorescence": DATA_DIR / "fluorescence_indices.csv",
    "reflectance": DATA_DIR / "reflectance_indices.csv",
    "wp": DATA_DIR / "predawn_wp_2023.csv",
}

# Parquet paths used by DuckDB views / query engine
TABLE_DOMAINS: dict[str, Path] = {k: parquet_for(v) for k, v in TABLE_CSV.items()}

WEATHER_VIEWS: dict[str, Path] = {
    f"weather_{source}_{site.lower()}": parquet_for(path)
    for source, sites in WEATHER_CSV.items()
    for site, path in sites.items()
}

UAV_DATASETS: dict[int, Path] = {year: parquet_for(path) for year, path in UAV_CSV.items()}

# CSV paths for downloads and dataset catalog (source of truth)
WEATHER_SOURCES = WEATHER_CSV

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
        metadata_file=None,
    ),
}

DOMAIN_FILES: dict[str, Path | dict[Any, Path]] = {
    "fluorescence": TABLE_CSV["fluorescence"],
    "reflectance": TABLE_CSV["reflectance"],
    "wp": TABLE_CSV["wp"],
    "uav": UAV_CSV,
    "weather": WEATHER_CSV,
}


def all_csv_sources() -> list[Path]:
    """Every CSV export that has a corresponding Parquet query file."""
    paths: list[Path] = list(TABLE_CSV.values())
    for sites in WEATHER_CSV.values():
        paths.extend(sites.values())
    paths.extend(UAV_CSV.values())
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
        files = DOMAIN_FILES[domain_id]
        if domain_id == "weather":
            entry["sources"] = {
                source: {site: path.name for site, path in sites.items()}
                for source, sites in files.items()
            }
        elif domain_id == "uav":
            entry["years"] = {year: path.name for year, path in files.items()}
        else:
            entry["file"] = files.name
        items.append(entry)
    return items
