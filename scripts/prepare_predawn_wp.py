#!/usr/bin/env python3
"""Export predawn water potential from III_db_final PredawnWaterPotential/."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from fastpheno_env import get_iii_db_root, load_env

load_env()

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = get_iii_db_root() / "PredawnWaterPotential" / "Process"
OUT = ROOT / "data" / "fastpheno" / "predawn_wp_2023.csv"
KEEP = ["site", "date", "Cluster", "Genotype", "wp_pd"]


def find_source(src_dir: Path) -> Path:
    preferred = src_dir / "SPC_PreWP_2023.csv"
    if preferred.is_file():
        return preferred
    matches = sorted(src_dir.glob("SPC_PreWP_*.csv"))
    if matches:
        return matches[-1]
    raise FileNotFoundError(f"No SPC_PreWP_*.csv under {src_dir}")


def export(src_file: Path, out_path: Path) -> int:
    with src_file.open(newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            site = (row.get("site") or "").strip().upper()
            if not site:
                continue
            rows.append(
                {
                    "site": site,
                    "date": (row.get("date") or "").strip()[:10],
                    "Cluster": (row.get("Cluster") or "").strip(),
                    "Genotype": str(row.get("Genotype") or "").strip(),
                    "wp_pd": (row.get("wp_pd") or "").strip(),
                }
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=KEEP)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC, help="PredawnWaterPotential/Process folder")
    parser.add_argument("--out", type=Path, default=OUT, help="Output CSV path")
    args = parser.parse_args()

    if not args.src.is_dir():
        print(f"Source folder not found: {args.src}", file=sys.stderr)
        return 1

    try:
        src_file = find_source(args.src)
    except FileNotFoundError as exc:
        print(exc, file=sys.stderr)
        return 1

    n = export(src_file, args.out)
    print(f"predawn_wp: {src_file.name} -> {args.out.name} ({n} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
