# UAV Hyperspectral Reflectance Metadata

## Metadata Description

| Column Name | Description |
|---|---|
| site | Field site identifier (PIN = Pintendre, PIK = Pickering). |
| year | Calendar year of the UAV flight campaign. |
| flight_date | Date of the UAV overpass (YYYY-MM-DD). |
| dataset | Dataset or product label for the reflectance export. |
| source_file | Original source filename from the UAV spatial information folder. |
| site_treeid | Tree identifier within the site (e.g. PIN_1001); links to other tree-level tables via primary_key. |
| confidence | Tree segmentation or index extraction confidence score (0–1). |
| NDVI_mean | Mean Normalized Difference Vegetation Index within the tree crown for this flight. |
| NDVI_std | Standard deviation of NDVI within the tree crown. |
| GNDVI_mean | Mean Green Normalized Difference Vegetation Index within the tree crown. |
| GNDVI_std | Standard deviation of GNDVI within the tree crown. |
| PRI_mean | Mean Photochemical Reflectance Index within the tree crown. |
| PRI_std | Standard deviation of PRI within the tree crown. |
| NDRE_mean | Mean Normalized Difference Red Edge Index within the tree crown. |
| NDRE_std | Standard deviation of NDRE within the tree crown. |
| CCI_mean | Mean Chlorophyll/Carotenoid Index within the tree crown. |
| CCI_std | Standard deviation of CCI within the tree crown. |
| NIRv_mean | Mean Near-Infrared Reflectance of Vegetation within the tree crown. |
| NIRv_std | Standard deviation of NIRv within the tree crown. |
| WaterIndex_mean | Mean water index within the tree crown. |
| WaterIndex_std | Standard deviation of the water index within the tree crown. |

## Notes

- Exports are consolidated by flight year (`uav_reflectance_2022.csv`, `uav_reflectance_2023.csv`).
- Dashboard charts use daily means across trees; compare mode shows per-tree distributions for a selected flight date.
