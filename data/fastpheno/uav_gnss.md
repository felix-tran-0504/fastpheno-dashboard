# UAV Tree Geolocation (GNSS) Metadata

## Metadata Description

| Column Name | Description |
|---|---|
| site | Field site identifier (PIN = Pintendre, PIK = Pickering). |
| year | Calendar year of the UAV flight campaign. |
| flight_date | Date of the UAV overpass (YYYY-MM-DD). |
| flight_id | Flight folder or pass identifier (may include a same-day suffix for repeat passes). |
| source_file | Original source filename (`*treeTop.csv`) from the UAV spatial information folder. |
| site_treeid | Tree identifier within the site (e.g. PIN_1001); links to other tree-level tables via primary_key. |
| treeTop_x | Easting coordinate of the segmented tree top (projected CRS used in source exports). |
| treeTop_y | Northing coordinate of the segmented tree top (projected CRS used in source exports). |
| treeTop_x_std | Standard deviation of tree-top X position (positional uncertainty). |
| treeTop_y_std | Standard deviation of tree-top Y position (positional uncertainty). |

## Notes

- Exports are consolidated by site and year (`uav_gnss_{pik|pin}_{year}.csv`).
- Coordinates refer to the tree-top point matched to each segmented crown for that flight.
