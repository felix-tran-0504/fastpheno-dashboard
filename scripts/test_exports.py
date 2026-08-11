#!/usr/bin/env python3
"""Smoke-test Parquet export endpoints (client vs server paths)."""

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.app import app
from backend.services import query_engine

client = TestClient(app)


def _count_csv_rows(text: str) -> int:
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    return max(0, len(rows) - 1)


def _parquet_count(domain: str, **filters) -> int:
    spec = query_engine.prepare_export(domain, **filters)
    return spec.total


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("parquet_ready") is True, body
    print("OK  /api/health parquet_ready=true")


def test_export_meta():
    cases = [
        ("fluorescence", {}, "client"),
        ("reflectance", {}, "client"),
        ("wp", {}, "client"),
        ("uav", {"year": 2022}, "client"),
        ("uav", {"year": 2023}, "server"),
        ("soil_moisture", {"site": "PIK"}, "server"),
        ("lidar", {"site": "PIN", "year": 2023}, "server"),
        ("gnss", {"site": "PIK", "year": 2022}, "server"),
        ("weather", {"source": "daymet", "site": "PIN"}, "client"),
    ]
    for domain, params, expected_method in cases:
        r = client.get(f"/api/query/{domain}/export/meta", params=params)
        assert r.status_code == 200, f"{domain} meta: {r.status_code} {r.text}"
        body = r.json()
        assert body["method"] == expected_method, (domain, body)
        pq = _parquet_count(domain, **params)
        assert body["total"] == pq, (domain, body["total"], pq)
        print(f"OK  export/meta {domain} total={body['total']} method={body['method']}")


def test_client_exports():
    cases = [
        ("fluorescence", {}, "fluorescence_indices.csv"),
        ("reflectance", {}, "reflectance_indices.csv"),
        ("wp", {}, "predawn_wp_2023.csv"),
        ("uav", {"year": 2022}, "uav_reflectance_2022.csv"),
        ("weather", {"source": "eccc", "resolution": "daily", "site": "PIN"}, None),
    ]
    for domain, params, _filename in cases:
        meta = client.get(f"/api/query/{domain}/export/meta", params=params).json()
        rows_r = client.get(f"/api/query/{domain}/rows", params={**params, "all": "true"})
        assert rows_r.status_code == 200, rows_r.text
        api_rows = len(rows_r.json().get("rows") or [])
        assert api_rows == meta["total"], (domain, api_rows, meta["total"])
        print(f"OK  client rows {domain} count={api_rows}")


def test_server_exports():
    cases = [
        ("soil_moisture", {"site": "PIK"}),
        ("lidar", {"site": "PIN", "year": 2023}),
        ("gnss", {"site": "PIK", "year": 2022}),
    ]
    for domain, params in cases:
        meta = client.get(f"/api/query/{domain}/export/meta", params=params).json()
        r = client.get(f"/api/query/{domain}/export.csv", params=params)
        assert r.status_code == 200, f"{domain} export: {r.status_code} {r.text[:200]}"
        assert "text/csv" in r.headers.get("content-type", ""), r.headers
        csv_rows = _count_csv_rows(r.text)
        assert csv_rows == meta["total"], (domain, csv_rows, meta["total"])
        assert csv_rows > 0, domain
        print(f"OK  server export.csv {domain} rows={csv_rows}")


def test_uav_server_export_small_year():
    """UAV by year stays client-side but export.csv should still work."""
    params = {"year": 2023, "site": "PIN"}
    meta = client.get("/api/query/uav/export/meta", params=params).json()
    assert meta["method"] == "client"
    r = client.get("/api/query/uav/export.csv", params=params)
    assert r.status_code == 200, r.text[:200]
    csv_rows = _count_csv_rows(r.text)
    assert csv_rows == meta["total"]
    print(f"OK  uav export.csv (client-class) rows={csv_rows}")


def main() -> None:
    query_engine.init_duckdb()
    test_health()
    test_export_meta()
    test_client_exports()
    test_server_exports()
    test_uav_server_export_small_year()
    print("\nAll export tests passed.")


if __name__ == "__main__":
    main()
