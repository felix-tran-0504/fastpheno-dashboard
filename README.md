# FastPheno Plant Physiology Dashboard

An interactive web interface for exploring FastPheno field measurements from the **III_db_final** research collection. Open it in a browser to view charts, tables, and metadata for trees and sites at **Pickering (PIK)** and **Pintendre (PIN)**, plus additional weather station locations.

> **For developers:** setup, API, data pipeline, and server maintenance are documented in [`DEVELOPER.md`](./DEVELOPER.md).

---

## What you can explore

The home page organizes data into three areas, aligned with the FastPheno database schema:

### Environmental

| View | What it shows |
|------|----------------|
| **Climate** | Daily and hourly weather from ECCC, and daily Daymet records (2010–2024). View a single day in detail or plot a date range. |
| **Soil moisture** | Soil water content and temperature from field sensors over time. |

### Ground campaigns

| View | What it shows |
|------|----------------|
| **Fluorescence** | Chlorophyll fluorescence metrics (e.g. QY<sub>max</sub>, NPQ) measured on individual trees during field campaigns. |
| **Leaf reflectance** | Vegetation indices from leaf-level spectrometer measurements (e.g. NDVI, PRI, GNDVI). |
| **Predawn water potential (WP)** | Predawn leaf water potential (Ψ<sub>pd</sub>) by cluster and genotype. |
| **Pigments** | Pigment sampling campaigns — browse by site and date, then download matched campaign folders as a zip file. |

### UAV flights

| View | What it shows |
|------|----------------|
| **Hyp_spec** | Tree-level hyperspectral reflectance indices from UAV flights (2022–2023). |
| **LiDAR** | Tree height, location, and structural metrics from UAV LiDAR. |
| **GNSS** | Tree geolocation from UAV GNSS surveys. |

Each view includes a **metadata panel** with field descriptions and data notes where available.

---

## How to use the dashboard

1. **Open the site** — use the URL provided by your lab or UofT host (or ask whoever maintains the deployment).
2. **Choose a domain** — Environmental, Ground, or UAV on the home page.
3. **Pick a data type** — e.g. Fluorescence, Climate, Hyp_spec.
4. **Set filters** — site (PIK / PIN where applicable), dates, and metrics.
5. **Read the chart and table** — results load when you open a view; you do not need to download files first.
6. **Export if needed** — many views offer CSV download for the filtered table.

### Two ways to compare dates

- **Compare dates** — overlay up to four chosen measurement dates on one chart (common for fluorescence, reflectance, and UAV hyperspectral).
- **Date range** — show all measurements between a start and end date.

Climate uses **single day** (detailed snapshot) or **date range** (time series line chart).

---

## Sites and coverage

- **Field sites:** PIK (Pickering) and PIN (Pintendre) for most phenotyping and UAV data.
- **Weather:** nine ECCC station codes (including PIK, PIN, CSI, FMM, GP, SCA, SM, TP39, TPD).
- **Years:** weather spans 2010–2024; most campaign and UAV data focus on 2022–2024 (varies by sensor).

If a view shows no data for your selection, that combination may not exist in the database yet, or the deployment may not have been refreshed since new data were added.

---

## Getting help

- **Using the interface** — contact your lab lead or the person who shared the dashboard URL.
- **Missing or outdated data** — ask the maintainer to refresh from the FastPheno server (see [`DEVELOPER.md`](./DEVELOPER.md)).
- **Technical / integration questions** — see [`DEVELOPER.md`](./DEVELOPER.md) and [`FASTPHENO_DB_INTEGRATION.md`](./FASTPHENO_DB_INTEGRATION.md).

---

## Status

The dashboard currently supports interactive exploration of climate, soil moisture, ground campaigns (fluorescence, reflectance, predawn WP, pigments), and UAV products (hyperspectral, LiDAR, GNSS). Some ERD entities (e.g. soil texture) are listed on the home page but not yet wired to data.
