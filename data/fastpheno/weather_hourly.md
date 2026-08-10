# ECCC Hourly Weather Metadata

## Source

Hourly weather records from Environment and Climate Change Canada (ECCC) stations, spatially interpolated to FastPheno field sites. Files are the original ECCC hourly exports for **2022–2024** at Pickering (PIK) and Pintendre (PIN).

- `PIK_hourly_2022-2024.csv`
- `PIN_hourly_2022-2024.csv`

## Source layout (III_db_final)

```text
Weather/
  ECCC/
    PIK/Hourly/PIK_hourly_2022-2024.csv
    PIN/Hourly/PIN_hourly_2022-2024.csv
```

## CSV Columns

| Column Name | Description |
|---|---|
| site_id | Field site identifier (PIK = Pickering, PIN = Pintendre). |
| date | Calendar date (YYYY-MM-DD). |
| time | Observation timestamp (UTC, ISO-8601). |
| lat | Interpolated latitude (°). |
| lon | Interpolated longitude (°). |
| elev | Elevation (m). |
| hmdx | Humidex. |
| precip_amt | Hourly precipitation (mm). |
| pressure | Station pressure (kPa). |
| rel_hum | Relative humidity (%). |
| temp | Air temperature (°C). |
| temp_dew | Dew point temperature (°C). |
| visib | Visibility (km). |
| wind_chill | Wind chill (°C). |
| wind_dir | Wind direction (°). |
| wind_spd | Wind speed (km/h). |
| n_stations | Number of contributing ECCC stations. |
| mean_distance | Mean distance to contributing stations (km). |
| site_lat | Field site latitude (°). |
| site_lon | Field site longitude (°). |
| vpd | Vapor pressure deficit (kPa). |
| temp_interp | Interpolated air temperature (°C). |
| temp_dew_interp | Interpolated dew point (°C). |
| rel_hum_interp | Interpolated relative humidity (%). |
| wind_spd_interp | Interpolated wind speed (km/h). |
| pressure_interp | Interpolated pressure (kPa). |
| hmdx_interp | Interpolated humidex. |
| wind_chill_interp | Interpolated wind chill (°C). |

## Notes

- Source path: `Weather/ECCC/{PIK,PIN}/Hourly/*_hourly_2022-2024.csv`
- Hourly data is available for ECCC only; Daymet remains daily.
- Missing numeric values are encoded as `NA` in the source files.
