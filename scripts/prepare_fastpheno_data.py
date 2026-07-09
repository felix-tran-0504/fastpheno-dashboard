#!/usr/bin/env python3
"""Extract browser-sized FastPheno CSVs from III_db_final."""

import csv
import re
import shutil
from collections import defaultdict
from pathlib import Path
from statistics import mean

SRC = Path("/Users/felixtran/Downloads/III_db_final")
OUT = Path(__file__).resolve().parents[1] / "data" / "fastpheno"
SITE_MAP = {"Pintendre": "PIN", "Pickering": "PIK"}
DATE_IN_NAME = re.compile(r"(20\d{2}-\d{2}-\d{2})")


def parse_year(text: str) -> str:
    match = re.search(r"(20\d{2})", text)
    return match.group(1) if match else ""


def parse_date_from_name(name: str) -> str:
    match = DATE_IN_NAME.search(name)
    return match.group(1) if match else ""


def site_from_path(path: Path) -> str:
    for part in path.parts:
        if part in SITE_MAP:
            return SITE_MAP[part]
    return "PIN" if "PIN" in path.name else "PIK" if "PIK" in path.name else ""


def write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def copy_weather():
    for site in ("PIK", "PIN"):
        src = SRC / "Weather" / "ECCC" / site / "Daily" / f"{site}_daily_2010-2024.csv"
        dst = OUT / f"{site}_daily_2010-2024.csv"
        shutil.copy2(src, dst)


def build_fluorescence():
    groups = defaultdict(lambda: {"QY_max": [], "NPQ_Lss": []})
    for path in sorted((SRC / "Fluorescence").rglob("FLP_*.csv")):
        site = "PIN" if "PIN" in path.name else "PIK"
        file_year = parse_year(path.name)
        with path.open() as handle:
            for row in csv.DictReader(handle):
                dt = (row.get("datetime_est") or row.get("date") or "").strip()
                date = dt[:10] if dt else ""
                if not date or date == "NA":
                    continue
                year = file_year or date[:4]
                key = (site, year, date)
                for col in ("QY_max", "NPQ_Lss"):
                    val = row.get(col)
                    if val in (None, "", "NA"):
                        continue
                    try:
                        groups[key][col].append(float(val))
                    except ValueError:
                        pass

    rows = []
    for (site, year, date), vals in sorted(groups.items()):
        if not vals["QY_max"] and not vals["NPQ_Lss"]:
            continue
        rows.append({
            "site": site,
            "year": year,
            "date": date,
            "QY_max": round(mean(vals["QY_max"]), 3) if vals["QY_max"] else "",
            "NPQ_Lss": round(mean(vals["NPQ_Lss"]), 3) if vals["NPQ_Lss"] else "",
            "n_measurements": max(len(vals["QY_max"]), len(vals["NPQ_Lss"])),
        })
    write_csv(OUT / "fluorescence_indices.csv",
              ["site", "year", "date", "QY_max", "NPQ_Lss", "n_measurements"], rows)
    return rows


def build_reflectance():
    groups = defaultdict(lambda: {"NDVI": [], "PRI": [], "GNDVI": []})
    for path in sorted((SRC / "Reflectance").rglob("UNS_*.csv")):
        site = site_from_path(path)
        file_year = parse_year(path.parent.name) or parse_year(path.name)
        fallback_date = parse_date_from_name(path.name)
        with path.open() as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                continue
            has_date_col = "date" in reader.fieldnames
            for row in reader:
                date = (row.get("date") or "").strip()[:10]
                if not date:
                    date = fallback_date
                if not date:
                    continue
                year = file_year or date[:4]
                key = (site, year, date)
                for col in ("NDVI", "PRI", "GNDVI"):
                    val = row.get(col)
                    if val in (None, "", "NA"):
                        continue
                    try:
                        groups[key][col].append(float(val))
                    except ValueError:
                        pass
                if not has_date_col and fallback_date:
                    # One campaign file applies one date to all rows; don't duplicate per row keying.
                    pass

    rows = []
    for (site, year, date), vals in sorted(groups.items()):
        if not any(vals[col] for col in ("NDVI", "PRI", "GNDVI")):
            continue
        rows.append({
            "site": site,
            "year": year,
            "date": date,
            "NDVI": round(mean(vals["NDVI"]), 4) if vals["NDVI"] else "",
            "PRI": round(mean(vals["PRI"]), 4) if vals["PRI"] else "",
            "GNDVI": round(mean(vals["GNDVI"]), 4) if vals["GNDVI"] else "",
            "n_measurements": max(len(vals["NDVI"]), len(vals["PRI"]), len(vals["GNDVI"])),
        })
    write_csv(OUT / "reflectance_indices.csv",
              ["site", "year", "date", "NDVI", "PRI", "GNDVI", "n_measurements"], rows)
    return rows


def main():
    copy_weather()
    fluor = build_fluorescence()
    refl = build_reflectance()
    print(f"weather: PIK/PIN daily 2010-2024 copied")
    print(f"fluorescence_indices.csv: {len(fluor)} rows")
    print(f"reflectance_indices.csv: {len(refl)} rows")


if __name__ == "__main__":
    main()
