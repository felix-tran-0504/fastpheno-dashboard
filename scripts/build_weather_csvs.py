#!/usr/bin/env python3
"""Build dashboard weather CSVs from ECCC daily sources only."""

import csv
from pathlib import Path

SRC = Path("/Users/felixtran/Downloads/III_db_final/Weather/ECCC")
OUT = Path(__file__).resolve().parent.parent / "data" / "fastpheno"

SITES = ("PIK", "PIN")
YEAR_FROM = 2022
YEAR_TO = 2024
OUT_COLS = ("site_id", "date", "temp", "max_temp", "min_temp", "precip_amt")


def parse_float(val):
    if val in ("", "NA", None):
        return None
    try:
        return float(val)
    except ValueError:
        return None


def build_site_csv(site):
    daily_path = SRC / site / "Daily" / f"{site}_daily_2010-{YEAR_TO}.csv"
    rows = []

    with open(daily_path, newline="") as f:
        for row in csv.DictReader(f):
            date = row["date"]
            year = int(date[:4])
            if year < YEAR_FROM or year > YEAR_TO:
                continue
            rows.append({
                "site_id": row["site_id"],
                "date": date,
                "temp": parse_float(row.get("temp")),
                "max_temp": parse_float(row.get("max_temp")),
                "min_temp": parse_float(row.get("min_temp")),
                "precip_amt": parse_float(row.get("precip_amt")),
            })

    out_path = OUT / f"weather_{site.lower()}_{YEAR_FROM}-{YEAR_TO}.csv"
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUT_COLS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {out_path.name}: {len(rows)} rows")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for site in SITES:
        build_site_csv(site)


if __name__ == "__main__":
    main()
