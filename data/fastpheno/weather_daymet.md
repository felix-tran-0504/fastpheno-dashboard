# Daymet Daily Weather Metadata

## Source

Daily gridded meteorology from [Daymet v4](https://daymet.ornl.gov/) extracted at FastPheno field sites for **2010–2024** at Pickering (PIK) and Pintendre (PIN).

- `PIK_daymet_daily_2010-2024.csv`
- `PIN_daymet_daily_2010-2024.csv`

## Source layout (III_db_final)

```text
Weather/Daymet/{PIK,PIN}/daily/{site}_daily.csv
```

Additional Daymet site folders (CSI, FMM, GP, SCA, SM, TP39, TPD) are included alongside PIK and PIN in the dashboard build.

## CSV Columns

| Column Name | Description |
|---|---|
| site_id | Field site identifier (PIK = Pickering, PIN = Pintendre). |
| date | Calendar date (YYYY-MM-DD), derived from year + day-of-year. |
| year | Calendar year. |
| yday | Day of year (1–365/366). |
| tmax_c | Maximum daily temperature (°C). |
| tmin_c | Minimum daily temperature (°C). |
| prcp_mm_day | Total daily precipitation (mm). |
| vpd_kpa | Vapor pressure deficit (kPa). |
| par_w_m2 | Photosynthetically active radiation (W/m²). |
| par_mol_m2_day | PAR daily integral (mol/m²/day). |
| srad_w_m2 | Shortwave radiation (W/m²). |
| vp_Pa | Vapor pressure (Pa). |
| dayl_s | Day length (seconds). |
| temp | Mean daily temperature (°C), computed as (tmax_c + tmin_c) / 2. |

## Notes

- Source path: `Weather/Daymet/{PIK,PIN}/daily/{site}_daily.csv`
- Original `date` and `dayl_s` fields in the source files are Daymet internal values; dashboard dates use ISO format from year + yday.
