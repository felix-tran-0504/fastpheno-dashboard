#!/usr/bin/env python3
"""Merge UAV LiDAR and GNSS CSVs into one export per dataset, site, and year."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

SITE_MAP = {"Pickering": "PIK", "Pintendre": "PIN"}
FLIGHT_FOLDER = re.compile(r"^(20\d{2}-\d{2}-\d{2}(?:_\d+)?)$")
FLIGHT_DATE = re.compile(r"(20\d{2}-\d{2}-\d{2})")

from fastpheno_env import get_iii_db_root, load_env

load_env()
DEFAULT_SRC = get_iii_db_root() / "UAV-SpatialInformation"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "fastpheno"

LIDAR_FILE = "treeSpatialMetrics.csv"
GNSS_FILE = "treeTop.csv"

META_FIELDS = ["site", "year", "flight_date", "flight_id", "source_file", "site_treeid"]
LIDAR_METRICS = [
    "tree_height_corrected_m",
    "canopy_area_m2",
    "tree_altitude_m",
]
GNSS_METRICS = ["treeTop_x", "treeTop_y", "treeTop_x_std", "treeTop_y_std"]


def parse_site(path: Path) -> str:
    for part in path.parts:
        if part in SITE_MAP:
            return SITE_MAP[part]
    return ""


def parse_year(path: Path) -> str:
    match = re.search(r"/(20\d{2})/", path.as_posix())
    if match:
        return match.group(1)
    match = re.search(r"(20\d{2})", path.name)
    return match.group(1) if match else ""


def parse_flight_id(path: Path) -> str:
    for part in path.parts:
        if FLIGHT_FOLDER.match(part):
            return part
    match = FLIGHT_DATE.search(path.name)
    return match.group(1) if match else ""


def parse_flight_date(flight_id: str) -> str:
    match = FLIGHT_DATE.search(flight_id)
    return match.group(1) if match else ""


def classify_kind(path: Path) -> str | None:
    name = path.name
    if name.endswith(LIDAR_FILE) or "treeSpatialMetrics" in name:
        return "lidar"
    if name.endswith(GNSS_FILE) or "treeTop" in name:
        return "gnss"
    return None


def metric_fields(kind: str) -> list[str]:
    return LIDAR_METRICS if kind == "lidar" else GNSS_METRICS


def collect_sources(src: Path) -> dict[tuple[str, str, str], list[Path]]:
    groups: dict[tuple[str, str, str], list[Path]] = defaultdict(list)
    for path in sorted(src.rglob("*.csv")):
        kind = classify_kind(path)
        if not kind:
            continue
        site = parse_site(path)
        year = parse_year(path)
        if not site or not year:
            raise SystemExit(f"Could not infer site/year for {path}")
        groups[(kind, site.lower(), year)].append(path)
    return groups


def write_group(kind: str, site: str, year: str, paths: list[Path], out_path: Path) -> int:
    fieldnames = META_FIELDS + metric_fields(kind)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    row_count = 0
    with out_path.open("w", newline="", encoding="utf-8") as out_handle:
        writer = csv.DictWriter(out_handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for path in paths:
            flight_id = parse_flight_id(path)
            flight_date = parse_flight_date(flight_id)
            with path.open(newline="", encoding="utf-8") as in_handle:
                reader = csv.DictReader(in_handle)
                for row in reader:
                    writer.writerow({
                        "site": site.upper(),
                        "year": year,
                        "flight_date": flight_date,
                        "flight_id": flight_id,
                        "source_file": path.name,
                        "site_treeid": row.get("site_treeid", ""),
                        **{name: row.get(name, "") for name in metric_fields(kind)},
                    })
                    row_count += 1
    return row_count


def resolve_src(path: Path | None) -> Path:
    if path is not None:
        if not path.is_dir():
            raise SystemExit(f"Input directory not found: {path}")
        return path
    if DEFAULT_SRC.is_dir():
        return DEFAULT_SRC
    raise SystemExit(
        f"No input directory found. Pass --src (expected {DEFAULT_SRC})."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, default=None, help="UAV-SpatialInformation folder")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory")
    parser.add_argument("--no-parquet", action="store_true", help="skip Parquet rebuild")
    args = parser.parse_args()

    src = resolve_src(args.src)
    groups = collect_sources(src)
    if not groups:
        raise SystemExit(f"No LiDAR/GNSS CSV files found under {src}")

    print(f"Source: {src}")
    print(f"Output: {args.out}")
    written: list[Path] = []
    for (kind, site, year) in sorted(groups):
        out_path = args.out / f"uav_{kind}_{site}_{year}.csv"
        rows = write_group(kind, site, year, groups[(kind, site, year)], out_path)
        n_files = len(groups[(kind, site, year)])
        n_cols = len(META_FIELDS) + len(metric_fields(kind))
        print(f"  uav_{kind}_{site}_{year}.csv: {n_files} files -> {rows:,} rows, {n_cols} columns")
        written.append(out_path)

    if args.no_parquet:
        return

    root = Path(__file__).resolve().parents[1]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from backend.services.parquet_store import build_one

    built = [build_one(path, force=False) for path in written]
    built = [p for p in built if p is not None]
    print(f"Parquet: {len(built)} spatial file(s) updated in data/fastpheno/parquet/")


if __name__ == "__main__":
    main()
