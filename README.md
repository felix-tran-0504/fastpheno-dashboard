# FastPheno Plant Physiology Dashboard

A browser-based dashboard for exploring FastPheno field data from the `III_db_final` research collection. It covers climate/weather, leaf reflectance, chlorophyll fluorescence, predawn water potential, soil moisture, UAV hyperspectral indices, LiDAR structure, GNSS geolocation, and pigment campaign downloads across Pickering (PIK), Pintendre (PIN), and additional ECCC weather station codes.

The app is a single HTML dashboard backed by a **FastAPI query API**. Sensor data is **lazy-loaded** on demand (no bulk CSV parsing in the browser). CSV exports remain the source of truth; the API queries **consolidated Parquet** files built from those CSVs.

## Features

### Environmental
- **Climate** — ECCC daily and hourly records plus Daymet daily (2010–2024); nine station codes (CSI, FMM, GP, PIK, PIN, SCA, SM, TP39, TPD); single-day detail or date-range charts
- **Soil moisture** — field sensor time series with per-sensor filtering and hourly/daily/weekly/monthly aggregation

### Ground campaigns
- **Fluorescence** — campaign metrics (e.g. QY<sub>max</sub>, NPQ); **Compare dates** or **Date range**; scatter-box charts by tree
- **Leaf reflectance** — vegetation indices (e.g. NDVI, PRI, GNDVI); same compare/range UX with site-aware date filters
- **Predawn water potential** — date-only comparison of Ψ<sub>pd</sub> by cluster and genotype
- **Pigments** — browse pigment campaigns by site and date range; download campaign folders as zip (reads from local `III_db_final` mirror, not Parquet)

### UAV
- **Hyp_spec** — tree-level hyperspectral index metrics (2022–2023); compare dates across flights or date-range table view
- **LiDAR** — tree height, location, and structural metrics by flight date
- **GNSS** — tree geolocation and GNSS metadata by flight date

### General
- **Metadata panels** — field descriptions loaded from markdown next to each sensor view
- **Tables + CSV download** — Tabulator tables (full-width layout) for selected series or filtered ranges
- **Remote sync** — selective SFTP pull from the UofT FastPheno host into a local staging folder, then automated CSV prep and Parquet rebuild

## Quick start

### Backend mode (required for sensor views)

```bash
cd "/path/to/PCA_C-SPIRIT Single Cell Papers_files"
python3 -m pip install -r backend/requirements.txt
python3 scripts/build_parquet.py    # first time, or after CSV updates
python3 -m uvicorn backend.app:app --reload --port 8000
```

Open [http://localhost:8000/fastpheno-dashboard.html](http://localhost:8000/fastpheno-dashboard.html)

Parquet files under `data/fastpheno/parquet/` are consolidated **one file per sensor** (weather uses three source files: `weather_eccc`, `weather_eccc_hourly`, `weather_daymet`). They are **auto-rebuilt on API startup** if missing or stale. Raw CSVs and markdown are still served at `/api/data/fastpheno/` for full downloads.

### Configuration

Copy `backend/.env.example` to `backend/.env` and fill in remote sync credentials when refreshing data from the UofT host:

| Variable | Purpose |
|----------|---------|
| `FASTPHENO_III_DB_ROOT` | Local mirror of selected remote folders (default `~/III_db_final_local`) |
| `FASTPHENO_PIGMENTS_ROOT` | Pigments campaign files (default `~/III_db_final_local/Pigments`) |
| `FASTPHENO_REMOTE_HOST` | `ffgg-fastpheno2.utm.utoronto.ca` |
| `FASTPHENO_REMOTE_USER` / `FASTPHENO_REMOTE_PASSWORD` | SSH/SFTP credentials |
| `FASTPHENO_REMOTE_III_DB_PATH` | Remote data root (default `/data/FastPheno/III_db_final`) |
| `FASTPHENO_SYNC_FOLDERS` | Comma-separated top-level folders to download (not the full server tree) |
| `FASTPHENO_REMOTE_SSH_KEY` | Optional SSH key instead of password |

Optional: set `FASTPHENO_DATA_DIR` if your data directory is not the repo default (`data/fastpheno`).

### Static file server (home page only)

```bash
python3 -m http.server 8090
```

Sensor views need the backend on port 8000 (or append `?api` when the dashboard is opened from another static host that proxies to the API).

## Dashboard UX

The home page groups entities into three domains — **Environmental**, **Ground**, and **UAV** — matching the FastPheno ERD. Data loads when you open a sensor tab (`ensureSensorReady`), not on initial page load.

| Entity | API domain | Site filter | Date modes | Chart |
|--------|------------|-------------|------------|-------|
| Climate | `weather` | All ECCC sites | Single day / Date range | Line (range) |
| Soil moisture | `soil_moisture` | PIK / PIN | Date range | Line (aggregated) |
| Fluorescence | `fluorescence` | PIK / PIN | Compare dates / Date range | Scatter-box |
| Leaf reflectance | `reflectance` | PIK / PIN | Compare dates / Date range | Scatter-box |
| Predawn WP | `wp` | — | Compare dates / Date range | Scatter-box |
| Pigments | `pigments` | PIK / PIN | Date range | Campaign list + zip download |
| Hyp_spec | `uav` | PIK / PIN | Compare dates / Date range | Scatter-box (compare) / line (range) |
| LiDAR | `lidar` | PIK / PIN | Flight date picker | Line (daily means) |
| GNSS | `gnss` | PIK / PIN | Flight date picker | Line (daily means) |

**Compare dates** — pick up to four site+date series, overlay on one chart, paginated metric table below.

**Date range** — filter all trees/measurements in a from/to window via the API (`all=true`).

## Project layout

```
fastpheno-dashboard.html          # Main dashboard (UAV / Ground / Environmental schema)
backend/
  app.py                            # FastAPI app, static files, Parquet warmup on startup
  config.py                         # Paths, row limits, pigments root resolution
  routers/
    data_files.py                   # CSV/MD file serving
    query.py                        # JSON query endpoints
    pigments.py                     # Pigment campaign listing and zip download
  services/
    datasets.py                     # Dataset registry (CSV sources + Parquet paths)
    parquet_registry.py             # Site/coverage discovery from Parquet
    parquet_store.py                # CSV → consolidated Parquet build / ensure
    query_engine.py                 # DuckDB queries over Parquet
    pigments.py                     # Pigments filesystem access
data/fastpheno/                   # CSV exports + metadata markdown
data/fastpheno/parquet/           # Query layer (generated; gitignored)
scripts/
  fastpheno_env.py                # Load backend/.env; resolve local/remote paths
  sync_iii_db_final.py            # Selective SFTP sync from UofT host
  refresh_from_remote.py          # Sync + full prep pipeline + Parquet rebuild
  prepare_fastpheno_data.py       # Build derived CSVs from III_db_final
  prepare_predawn_wp.py           # Predawn WP from PredawnWaterPotential/Process/
  prepare_soil_moisture.py        # Soil moisture CSV
  consolidate_uav_reflectance.py  # Merge UAV hyperspectral source CSVs
  consolidate_uav_spatial.py      # Merge LiDAR/GNSS spatial exports
  build_parquet.py                # Build consolidated Parquet from all CSV exports
  verify_fastpheno_data.py        # Check derived CSVs against source
FASTPHENO_DB_INTEGRATION.md       # Integration options and longer design notes
```

## API endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Health check, Parquet readiness |
| `GET /api/query/datasets` | Catalog of all sensor domains |
| `GET /api/query/{domain}/meta` | Sites, metrics, available dates, bounds |
| `GET /api/query/{domain}/daily?metric=…` | Chart-ready daily series |
| `GET /api/query/{domain}/rows` | Paginated filtered rows (`page`, `page_size`) |
| `GET /api/query/{domain}/rows?all=true` | All matching rows (dashboard tables) |
| `GET /api/data/fastpheno/{file}` | Raw CSV or markdown download |
| `GET /api/pigments/meta` | Pigment campaign sites and date bounds |
| `GET /api/pigments/campaigns` | Campaign list filtered by site and date range |
| `GET /api/pigments/download` | Zip download of matched campaign folders |

**Query domains:** `weather`, `fluorescence`, `reflectance`, `wp`, `soil_moisture`, `uav`, `lidar`, `gnss`

**Common query params:** `site=PIK|PIN` (or any weather site code), `from`, `to`, `all=true`

**Weather:** `source=eccc|eccc_hourly|daymet`, `resolution=daily|hourly` (hourly applies to ECCC only)

**Soil moisture:** `sensor_id` (e.g. `b11`), `interval=hourly|daily|weekly|monthly`

**UAV / LiDAR / GNSS:** `site`, `from`, `to`, optional `year` (meta/daily); rows span all years when `year` is omitted

Examples:

```bash
curl "http://localhost:8000/api/query/uav/meta?site=PIN"
curl "http://localhost:8000/api/query/uav/rows?site=PIN&from=2023-05-08&to=2023-05-08&all=true"
curl "http://localhost:8000/api/query/reflectance/meta?site=PIK"
curl "http://localhost:8000/api/query/weather/rows?source=daymet&site=PIN&from=2023-06-01&to=2023-08-31&all=true"
curl "http://localhost:8000/api/query/soil_moisture/meta?site=PIN"
curl "http://localhost:8000/api/query/lidar/daily?metric=height&site=PIN&from=2023-05-08&to=2023-05-08"
curl "http://localhost:8000/api/pigments/campaigns?site=PIN&from=2023-06-01&to=2023-08-31"
```

## Data files (`data/fastpheno/`)

| File pattern | Description |
|--------------|-------------|
| `{SITE}_daily_2010-2024.csv` | ECCC daily weather (9 sites) |
| `{SITE}_hourly_2022-2024.csv` | ECCC hourly weather |
| `{SITE}_daymet_daily_2010-2024.csv` | Daymet daily weather |
| `fluorescence_indices.csv` | Combined fluorescence campaign rows |
| `reflectance_indices.csv` | Combined reflectance index rows |
| `predawn_wp_2023.csv` | Predawn water potential (from `PredawnWaterPotential/Process/SPC_PreWP_2023.csv`) |
| `soil_moisture.csv` | Soil moisture and temperature time series |
| `uav_reflectance_2022.csv` / `uav_reflectance_2023.csv` | UAV tree-level hyperspectral index metrics |
| `uav_lidar_{pik\|pin}_{year}.csv` | UAV LiDAR structure exports |
| `uav_gnss_{pik\|pin}_{year}.csv` | UAV GNSS geolocation exports |
| `*.md` | Sensor metadata shown in the dashboard |

**Consolidated Parquet** (under `data/fastpheno/parquet/`): `fluorescence`, `reflectance`, `wp`, `soil_moisture`, `weather_eccc`, `weather_eccc_hourly`, `weather_daymet`, `uav`, `lidar`, `gnss`.

## Regenerating data

Derived CSVs are produced from a local copy of `III_db_final` (synced from the UofT host or a manual download). Configure `backend/.env` (see `backend/.env.example`), then:

```bash
pip install -r backend/requirements.txt

# One-time: set FASTPHENO_REMOTE_USER and FASTPHENO_REMOTE_PASSWORD in backend/.env
python3 scripts/sync_iii_db_final.py --list-remote   # confirm remote path

# Full refresh: sync → prep CSVs → rebuild Parquet
python3 scripts/refresh_from_remote.py

# Or step by step:
python3 scripts/sync_iii_db_final.py
python3 scripts/refresh_from_remote.py --skip-sync
```

`refresh_from_remote.py` runs, in order: weather/fluorescence/reflectance prep, predawn WP, UAV reflectance, LiDAR/GNSS, soil moisture, then `build_parquet.py`. Individual steps warn and continue if a source folder is missing on the server.

Local staging defaults to `~/III_db_final_local` (`FASTPHENO_III_DB_ROOT`). Sync downloads only folders listed in `FASTPHENO_SYNC_FOLDERS` from `/data/FastPheno/III_db_final` on `ffgg-fastpheno2.utm.utoronto.ca` (use `sync_iii_db_final.py --all` for the full tree). Repeat syncs update the same local folder incrementally; stale files are not deleted automatically.

| Remote folder | Dashboard entity |
|---------------|------------------|
| `Weather/` | Climate |
| `Fluorescence/` | Fluorescence |
| `Reflectance/` | Leaf reflectance |
| `UAV-Reflectance/` | Hyp_spec |
| `UAV-SpatialInformation/` | LiDAR + GNSS |
| `SoilMoisture/` | Soil moisture |
| `PredawnWaterPotential/` | Predawn WP |
| `Pigments/` | Pigments tab |

Legacy manual path (if you already have a local tree):

```bash
python3 scripts/prepare_fastpheno_data.py --weather-only   # ECCC + Daymet CSVs + weather Parquet only
python3 scripts/prepare_fastpheno_data.py                  # all CSVs; rebuild Parquet
python3 scripts/prepare_predawn_wp.py
python3 scripts/consolidate_uav_reflectance.py
python3 scripts/consolidate_uav_spatial.py
python3 scripts/prepare_soil_moisture.py
python3 scripts/verify_fastpheno_data.py --weather-only
python3 scripts/build_parquet.py                           # rebuild all Parquet (or --force)
```

## Architecture notes

- **Runtime:** the live API reads consolidated Parquet and markdown; it does not connect to the remote server or a database at request time.
- **Sync/prep:** runs locally with SSH credentials; writes CSVs into `data/fastpheno/` and Parquet into `data/fastpheno/parquet/`.
- **Parquet-only deploy:** charts work from Parquet alone; CSV download buttons and pigments zip downloads need the underlying files on disk.
- **Site discovery:** weather, LiDAR, and GNSS site lists are discovered from Parquet at runtime (`parquet_registry.py`), with CSV filename fallback during prep.

## Stack

- HTML / CSS (BAR-style shell)
- [PapaParse](https://www.papaparse.com/) — CSV export downloads
- [Tabulator](http://tabulator.info/) — paginated tables (`fitColumns` layout)
- [Chart.js](https://www.chartjs.org/) — charts
- FastAPI + DuckDB + Parquet — query API backend
- Paramiko — SFTP remote sync
- Python 3 — data preparation and verification

## Related docs

- [`FASTPHENO_DB_INTEGRATION.md`](./FASTPHENO_DB_INTEGRATION.md) — design options (static CSV vs SQLite vs API) and file inventory

## Status

Current build: unified query API over consolidated Parquet for all chart/table sensors, lazy loading, compare/range modes for ground campaigns and UAV hyperspectral, multi-site ECCC + Daymet + hourly weather, soil moisture aggregation, LiDAR/GNSS flight views, and pigment campaign zip downloads. Broader cross-domain joins and additional ERD entities (e.g. soil texture) remain future work.
