# Soil Moisture Metadata

## Metadata Description

| Column Name | Description |
|---|---|
| site | Field site identifier (PIN = Pintendre, PIK = Pickering). |
| sensor_id | Soil sensor identifier (e.g. b11, b35). |
| date | Measurement date (YYYY-MM-DD). |
| time | Measurement time (HH:MM:SS). |
| datetime | Combined date and time stamp. |
| vwc | Volumetric water content (m³/m³). |
| st | Soil temperature (°C). |
| elevation_m | Sensor elevation above sea level (metres). |
| week_label | Year_week code from the source export (e.g. 23_19). |

## Notes

- Current build includes **Pickering (PIK)** data from May 2023 through November 2024 (~30-minute sampling).
- Pintendre (PIN) will appear when files are added under `SoilMoisture/Pintendre/` in the source database.
- Use the **Sensor** filter to choose a probe; the chart aggregates that sensor at the selected **Interval** (hourly, daily, weekly, or monthly means).
