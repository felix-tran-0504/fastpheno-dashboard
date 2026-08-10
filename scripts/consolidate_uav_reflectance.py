#!/usr/bin/env python3
"""Merge all UAV reflectance CSVs under one directory into one file per year."""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from pathlib import Path

SITE_MAP = {"Pickering": "PIK", "Pintendre": "PIN"}
YEAR_IN_PATH = re.compile(r"/(20\d{2})/")
DATE_IN_PATH = re.compile(r"(20\d{2}-\d{2}-\d{2})")
META_FIELDS = ["site", "year", "flight_date", "dataset", "source_file"]
BAND_COLUMN = re.compile(r"^\d+nm$")
from fastpheno_env import get_iii_db_root, load_env

load_env()
DEFAULT_SRC = Path(__file__).resolve().parents[1] / "uav-reflectance"
FALLBACK_SRC = get_iii_db_root() / "UAV-Reflectance"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "fastpheno"


def classify_dataset(name: str) -> str:
    if "HyperspectralMetrics" in name:
        return "hyperspectral_metrics"
    if "ReflectanceCurves" in name:
        return "reflectance_curves"
    return "unknown"


def include_source_file(path: Path) -> bool:
    """Keep index/metric exports only; spectral curve files are band-only."""
    return "HyperspectralMetrics" in path.name


def keep_column(name: str) -> bool:
    return not BAND_COLUMN.fullmatch(name)


def parse_site(path: Path) -> str:
    for part in path.parts:
        if part in SITE_MAP:
            return SITE_MAP[part]
    return ""


def parse_year(path: Path) -> str:
    match = YEAR_IN_PATH.search(path.as_posix())
    if match:
        return match.group(1)
    match = re.search(r"(20\d{2})", path.name)
    return match.group(1) if match else ""


def parse_flight_date(path: Path) -> str:
    for part in path.parts:
        match = DATE_IN_PATH.search(part)
        if match:
            return match.group(1)
    match = DATE_IN_PATH.search(path.name)
    return match.group(1) if match else ""


def collect_csvs(src: Path) -> dict[str, list[Path]]:
    by_year: dict[str, list[Path]] = defaultdict(list)
    for path in sorted(src.rglob("*.csv")):
        if not include_source_file(path):
            continue
        year = parse_year(path)
        if not year:
            raise SystemExit(f"Could not infer year for {path}")
        by_year[year].append(path)
    return by_year


def fieldnames_for_year(paths: list[Path]) -> list[str]:
    fields = list(META_FIELDS)
    seen = set(fields)
    for path in paths:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                continue
            for name in reader.fieldnames:
                if not keep_column(name):
                    continue
                if name not in seen:
                    seen.add(name)
                    fields.append(name)
    return fields


def write_year(paths: list[Path], out_path: Path) -> tuple[int, int]:
    fieldnames = fieldnames_for_year(paths)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    row_count = 0
    with out_path.open("w", newline="", encoding="utf-8") as out_handle:
        writer = csv.DictWriter(out_handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for path in paths:
            site = parse_site(path)
            year = parse_year(path)
            flight_date = parse_flight_date(path)
            dataset = classify_dataset(path.name)
            with path.open(newline="", encoding="utf-8") as in_handle:
                reader = csv.DictReader(in_handle)
                for row in reader:
                    out_row = {name: row.get(name, "") for name in fieldnames}
                    out_row.update({
                        "site": site,
                        "year": year,
                        "flight_date": flight_date,
                        "dataset": dataset,
                        "source_file": path.name,
                    })
                    writer.writerow(out_row)
                    row_count += 1
    return row_count, len(fieldnames)


def resolve_src(path: Path | None) -> Path:
    if path is not None:
        if not path.is_dir():
            raise SystemExit(f"Input directory not found: {path}")
        return path
    if DEFAULT_SRC.is_dir():
        return DEFAULT_SRC
    if FALLBACK_SRC.is_dir():
        return FALLBACK_SRC
    raise SystemExit(
        f"No input directory found. Add CSVs under {DEFAULT_SRC} "
        f"or pass --src explicitly."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, default=None, help="uav-reflectance source folder")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    parser.add_argument("--no-parquet", action="store_true", help="skip Parquet rebuild")
    args = parser.parse_args()

    src = resolve_src(args.src)
    by_year = collect_csvs(src)
    if not by_year:
        raise SystemExit(f"No CSV files found under {src}")

    print(f"Source: {src}")
    print(f"Output: {args.out}")
    for year in sorted(by_year):
        out_path = args.out / f"uav_reflectance_{year}.csv"
        rows, cols = write_year(by_year[year], out_path)
        print(f"  {year}: {len(by_year[year])} files -> {out_path.name} ({rows:,} rows, {cols} columns)")

    if args.no_parquet:
        return

    import sys

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from backend.services.parquet_store import build_all

    built = build_all(force=False)
    uav_pq = [p for p in built if p.name.startswith("uav_reflectance_")]
    print(f"Parquet: {len(uav_pq)} UAV file(s) updated in data/fastpheno/parquet/")


if __name__ == "__main__":
    main()
