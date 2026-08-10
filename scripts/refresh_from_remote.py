#!/usr/bin/env python3
"""
Pull latest III_db_final from ffgg-fastpheno2, rebuild CSVs + Parquet.

Usage (after filling backend/.env):
  python3 scripts/refresh_from_remote.py
  python3 scripts/refresh_from_remote.py --skip-sync    # use existing local staging
  python3 scripts/refresh_from_remote.py --weather-only
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent


def _run(cmd: list[str]) -> None:
    print(f"\n>> {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def _run_optional(cmd: list[str], label: str) -> None:
    """Run a prep step; warn and continue if source folders are absent."""
    print(f"\n>> {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        print(f"Warning: {label} step failed (exit {result.returncode}); continuing.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync III_db_final from UofT host and refresh dashboard data"
    )
    parser.add_argument(
        "--skip-sync",
        action="store_true",
        help="Skip SFTP sync; use existing FASTPHENO_III_DB_ROOT",
    )
    parser.add_argument(
        "--dry-run-sync",
        action="store_true",
        help="Pass --dry-run to sync step only",
    )
    parser.add_argument(
        "--weather-only",
        action="store_true",
        help="Refresh weather CSVs and Parquet only",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Run verify_fastpheno_data.py after prep",
    )
    parser.add_argument(
        "--no-parquet",
        action="store_true",
        help="Skip build_parquet.py (prepare CSVs only)",
    )
    args = parser.parse_args()

    py = sys.executable

    if not args.skip_sync:
        sync_cmd = [py, str(SCRIPTS / "sync_iii_db_final.py")]
        if args.dry_run_sync:
            sync_cmd.append("--dry-run")
        _run(sync_cmd)
        if args.dry_run_sync:
            print("\nDry run complete; no prep/build steps run.")
            return

    prep_cmd = [py, str(SCRIPTS / "prepare_fastpheno_data.py")]
    if args.weather_only:
        prep_cmd.append("--weather-only")
    _run(prep_cmd)

    if not args.weather_only:
        _run_optional(
            [py, str(SCRIPTS / "prepare_predawn_wp.py")],
            "Predawn water potential",
        )
        _run_optional(
            [py, str(SCRIPTS / "consolidate_uav_reflectance.py"), "--no-parquet"],
            "UAV reflectance",
        )
        _run_optional(
            [py, str(SCRIPTS / "consolidate_uav_spatial.py"), "--no-parquet"],
            "UAV LiDAR/GNSS",
        )
        _run_optional(
            [py, str(SCRIPTS / "prepare_soil_moisture.py")],
            "Soil moisture",
        )

    if args.verify:
        verify_cmd = [py, str(SCRIPTS / "verify_fastpheno_data.py")]
        if args.weather_only:
            verify_cmd.append("--weather-only")
        _run(verify_cmd)

    if not args.no_parquet and not args.weather_only:
        _run([py, str(SCRIPTS / "build_parquet.py"), "--force"])
    elif not args.no_parquet and args.weather_only:
        pass  # prepare_fastpheno_data --weather-only already rebuilds weather parquet

    print("\nRefresh complete. Restart the API if it is already running:")
    print("  python3 -m uvicorn backend.app:app --reload --port 8000")


if __name__ == "__main__":
    main()
