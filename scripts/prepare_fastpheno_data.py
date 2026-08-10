#!/usr/bin/env python3
"""Extract browser-sized FastPheno CSVs from III_db_final."""

import csv
import re
import shutil
from pathlib import Path

from fastpheno_env import get_iii_db_root, load_env

load_env()
SRC = get_iii_db_root()
OUT = Path(__file__).resolve().parents[1] / "data" / "fastpheno"
SITE_MAP = {"Pintendre": "PIN", "Pickering": "PIK"}
DATE_IN_NAME = re.compile(r"(20\d{2}-\d{2}-\d{2})")

# Browser exports: metadata + index metrics only (no spectral wavelength columns).
# Fluorescence columns match data/fastpheno/fluorescence_pin_2023.md (+ site/year/date).
FLUORESCENCE_KEEP = [
    "site", "year", "date",
    "primary_key", "datetime_est", "datetime_ust", "sensor", "operator",
    "Fo", "Fm", "Fp",
    "Ft_L1", "Ft_L2", "Ft_L3", "Ft_L4", "Ft_L5", "Ft_L6", "Ft_L7", "Ft_L8", "Ft_L9", "Ft_Lss",
    "Fm_L1", "Fm_L2", "Fm_L3", "Fm_L4", "Fm_L5", "Fm_L6", "Fm_L7", "Fm_L8", "Fm_L9", "Fm_Lss",
    "NPQ_L1", "NPQ_L2", "NPQ_L3", "NPQ_L4", "NPQ_L5", "NPQ_L6", "NPQ_L7", "NPQ_L8", "NPQ_L9", "NPQ_Lss",
    "Qp_L1", "Qp_L2", "Qp_L3", "Qp_L4", "Qp_L5", "Qp_L6", "Qp_L7", "Qp_L8", "Qp_L9", "Qp_Lss",
    "Rfd", "Fm_D1", "Fm_D2", "NPQ_D1", "NPQ_D2", "Qp_D1", "Qp_D2",
    "QY_max", "QY_L1", "QY_L2", "QY_L3", "QY_L4", "QY_L5", "QY_L6", "QY_L7", "QY_L8", "QY_L9", "QY_Lss",
    "QY_D1", "QY_D2",
]
REFLECTANCE_KEEP = [
    "site", "year", "date",
    "primary_key", "Measurement_ID", "time_EST", "time_GMT", "time",
    "campaign", "sample", "acquisition_time", "orientation", "measurement_number",
    "rank_within_tree",
    "PRI", "NDVI", "NIRv", "CCI", "ChapA", "ChapB", "PSRI", "SIPI",
    "NDRE", "WBI", "CIRE", "EVI", "EVI2", "SAVI", "GNDVI",
]


def parse_year(text: str) -> str:
    match = re.search(r"(20\d{2})", text)
    return match.group(1) if match else ""


def parse_date_from_name(name: str) -> str:
    match = DATE_IN_NAME.search(name)
    return match.group(1) if match else ""


def write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def eccc_weather_sites():
    root = SRC / "Weather" / "ECCC"
    if not root.is_dir():
        return []
    return sorted(
        path.name
        for path in root.iterdir()
        if path.is_dir() and (path / "Daily").is_dir()
    )


def copy_weather():
    for site in eccc_weather_sites():
        src = SRC / "Weather" / "ECCC" / site / "Daily" / f"{site}_daily_2010-2024.csv"
        dst = OUT / f"{site}_daily_2010-2024.csv"
        if not src.is_file():
            raise FileNotFoundError(f"Missing ECCC daily export: {src}")
        shutil.copy2(src, dst)


def copy_eccc_hourly():
    for site in eccc_weather_sites():
        src = SRC / "Weather" / "ECCC" / site / "Hourly" / f"{site}_hourly_2022-2024.csv"
        dst = OUT / f"{site}_hourly_2022-2024.csv"
        if not src.is_file():
            raise FileNotFoundError(f"Missing ECCC hourly export: {src}")
        shutil.copy2(src, dst)


def build_daymet_weather():
    from datetime import datetime, timedelta

    # Preserve all Daymet source weather columns; source "date" is an internal
    # Daymet value (duplicate of dayl_s) and is omitted in favor of ISO date.
    fieldnames = [
        "site_id", "date", "year", "yday",
        "tmax_c", "tmin_c", "prcp_mm_day", "vpd_kpa",
        "par_w_m2", "par_mol_m2_day", "srad_w_m2", "vp_Pa", "dayl_s",
        "temp",
    ]
    for site in eccc_weather_sites():
        src = SRC / "Weather" / "Daymet" / site / "daily" / f"{site}_daily.csv"
        if not src.is_file():
            raise FileNotFoundError(f"Missing Daymet daily export: {src}")
        rows = []
        with src.open() as handle:
            for row in csv.DictReader(handle):
                year = int(row["year"])
                yday = int(row["yday"])
                iso_date = (datetime(year, 1, 1) + timedelta(days=yday - 1)).strftime("%Y-%m-%d")
                try:
                    tmax = float(row["tmax_c"])
                    tmin = float(row["tmin_c"])
                    temp_mean = round((tmax + tmin) / 2, 4)
                except (TypeError, ValueError):
                    temp_mean = ""
                rows.append({
                    "site_id": row["site"].strip().upper(),
                    "date": iso_date,
                    "year": year,
                    "yday": yday,
                    "tmax_c": row["tmax_c"],
                    "tmin_c": row["tmin_c"],
                    "prcp_mm_day": row["prcp_mm_day"],
                    "vpd_kpa": row["vpd_kpa"],
                    "par_w_m2": row["par_w_m2"],
                    "par_mol_m2_day": row["par_mol_m2_day"],
                    "srad_w_m2": row["srad_w_m2"],
                    "vp_Pa": row["vp_Pa"],
                    "dayl_s": row["dayl_s"],
                    "temp": temp_mean,
                })
        write_csv(OUT / f"{site}_daymet_daily_2010-2024.csv", fieldnames, rows)


def site_from_path(path: Path) -> str:
    for part in path.parts:
        if part in SITE_MAP:
            return SITE_MAP[part]
    name = path.name.upper()
    if "_PIN_" in name or name.startswith("FLP_PIN") or name.startswith("UNS_PIN"):
        return "PIN"
    if "_PIK_" in name or name.startswith("FLP_PIK") or name.startswith("UNS_PIK"):
        return "PIK"
    return ""


def combine_raw_csvs(paths, derived_fields, derive_row):
    raw_rows = []
    extra_fields = []
    seen_fields = set()

    for path in paths:
        with path.open() as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                continue
            for field in reader.fieldnames:
                if field not in seen_fields and field not in derived_fields:
                    seen_fields.add(field)
                    extra_fields.append(field)
            for row in reader:
                derived = derive_row(path, row)
                if not derived:
                    continue
                raw_rows.append((derived, row))

    fieldnames = list(derived_fields) + extra_fields
    rows = []
    for derived, row in raw_rows:
        combined = {field: derived.get(field, "") for field in derived_fields}
        for field in extra_fields:
            combined[field] = row.get(field, "")
        rows.append(combined)
    return fieldnames, rows


def project_rows(fieldnames, rows, keep_fields):
    """Keep only viz-ready columns (drops spectral bands and other wide raw fields)."""
    present = set(fieldnames)
    out_fields = [field for field in keep_fields if field in present]
    out_rows = [{field: row.get(field, "") for field in out_fields} for row in rows]
    return out_fields, out_rows


def build_fluorescence():
    paths = sorted((SRC / "Fluorescence").rglob("FLP_*.csv"))

    def derive_row(path: Path, row: dict):
        site = site_from_path(path)
        if not site:
            return None
        dt = (row.get("datetime_est") or row.get("date") or "").strip()
        date = dt[:10] if dt else ""
        if not date or date == "NA":
            return None
        year = parse_year(path.name) or date[:4]
        return {"site": site, "year": year, "date": date}

    fieldnames, rows = combine_raw_csvs(paths, ["site", "year", "date"], derive_row)
    fieldnames, rows = project_rows(fieldnames, rows, FLUORESCENCE_KEEP)
    rows.sort(key=lambda r: (r["site"], r["year"], r["date"], r.get("datetime_est", ""), r.get("primary_key", "")))
    write_csv(OUT / "fluorescence_indices.csv", fieldnames, rows)
    return rows


def build_reflectance():
    paths = sorted((SRC / "Reflectance").rglob("UNS_*.csv"))

    def derive_row(path: Path, row: dict):
        site = site_from_path(path)
        if not site:
            return None
        date = (row.get("date") or "").strip()[:10]
        if not date:
            date = parse_date_from_name(path.name)
        if not date:
            return None
        year = parse_year(path.parent.name) or parse_year(path.name) or date[:4]
        return {"site": site, "year": year, "date": date}

    fieldnames, rows = combine_raw_csvs(paths, ["site", "year", "date"], derive_row)
    fieldnames, rows = project_rows(fieldnames, rows, REFLECTANCE_KEEP)
    rows.sort(key=lambda r: (r["site"], r["year"], r["date"], r.get("time", ""), r.get("primary_key", "")))
    write_csv(OUT / "reflectance_indices.csv", fieldnames, rows)
    return rows


def build_weather():
    copy_weather()
    copy_eccc_hourly()
    build_daymet_weather()


def build_parquet(*, force: bool = False, weather_only: bool = False):
    import sys

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from backend.services.parquet_store import build_all, build_target

    if weather_only:
        from backend.services import datasets

        paths = []
        for name, out_path, csv_paths in datasets.parquet_build_targets():
            if not name.startswith("weather_"):
                continue
            out = build_target(name, out_path, csv_paths, force=force)
            if out is not None:
                paths.append(out)
        return paths

    return build_all(force=force)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Build FastPheno CSV exports from III_db_final")
    parser.add_argument(
        "--weather-only",
        action="store_true",
        help="Refresh all ECCC daily + hourly and Daymet daily CSVs and Parquet only",
    )
    args = parser.parse_args()

    if args.weather_only:
        build_weather()
        paths = build_parquet(force=True, weather_only=True)
        print("weather: ECCC daily 2010-2024 copied for", ", ".join(eccc_weather_sites()))
        print("weather: ECCC hourly 2022-2024 copied for", ", ".join(eccc_weather_sites()))
        print("weather: Daymet daily 2010-2024 built for", ", ".join(eccc_weather_sites()))
        print(f"parquet: {len(paths)} weather file(s) in data/fastpheno/parquet/")
        return

    build_weather()
    fluor = build_fluorescence()
    refl = build_reflectance()
    print("weather: ECCC daily 2010-2024 copied for", ", ".join(eccc_weather_sites()))
    print("weather: ECCC hourly 2022-2024 copied for", ", ".join(eccc_weather_sites()))
    print("weather: Daymet daily 2010-2024 built for", ", ".join(eccc_weather_sites()))
    print(f"fluorescence_indices.csv: {len(fluor)} rows")
    print(f"reflectance_indices.csv: {len(refl)} rows")
    paths = build_parquet(force=True)
    print(f"parquet: {len(paths)} file(s) in data/fastpheno/parquet/")


if __name__ == "__main__":
    main()
