# FastPheno (III_db_final) Integration Plan

This document outlines concrete approaches for integrating the FastPheno plant physiology database at `/Users/felixtran/Downloads/III_db_final` into the BAR-style static HTML dashboard at [`fastpheno-dashboard.html`](./fastpheno-dashboard.html).

**Context:** III_db_final is a folder-based database (~215 files) spanning weather, reflectance, fluorescence, predawn water potential, and pressure–volume (TLP) curves across two field sites (Pickering/PIK, Pintendre/PIN) and multiple years (2010–2024 for weather; 2022–2024 for most phenotyping).

The primary app is [`fastpheno-dashboard.html`](./fastpheno-dashboard.html), backed by derived CSVs in [`data/fastpheno/`](./data/fastpheno/).

---

## Dataset domains and viz-readiness

| Domain | Source path(s) | Browser-friendly? | Best viz types |
|--------|----------------|-------------------|----------------|
| **Weather (ECCC daily)** | `Weather/ECCC/{PIK,PIN}/Daily/*_daily_2010-2024.csv` | Yes — ~5.5k rows/site | Time series (temp, precip, VPD) |
| **Weather (Daymet daily)** | `Weather/Daymet/{PIK,PIN}/daily/*_daily.csv` | Yes — ~5.5k rows/site | Time series (temp, PAR, VPD) |
| **Weather (hourly)** | `Weather/ECCC/{site}/Hourly/*_hourly_2022-2024.csv` | Not in dashboard yet | Future hourly views |
| **Reflectance** | `Reflectance/{site}/{year}/UNS_*.csv` | Partial — raw campaign files are wide (hundreds of spectral cols) but still usable if filtered to key metrics in the UI | Time series, genotype boxplots |
| **Fluorescence** | `Fluorescence/{site}/FLP_*.csv` | Yes — raw campaign rows are browser-friendly | Time series (QY_max, NPQ_Lss), scatter vs WP |
| **Predawn WP** | `PredawnWaterPotential/Process/SPC_PreWP_2023.csv` | Yes — ~530 rows | Boxplot by cluster/genotype, scatter over season |
| **TLP (P–V curves)** | `Tlp/**/pv_parameters_clean*.csv` | Moderate — multiple R-output files, needs consolidation | Parameter tables (Ψ<sub>tlp</sub>, RWC<sub>tlp</sub>), curve overlays |

---

## Approach 1: Static CSV + Tabulator (current pattern)

**Description:** Pre-process III_db_final into flat, browser-sized CSVs. Load them with PapaParse + Tabulator (and Chart.js for plots) in `fastpheno-dashboard.html`.

### Architecture

```
III_db_final/  ──(Python prep script)──►  data/fastpheno/*.csv
                                              │
fastpheno-dashboard.html  ◄───────────────────┘
  PapaParse → Tabulator tables
  Chart.js → time series / scatter
```

### What tables/charts fit

- **Tabulator tables:** predawn WP records, raw fluorescence campaign rows, raw reflectance campaign metadata, TLP parameter summaries
- **Chart.js line charts:** daily weather, NDVI/GNDVI seasonality, QY_max over time (client-side date aggregation from raw campaign rows)
- **Chart.js scatter/box:** predawn Ψ by cluster; fluorescence vs water potential

### Data prep needed

- One-time (or periodic) Python/R script to:
  - Subsample weather to recent years or monthly aggregates
  - Combine raw reflectance campaign CSVs into one browser-loadable export
  - Combine raw fluorescence campaign CSVs into one browser-loadable export
  - Consolidate scattered TLP outputs into one `tlp_summary.csv`
- Target: keep each CSV under ~2 MB for snappy loads

### Effort estimate

**Low–medium (2–5 days)** for a focused dashboard covering 3–4 domains. Scales linearly with number of domains/years added.

### Pros

- Matches BAR shell conventions (`efp.css`, Tabulator, PapaParse)
- No server dependency beyond `python3 -m http.server`
- Easy to version-control derived CSVs alongside HTML
- Raw campaign rows stay faithful to the source database

### Cons

- Manual or scripted refresh when source data changes
- Cross-domain joins (e.g. WP + weather on same date) require pre-computation
- Full reflectance spectra make the combined browser CSV materially larger

### Recommended for

**Yes — recommended as the primary path.** The folder-based CSV structure maps naturally to derived flat files. The dashboard is already built for this pattern.

---

## Approach 2: SQLite WASM in browser (sql.js)

**Description:** Import all III_db_final CSVs into a single SQLite database file. Load `sql.js` in the browser and run SQL queries client-side for filtering, joins, and aggregates.

### Architecture

```
III_db_final/**/*.csv  ──(import script)──►  fastpheno.db (SQLite)
                                                  │
Browser: sql.js (WASM) ◄── fetch fastpheno.db ────┘
         SQL queries → JSON rows → Tabulator / Chart.js
```

### Example queries

```sql
SELECT date, AVG(NDVI) AS ndvi
FROM reflectance WHERE site='PIN' AND year=2023
GROUP BY date ORDER BY date;

SELECT wp.Cluster, AVG(wp.wp_pd) AS mean_wp
FROM predawn_wp wp
JOIN weather w ON wp.date = w.date AND wp.site = w.site_id
WHERE w.temp > 20
GROUP BY wp.Cluster;
```

### Data prep needed

- Python script using `sqlite3` or `pandas.to_sql()` to:
  - Create tables: `weather`, `reflectance_indices`, `fluorescence`, `predawn_wp`, `tlp`
  - Import only needed columns (not full spectra)
  - Add indexes on `site`, `date`, `primary_key`
- Resulting `.db` file: estimate 5–20 MB (acceptable for WASM load)

### Effort estimate

**Medium (5–8 days)** including import pipeline, sql.js integration, and query UI.

### Pros

- Unified query layer — cross-domain joins without pre-computing every combination
- Flexible ad-hoc filtering (site × year × genotype × date range)
- Single artifact (`fastpheno.db`) replaces many CSVs

### Cons

- Initial WASM download (~1 MB for sql.js) adds latency
- Loading a multi-MB `.db` over HTTP can be slow on first visit
- More complex frontend code than flat CSV fetch
- Debugging SQL in browser is harder than inspecting a CSV

### Recommended for

**Secondary option** if the team needs interactive cross-domain queries (e.g. "show NDVI for trees with wp_pd < 0.3 MPa during heat waves") without building a backend.

---

## Approach 3: Lightweight backend API (Python Flask/FastAPI or Node)

**Description:** A small local or hosted API reads III_db_final directly from disk and returns JSON for the frontend. The HTML dashboard stays mostly unchanged; it fetches from `/api/...` endpoints instead of static CSVs.

### Architecture

```
III_db_final/  ◄── reads ──  FastAPI/Flask app
                                  │
                           /api/weather?site=PIK&year=2023
                           /api/reflectance/indices?site=PIN
                           /api/fluorescence?year=2023
                           /api/water-potential
                           /api/tlp/summary
                                  │
Browser (Tabulator + Chart.js) ◄── JSON responses
```

### Example endpoints

| Endpoint | Returns |
|----------|---------|
| `GET /api/weather?site=PIK&from=2023-01-01&to=2023-12-31` | Daily weather rows |
| `GET /api/reflectance/indices?site=PIN&year=2023` | NDVI, PRI, GNDVI time series |
| `GET /api/fluorescence?site=PIN&year=2023` | QY_max, NPQ_Lss per measurement |
| `GET /api/water-potential?site=pik&cluster=G` | Predawn WP records |
| `GET /api/tlp/summary?site=PIK` | Consolidated PV parameters |

### Data prep needed

- Minimal — API reads source CSVs on demand
- Optional: in-memory or file-based cache for large weather files
- Column projection in API layer (never send 600 wavelength columns)

### Effort estimate

**Medium–high (1–2 weeks)** for API + frontend wiring + deployment docs.

### Pros

- Always reads latest data from III_db_final (no re-export step)
- Server-side joins, aggregation, and column filtering
- Can serve full dataset without bloating browser downloads
- Natural path to authentication, rate limiting, or multi-user access later

### Cons

- Requires running a server process (not pure static hosting)
- Deployment complexity vs. opening an HTML file
- CORS configuration if API and frontend are on different origins
- Overkill for a single-researcher local workflow

### Recommended for

**Future path** if FastPheno visualization becomes a shared team tool or needs live data refresh without manual CSV regeneration. Not needed for the current local preview use case.

---

## Comparison summary

| Approach | Effort | Server needed | Cross-domain joins | Live data refresh | Best fit |
|----------|--------|---------------|-------------------|-------------------|----------|
| 1. Static CSV + Tabulator | 2–5 days | Static HTTP only | Pre-computed | Manual re-export | **Primary** |
| 2. SQLite WASM | 5–8 days | Static HTTP only | SQL joins in browser | Re-build .db file | Interactive exploration |
| 3. Backend API | 1–2 weeks | Python/Node process | Server-side | Automatic | Team/shared deployment |

---

## Recommended path for this situation

Given a **folder-based CSV/Excel database with ~215 files**, two sites, and a researcher-local workflow:

### Phase 1 — Done

1. **Derived CSVs** in `data/fastpheno/` (weather 2010–24, reflectance indices, fluorescence, predawn WP)
2. **Standalone dashboard** at `fastpheno-dashboard.html` with site/year filters, charts, stats panel, and sensor tables

### Phase 2 — Short term (1 week)

1. Expand derived CSVs to cover PIK reflectance/fluorescence and 2022/2024 phenotyping years
2. Write a `scripts/build_fastpheno_csvs.py` to regenerate derived data from III_db_final

### Phase 3 — If needed later

- Move to **sql.js** (Approach 2) if cross-domain queries become a bottleneck
- Move to **FastAPI** (Approach 3) only if multiple users need concurrent access to live data

### What not to do

- Do not load full reflectance spectra (600+ columns) in the browser
- Do not embed all 215 raw files — always project to viz-ready subsets

---

## File inventory

| File | Purpose |
|------|---------|
| [`fastpheno-dashboard.html`](./fastpheno-dashboard.html) | Primary dashboard (Chart.js + Tabulator) |
| [`data/fastpheno/PIK_daily_2010-2024.csv`](./data/fastpheno/PIK_daily_2010-2024.csv) | PIK ECCC daily weather (2010–2024) |
| [`data/fastpheno/PIN_daily_2010-2024.csv`](./data/fastpheno/PIN_daily_2010-2024.csv) | PIN ECCC daily weather (2010–2024) |
| [`data/fastpheno/PIK_daymet_daily_2010-2024.csv`](./data/fastpheno/PIK_daymet_daily_2010-2024.csv) | PIK Daymet daily weather (2010–2024) |
| [`data/fastpheno/PIN_daymet_daily_2010-2024.csv`](./data/fastpheno/PIN_daymet_daily_2010-2024.csv) | PIN Daymet daily weather (2010–2024) |
| [`data/fastpheno/reflectance_indices.csv`](./data/fastpheno/reflectance_indices.csv) | Daily NDVI/PRI/GNDVI means (all sites/years) |
| [`data/fastpheno/fluorescence_indices.csv`](./data/fastpheno/fluorescence_indices.csv) | Daily QY_max/NPQ_Lss means (all sites/years) |
| [`data/fastpheno/predawn_wp_2023.csv`](./data/fastpheno/predawn_wp_2023.csv) | Predawn water potential records |

## How to run

```bash
cd "/Users/felixtran/Desktop/PCA_C-SPIRIT Single Cell Papers_files"
python3 -m http.server 8080
```

Open: [http://localhost:8080/fastpheno-dashboard.html](http://localhost:8080/fastpheno-dashboard.html)
