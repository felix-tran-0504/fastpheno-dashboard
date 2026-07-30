#!/usr/bin/env python3
"""Verify derived FastPheno CSVs match III_db_final source rows."""

import csv
import re
import sys
from pathlib import Path

from prepare_fastpheno_data import FLUORESCENCE_KEEP, REFLECTANCE_KEEP, project_rows

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
    name = path.name.upper()
    if "_PIN_" in name or name.startswith("FLP_PIN") or name.startswith("UNS_PIN"):
        return "PIN"
    if "_PIK_" in name or name.startswith("FLP_PIK") or name.startswith("UNS_PIK"):
        return "PIK"
    return ""


def norm_row(row: dict) -> dict:
    out = {}
    for key, value in row.items():
        if key in ("site", "year", "date"):
            out[key] = str(value)
        elif key == "n_measurements":
            out[key] = int(value)
        else:
            try:
                out[key] = float(value) if value not in ("", None) else ""
            except (TypeError, ValueError):
                out[key] = value
    return out


def read_csv_rows(path: Path) -> list[dict]:
    with path.open() as handle:
        return [norm_row(row) for row in csv.DictReader(handle)]


def combine_raw_rows(paths, derived_fields, derive_row):
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

    rows = []
    for derived, row in raw_rows:
        combined = {field: derived.get(field, "") for field in derived_fields}
        for field in extra_fields:
            combined[field] = row.get(field, "")
        rows.append(norm_row(combined))
    return rows


def build_expected_fluorescence() -> list[dict]:
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

    rows = combine_raw_rows(sorted((SRC / "Fluorescence").rglob("FLP_*.csv")), ["site", "year", "date"], derive_row)
    if rows:
        _, rows = project_rows(list(rows[0].keys()), rows, FLUORESCENCE_KEEP)
    rows.sort(key=lambda r: (r["site"], r["year"], r["date"], r.get("datetime_est", ""), r.get("primary_key", "")))
    return rows


def build_expected_reflectance() -> list[dict]:
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

    rows = combine_raw_rows(sorted((SRC / "Reflectance").rglob("UNS_*.csv")), ["site", "year", "date"], derive_row)
    if rows:
        _, rows = project_rows(list(rows[0].keys()), rows, REFLECTANCE_KEEP)
    rows.sort(key=lambda r: (r["site"], r["year"], r["date"], r.get("time", ""), r.get("primary_key", "")))
    return rows


def compare(name: str, expected: list[dict], actual: list[dict]) -> bool:
    if expected == actual:
        print(f"OK  {name}: {len(actual)} rows match source rows")
        return True

    print(f"FAIL {name}: expected {len(expected)} rows, got {len(actual)}")
    for idx, (exp_row, act_row) in enumerate(zip(expected, actual)):
        if exp_row != act_row:
            print(f"  first mismatch at row {idx}:")
            print(f"    expected: {exp_row}")
            print(f"    actual:   {act_row}")
            break
    if len(expected) != len(actual):
        print("  row count differs")
    return False


def main() -> int:
    if not SRC.is_dir():
        print(f"Source database not found: {SRC}", file=sys.stderr)
        return 1

    ok = True
    ok &= compare(
        "fluorescence_indices.csv",
        build_expected_fluorescence(),
        read_csv_rows(OUT / "fluorescence_indices.csv"),
    )
    ok &= compare(
        "reflectance_indices.csv",
        build_expected_reflectance(),
        read_csv_rows(OUT / "reflectance_indices.csv"),
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
