# ECCC Daily Weather Metadata

## Source

Daily weather records from Environment and Climate Change Canada (ECCC) stations, spatially interpolated to FastPheno field sites. Files are the original ECCC daily exports for **2010–2024** at Pickering (PIK) and Pintendre (PIN).

- `PIK_daily_2010-2024.csv`
- `PIN_daily_2010-2024.csv`

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
| vpd | Daily mean vapor pressure deficit (kPa). **Excluded from dashboard filters.** |
| temp_interp | Interpolated mean temperature (°C). |
| wind_spd_interp | Interpolated wind speed (km/h). |

## Notes

- Source path: `Weather/ECCC/{PIK,PIN}/Daily/*_daily_2010-2024.csv`
- Missing numeric values are encoded as `NA` in the source files.
- VPD is present in the source CSV but omitted from dashboard metric filters and table columns.
