# UAV LiDAR Structure Metadata

## Metadata Description

| Column Name | Description |
|---|---|
| site | Field site identifier (PIN = Pintendre, PIK = Pickering). |
| year | Calendar year of the UAV flight campaign. |
| flight_date | Date of the UAV overpass (YYYY-MM-DD). |
| flight_id | Flight folder or pass identifier (may include a same-day suffix for repeat passes). |
| source_file | Original source filename (`*treeSpatialMetrics.csv`) from the UAV spatial information folder. |
| site_treeid | Tree identifier within the site (e.g. PIN_1001); links to other tree-level tables via primary_key. |
| tree_height_corrected_m | LiDAR-derived tree height after correction (metres). |
| canopy_area_m2 | Projected canopy area for the segmented tree crown (m²). |
| tree_altitude_m | Ground or tree-base altitude above sea level (metres). |

## Notes

- Exports are consolidated by site and year (`uav_lidar_{pik|pin}_{year}.csv`).
- Rows are keyed by site, flight date, and tree ID; use flight_id when multiple passes occur on the same day.
