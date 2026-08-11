# FastPheno Dashboard — Developer Guide

Technical documentation for running, deploying, and maintaining the FastPheno dashboard. For a lab-facing overview of what the interface does, see [`README.md`](./README.md).

---

## Architecture

```
III_db_final (UofT host)  ──SFTP sync──►  local staging (III_db_final_local)
                                              │
                                         prep scripts
                                              ▼
                                    data/fastpheno/*.csv
                                              │
                                         build_parquet
                                              ▼
                                    data/fastpheno/parquet/
                                              │
         fastpheno-dashboard.html  ◄───  FastAPI + DuckDB query API
```

- **Runtime:** the live API reads consolidated Parquet and markdown. It does not connect to the remote server or a database at request time.
- **Sync/prep:** runs on the host with SSH credentials; writes CSVs into `data/fastpheno/` and Parquet into `data/fastpheno/parquet/`.
- **Parquet-only deploy:** charts work from Parquet alone; CSV download buttons and pigment zip downloads need the underlying files on disk.
- **Site discovery:** weather, LiDAR, and GNSS site lists are discovered from Parquet at runtime (`parquet_registry.py`), with CSV filename fallback during prep.

The dashboard is a single HTML file backed by a **FastAPI query API**. Sensor data is **lazy-loaded** on demand. CSV exports are the source of truth; the API queries **consolidated Parquet** files built from those CSVs.

---

## Stack

| Layer | Technology |
|-------|------------|
| UI | HTML / CSS (BAR-style shell), [Chart.js](https://www.chartjs.org/), [Tabulator](http://tabulator.info/), [PapaParse](https://www.papaparse.com/) |
| API | [FastAPI](https://fastapi.tiangolo.com/) + [uvicorn](https://www.uvicorn.org/) |
| Query engine | [DuckDB](https://duckdb.org/) over Parquet |
| Data prep | Python |
| Remote sync | [Paramiko](https://www.paramiko.org/) SFTP |

---

## Quick start (local)

```bash
cd "/path/to/fastpheno-dashboard"
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
python3 scripts/build_parquet.py    # first time, or after CSV updates
python3 -m uvicorn backend.app:app --reload --port 8000
```

Open [http://localhost:8000/fastpheno-dashboard.html](http://localhost:8000/fastpheno-dashboard.html)

Parquet files under `data/fastpheno/parquet/` are consolidated **one file per sensor** (weather uses three: `weather_eccc`, `weather_eccc_hourly`, `weather_daymet`). They are **auto-rebuilt on API startup** if missing or stale.

### Configuration

Copy `backend/.env.example` → `backend/.env` (gitignored):

| Variable | Purpose |
|----------|---------|
| `FASTPHENO_III_DB_ROOT` | Local mirror of selected remote folders (default `~/III_db_final_local`) |
| `FASTPHENO_PIGMENTS_ROOT` | Pigments campaign files (default `~/III_db_final_local/Pigments`) |
| `FASTPHENO_REMOTE_HOST` | `ffgg-fastpheno2.utm.utoronto.ca` |
| `FASTPHENO_REMOTE_USER` / `FASTPHENO_REMOTE_PASSWORD` | SSH/SFTP credentials |
| `FASTPHENO_REMOTE_III_DB_PATH` | Remote data root (`/data/FastPheno/III_db_final`) |
| `FASTPHENO_SYNC_FOLDERS` | Comma-separated top-level folders to download |
| `FASTPHENO_REMOTE_SSH_KEY` | Optional SSH key instead of password |
| `FASTPHENO_DATA_DIR` | Optional override for `data/fastpheno` path |

---

## Project layout

```
fastpheno-dashboard.html          # Main dashboard
backend/
  app.py                            # FastAPI app, static files, Parquet warmup
  config.py                         # Paths, row limits, pigments root
  routers/
    data_files.py                   # CSV/MD file serving
    query.py                        # JSON query endpoints
    pigments.py                     # Pigment campaign listing and zip download
  services/
    datasets.py                     # Dataset registry
    parquet_registry.py             # Site/coverage discovery from Parquet
    parquet_store.py                # CSV → Parquet build / ensure
    query_engine.py                 # DuckDB queries
    pigments.py                     # Pigments filesystem access
data/fastpheno/                   # CSV exports + metadata markdown
data/fastpheno/parquet/           # Query layer (generated; gitignored)
scripts/
  fastpheno_env.py                # Load backend/.env; resolve paths
  sync_iii_db_final.py            # Selective SFTP sync
  refresh_from_remote.py          # Sync + prep + Parquet rebuild
  refresh_scheduled.sh            # Cron wrapper with logging + API restart
  install_weekly_cron.sh          # Install/remove weekly cron job
  prepare_fastpheno_data.py       # Build derived CSVs
  prepare_predawn_wp.py
  prepare_soil_moisture.py
  consolidate_uav_reflectance.py
  consolidate_uav_spatial.py
  build_parquet.py
  verify_fastpheno_data.py
logs/                             # refresh_scheduled.sh logs (gitignored)
```

---

## Dashboard ↔ API mapping

| Entity | API domain | Site filter | Date modes | Chart |
|--------|------------|-------------|------------|-------|
| Climate | `weather` | All ECCC sites | Single day / Date range | Line (range) |
| Soil moisture | `soil_moisture` | PIK / PIN | Date range | Line (aggregated) |
| Fluorescence | `fluorescence` | PIK / PIN | Compare / Range | Scatter-box |
| Leaf reflectance | `reflectance` | PIK / PIN | Compare / Range | Scatter-box |
| Predawn WP | `wp` | — | Compare / Range | Scatter-box |
| Pigments | `/api/pigments/*` | PIK / PIN | Date range | Campaign list + zip |
| Hyp_spec | `uav` | PIK / PIN | Compare / Range | Scatter-box / line |
| LiDAR | `lidar` | PIK / PIN | Flight date | Line (daily means) |
| GNSS | `gnss` | PIK / PIN | Flight date | Line (daily means) |

Data loads when a sensor tab is opened (`ensureSensorReady`), not on initial page load.

---

## API endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Health check, Parquet readiness |
| `GET /api/query/datasets` | Catalog of sensor domains |
| `GET /api/query/{domain}/meta` | Sites, metrics, dates, bounds |
| `GET /api/query/{domain}/daily?metric=…` | Chart-ready daily series |
| `GET /api/query/{domain}/rows` | Paginated rows (`page`, `page_size`) |
| `GET /api/query/{domain}/rows?all=true` | All matching rows (tables); used for client-side CSV export |
| `GET /api/query/{domain}/export/meta` | Export row count and recommended method (`client` or `server`) |
| `GET /api/query/{domain}/export.csv` | Server-side Parquet → CSV download |
| `GET /api/data/fastpheno/{file}` | Raw CSV or markdown download |
| `GET /api/pigments/meta` | Pigment sites and date bounds |
| `GET /api/pigments/campaigns` | Campaign list by site/date |
| `GET /api/pigments/download` | Zip of matched campaign folders |

**Query domains:** `weather`, `fluorescence`, `reflectance`, `wp`, `soil_moisture`, `uav`, `lidar`, `gnss`

**Common params:** `site`, `from`, `to`, `all=true`

**Weather:** `source=eccc|eccc_hourly|daymet`, `resolution=daily|hourly`

**Soil moisture:** `sensor_id`, `interval=hourly|daily|weekly|monthly`

**UAV / LiDAR / GNSS:** `site`, `from`, `to`, optional `year`

**CSV exports:** small datasets (fluorescence, reflectance, WP, weather, UAV when ≤50k rows) use client-side `/rows?all=true` → CSV in the browser. Large datasets (`soil_moisture`, `lidar`, `gnss`, and any export over 50k rows) stream from `/export.csv`. Run `python3 scripts/test_exports.py` to verify both paths.

Examples:

```bash
curl "http://localhost:8000/api/health"
curl "http://localhost:8000/api/query/uav/meta?site=PIN"
curl "http://localhost:8000/api/query/weather/rows?source=daymet&site=PIN&from=2023-06-01&to=2023-08-31&all=true"
curl "http://localhost:8000/api/pigments/campaigns?site=PIN&from=2023-06-01&to=2023-08-31"
```

---

## Data files

Runtime queries and CSV exports read **consolidated Parquet** under `data/fastpheno/parquet/`. Sensor metadata markdown (`*.md`) is also served to the dashboard.

Derived CSV exports under `data/fastpheno/*.csv` are **prep-only artifacts** (built by refresh scripts, then folded into Parquet). They are gitignored and not required on the deployed server.

| Parquet file | Description |
|--------------|-------------|
| `fluorescence.parquet` | Combined fluorescence campaign rows |
| `reflectance.parquet` | Combined reflectance index rows |
| `wp.parquet` | Predawn water potential |
| `soil_moisture.parquet` | Soil moisture / temperature |
| `weather_eccc.parquet` | ECCC daily weather (all sites) |
| `weather_eccc_hourly.parquet` | ECCC hourly weather |
| `weather_daymet.parquet` | Daymet daily weather |
| `uav.parquet` | UAV hyperspectral indices |
| `lidar.parquet` | LiDAR structure exports |
| `gnss.parquet` | GNSS geolocation exports |

Prep scripts still write intermediate CSVs locally when you run `refresh_from_remote.py`; `build_parquet.py` unions them into the files above.

---

## Updating data

The live dashboard **only reads local files** — it never connects to ffgg at request time. Refreshing data means rebuilding `data/fastpheno/` (CSVs + Parquet) somewhere, then making sure the **host that serves the site** has those files.

Choose one of the approaches below.

### Option A — Manual refresh from your laptop (no ffgg creds on UofT server)

Best when UofT hosts the site but ffgg SSH stays on a trusted lab machine.

```
ffgg-fastpheno2  ──SFTP──►  your / lab laptop
                              refresh_from_remote.py
                              data/fastpheno/
                              rsync/scp
                                  │
                                  ▼
                         UofT web server  ──►  users
```

**On the laptop** (needs `backend/.env` with ffgg credentials):

```bash
cd /path/to/fastpheno-dashboard
source .venv/bin/activate   # if using a venv
python3 scripts/refresh_from_remote.py
```

Spot-check locally if you want: `python3 -m uvicorn backend.app:app --port 8000`

**Copy data to the UofT server** (replace user, host, and path):

```bash
rsync -avz data/fastpheno/parquet/ USER@uoft-server:/path/to/fastpheno-dashboard/data/fastpheno/parquet/
rsync -avz data/fastpheno/*.md USER@uoft-server:/path/to/fastpheno-dashboard/data/fastpheno/
```

If the **Pigments** tab must serve zip downloads, also sync the pigments tree to wherever `FASTPHENO_PIGMENTS_ROOT` points on the server (often `~/III_db_final_local/Pigments`):

```bash
rsync -avz ~/III_db_final_local/Pigments/ USER@uoft-server:/path/to/Pigments/
```

**On the UofT server** — restart the API so DuckDB picks up new Parquet:

```bash
sudo systemctl restart fastpheno   # or ask UofT IT
curl https://your-url.utoronto.ca/api/health
```

The UofT server does **not** need ffgg passwords for this workflow.

---

### Option B — Refresh on the UofT server (manual, one-off)

Use when the web server can SSH to ffgg and a maintainer runs refresh by hand when needed.

**On the UofT server:**

1. Copy `backend/.env.example` → `backend/.env` and fill in ffgg SFTP settings (keep file permissions tight, e.g. `chmod 600 backend/.env`).
2. Run:

```bash
cd /path/to/fastpheno-dashboard
source .venv/bin/activate
python3 scripts/refresh_from_remote.py
sudo systemctl restart fastpheno
```

Confirm remote path first if unsure:

```bash
python3 scripts/sync_iii_db_final.py --list-remote
```

---

### Option C — Automated weekly refresh on the UofT server

Same as Option B, but on a schedule. Requires ffgg credentials in `backend/.env` on that host.

```bash
chmod +x scripts/refresh_scheduled.sh scripts/install_weekly_cron.sh

# One-off test (writes logs/refresh.log)
./scripts/refresh_scheduled.sh

# Install cron: every Sunday at 02:00 local time
./scripts/install_weekly_cron.sh

# Custom schedule (Monday 03:00)
CRON_SCHEDULE='0 3 * * 1' ./scripts/install_weekly_cron.sh

# Remove cron job
./scripts/install_weekly_cron.sh --uninstall
```

The wrapper logs to `logs/refresh.log`, skips overlapping runs, and restarts systemd unit `fastpheno` when active. Override with `FASTPHENO_SERVICE_NAME` or set `FASTPHENO_SKIP_RESTART=1`.

| Approach | ffgg creds on UofT server? | Who runs refresh? |
|----------|----------------------------|-------------------|
| A — Laptop + rsync | No | You / lab laptop |
| B — Server manual | Yes | Maintainer on server |
| C — Server cron | Yes | Cron on server |

---

### What `refresh_from_remote.py` does

```bash
pip install -r backend/requirements.txt

# Full refresh: sync → prep CSVs → rebuild Parquet
python3 scripts/refresh_from_remote.py

# Or step by step:
python3 scripts/sync_iii_db_final.py
python3 scripts/refresh_from_remote.py --skip-sync
```

Pipeline order: weather/fluorescence/reflectance prep → predawn WP → UAV reflectance → LiDAR/GNSS → soil moisture → `build_parquet.py`. Steps warn and continue if a source folder is missing.

Local staging defaults to `~/III_db_final_local`. Sync downloads only folders in `FASTPHENO_SYNC_FOLDERS` from `/data/FastPheno/III_db_final` on `ffgg-fastpheno2.utm.utoronto.ca`. Repeat syncs are incremental; stale files are not deleted automatically.

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

### Legacy manual prep (step-by-step scripts)

If you already have a local `III_db_final` tree and want to run prep scripts individually:

```bash
python3 scripts/prepare_fastpheno_data.py --weather-only
python3 scripts/prepare_fastpheno_data.py
python3 scripts/prepare_predawn_wp.py
python3 scripts/consolidate_uav_reflectance.py
python3 scripts/consolidate_uav_spatial.py
python3 scripts/prepare_soil_moisture.py
python3 scripts/verify_fastpheno_data.py
python3 scripts/build_parquet.py --force
```

---

## Deployment (UofT server)

Typical production layout:

```
Browser → https://your-url.utoronto.ca  (UofT nginx + TLS)
              ↓
         uvicorn backend.app:app  (127.0.0.1:8000, systemd)
              ↓
         data/fastpheno/ + parquet/
```

**Checklist:**

1. Clone repo, create venv, `pip install -r backend/requirements.txt`
2. Copy `data/fastpheno/parquet/` and `data/fastpheno/*.md` to the server (first deploy), or run refresh on the server — see [Updating data](#updating-data)
3. Set `FASTPHENO_PIGMENTS_ROOT` on the server if the Pigments tab is used
4. Run uvicorn via systemd; ask UofT IT to reverse-proxy the URL to port 8000
5. Verify `GET /api/health` returns `"parquet_ready": true`
6. Optional: Option C cron for automated refresh, or use Option A from a lab laptop when data change

Keep the dashboard and API on the **same origin** so the browser can reach `/api/*` without CORS changes. UofT IT does **not** need ffgg credentials unless you choose Option B or C on that host.

---

## Related docs

- [`README.md`](./README.md) — lab-facing overview
- [`FASTPHENO_DB_INTEGRATION.md`](./FASTPHENO_DB_INTEGRATION.md) — design options and file inventory

---

## Status

Unified query API over consolidated Parquet for all chart/table sensors, lazy loading, compare/range modes, multi-site ECCC + Daymet + hourly weather, soil moisture aggregation, LiDAR/GNSS flight views, and pigment zip downloads. Cross-domain joins and additional ERD entities (e.g. soil texture) remain future work.
