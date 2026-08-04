#!/usr/bin/env python3
"""Build Parquet query files from data/fastpheno/*.csv exports."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services import datasets, parquet_store  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Parquet query layer from FastPheno CSVs")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild all Parquet files even when CSV mtime is unchanged",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 if any Parquet file is missing or stale (no build)",
    )
    args = parser.parse_args()

    if args.check:
        missing = parquet_store.missing_parquet()
        stale = parquet_store.stale_parquet()
        if missing:
            print("Missing Parquet:", ", ".join(p.name for p in missing))
        if stale:
            print("Stale Parquet:", ", ".join(p.name for p in stale))
        return 1 if (missing or stale) else 0

    print(f"CSV source dir:  {datasets.DATA_DIR}")
    print(f"Parquet out dir: {datasets.PARQUET_DIR}")
    built = parquet_store.build_all(force=args.force)
    for path in built:
        rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        size_mb = path.stat().st_size / (1024 * 1024)
        print(f"  {rel} ({size_mb:.2f} MB)")
    print(f"Done — {len(built)} Parquet file(s) ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
