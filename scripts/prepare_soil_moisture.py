#!/usr/bin/env python3
"""Export III_db_final SoilMoisture CSVs into data/fastpheno/soil_moisture.csv."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from fastpheno_env import get_iii_db_root, load_env

load_env()
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = get_iii_db_root() / "SoilMoisture"
OUT = ROOT / "data" / "fastpheno" / "soil_moisture.csv"

SITE_MAP = {
    "Pickering": "PIK",
    "Pintendre": "PIN",
    "PIK": "PIK",
    "PIN": "PIN",
}

FIELDNAMES = [
    "site",
    "sensor_id",
    "date",
    "time",
    "datetime",
    "vwc",
    "st",
    "elevation_m",
    "week_label",
]


def site_from_path(path: Path) -> str:
    for part in path.parts:
        if part in SITE_MAP:
            return SITE_MAP[part]
    return ""


def parse_float(value: str) -> str:
    value = (value or "").strip()
    return value if value else ""


def iter_source_rows(src_root: Path):
    for csv_path in sorted(src_root.rglob("*.csv")):
        site = site_from_path(csv_path)
        if not site:
            print(f"  skip (no site): {csv_path}", file=sys.stderr)
            continue
        with csv_path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                date = (row.get("date") or "").strip()
                time = (row.get("time") or "").strip()
                if not date:
                    continue
                datetime = f"{date} {time}" if time else date
                yield {
                    "site": site,
                    "sensor_id": (row.get("ID") or "").strip(),
                    "date": date,
                    "time": time,
                    "datetime": datetime,
                    "vwc": parse_float(row.get("VWC", "")),
                    "st": parse_float(row.get("ST", "")),
                    "elevation_m": parse_float(row.get("elevation", "")),
                    "week_label": (row.get("week_label") or "").strip(),
                }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build soil_moisture.csv from III_db_final")
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC, help="SoilMoisture source folder")
    parser.add_argument("--out", type=Path, default=OUT, help="Output CSV path")
    args = parser.parse_args()

    if not args.src.is_dir():
        print(f"Source folder not found: {args.src}", file=sys.stderr)
        return 1

    rows = list(iter_source_rows(args.src))
    if not rows:
        print(f"No soil moisture rows found under {args.src}", file=sys.stderr)
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    sites = sorted({row["site"] for row in rows})
    sensors = sorted({row["sensor_id"] for row in rows if row["sensor_id"]})
    print(f"Wrote {len(rows):,} rows → {args.out}")
    print(f"  sites: {', '.join(sites)}")
    print(f"  sensors: {len(sensors)} ({', '.join(sensors)})")
    print(f"  dates: {rows[0]['date']} to {rows[-1]['date']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
