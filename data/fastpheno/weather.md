# ECCC Daily Weather Metadata

## Source

Daily weather records from Environment and Climate Change Canada (ECCC) stations, spatially interpolated to FastPheno field sites. Files are the original ECCC daily exports for **2010–2024** at Pickering (PIK) and Pintendre (PIN).

- `PIK_daily_2010-2024.csv`
- `PIN_daily_2010-2024.csv`

## Source layout (III_db_final)

The upstream Weather folder is organized by product and site:

```text
Weather/
  ECCC/
    PIK/Daily/PIK_daily_2010-2024.csv
    PIK/Hourly/PIK_hourly_2022-2024.csv
    PIN/Daily/…  PIN/Hourly/…
    … (other station codes: CSI, FMM, GP, SCA, SM, TP39, TPD)
  Daymet/
    PIK/daily/PIK_daily.csv
    PIN/daily/PIN_daily.csv
    … (same station codes as ECCC)
```

The dashboard uses **all ECCC site exports** under `Weather/ECCC/` (currently CSI, FMM, GP, PIK, PIN, SCA, SM, TP39, TPD) plus matching Daymet daily files.

## CSV Columns

| Column Name | Description |
|---|---|
| site_id | Field site identifier (PIK = Pickering, PIN = Pintendre). |
| date | Calendar date (YYYY-MM-DD). |
| lat | Interpolated latitude (°). |
| lon | Interpolated longitude (°). |
| elev | Elevation (m). |
| cool_deg_days | Cooling degree days. |
| wind_dir | Wind direction (°). |
| heat_deg_days | Heating degree days. |
| max_temp | Maximum daily air temperature (°C). |
| temp | Mean daily air temperature (°C). |
| min_temp | Minimum daily air temperature (°C). |
| snow_grnd | Snow on ground (cm). |
| wind_spd | Wind speed (km/h). |
| precip_amt | Total daily precipitation (mm). |
| total_rain | Total rain (mm). |
| total_snow | Total snow (cm). |
| n_stations | Number of contributing ECCC stations. |
| mean_distance | Mean distance to contributing stations (km). |
| site_lat | Field site latitude (°). |
| site_lon | Field site longitude (°). |
| vpd | Daily mean vapor pressure deficit (kPa). |
| temp_interp | Interpolated mean temperature (°C). |
| wind_spd_interp | Interpolated wind speed (km/h). |

## Notes

- Source path: `Weather/ECCC/{PIK,PIN}/Daily/*_daily_2010-2024.csv`
- Missing numeric values are encoded as `NA` in the source files.
