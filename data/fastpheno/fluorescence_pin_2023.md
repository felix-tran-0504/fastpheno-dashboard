# Chlorophyll Fluorescence Metadata

## Metadata Description

| Column Name | Description |
|---|---|
| primary_key | Unique identifier consiting of site (e.g. PIK) and the trees rolling number (e.g. _1001). |
| datetime_est | Date and time of measurement acquisition (EST timezone). |
| datetime_ust | Date and time of measurement acquisition (UST timezone). |
| sensor | Identifier of the fluorometer or sensor used. |
| operator | Operator or user responsible for the measurement. |
| Fo | Minimum fluorescence yield in the dark-adapted state. |
| Fm | Maximum fluorescence yield in the dark-adapted state. |
| Fp | Peak fluorescence yield during induction. |
| Ft_L1 | Steady-state fluorescence at light level 1. |
| Ft_L2 | Steady-state fluorescence at light level 2. |
| Ft_L3 | Steady-state fluorescence at light level 3. |
| Ft_L4 | Steady-state fluorescence at light level 4. |
| Ft_L5 | Steady-state fluorescence at light level 5. |
| Ft_L6 | Steady-state fluorescence at light level 6. |
| Ft_L7 | Steady-state fluorescence at light level 7. |
| Ft_L8 | Steady-state fluorescence at light level 8. |
| Ft_L9 | Steady-state fluorescence at light level 9. |
| Ft_Lss | Steady-state fluorescence under stabilized light conditions. |
| Fm_L1 | Maximum fluorescence at light level 1. |
| Fm_L2 | Maximum fluorescence at light level 2. |
| Fm_L3 | Maximum fluorescence at light level 3. |
| Fm_L4 | Maximum fluorescence at light level 4. |
| Fm_L5 | Maximum fluorescence at light level 5. |
| Fm_L6 | Maximum fluorescence at light level 6. |
| Fm_L7 | Maximum fluorescence at light level 7. |
| Fm_L8 | Maximum fluorescence at light level 8. |
| Fm_L9 | Maximum fluorescence at light level 9. |
| Fm_Lss | Maximum fluorescence under stabilized light conditions. |
| NPQ_L1 | Non-photochemical quenching at light level 1. |
| NPQ_L2 | Non-photochemical quenching at light level 2. |
| NPQ_L3 | Non-photochemical quenching at light level 3. |
| NPQ_L4 | Non-photochemical quenching at light level 4. |
| NPQ_L5 | Non-photochemical quenching at light level 5. |
| NPQ_L6 | Non-photochemical quenching at light level 6. |
| NPQ_L7 | Non-photochemical quenching at light level 7. |
| NPQ_L8 | Non-photochemical quenching at light level 8. |
| NPQ_L9 | Non-photochemical quenching at light level 9. |
| NPQ_Lss | Non-photochemical quenching under stabilized light conditions. |
| Qp_L1 | Photochemical quenching coefficient at light level 1. |
| Qp_L2 | Photochemical quenching coefficient at light level 2. |
| Qp_L3 | Photochemical quenching coefficient at light level 3. |
| Qp_L4 | Photochemical quenching coefficient at light level 4. |
| Qp_L5 | Photochemical quenching coefficient at light level 5. |
| Qp_L6 | Photochemical quenching coefficient at light level 6. |
| Qp_L7 | Photochemical quenching coefficient at light level 7. |
| Qp_L8 | Photochemical quenching coefficient at light level 8. |
| Qp_L9 | Photochemical quenching coefficient at light level 9. |
| Qp_Lss | Photochemical quenching coefficient under stabilized light conditions. |
| Rfd | Fluorescence decrease ratio; indicator of photosynthetic activity. |
| Fm_D1 | Maximum fluorescence during dark recovery phase 1. |
| Fm_D2 | Maximum fluorescence during dark recovery phase 2. |
| NPQ_D1 | Non-photochemical quenching during dark recovery phase 1. |
| NPQ_D2 | Non-photochemical quenching during dark recovery phase 2. |
| Qp_D1 | Photochemical quenching coefficient during dark recovery phase 1. |
| Qp_D2 | Photochemical quenching coefficient during dark recovery phase 2. |
| QY_max | Maximum quantum yield of PSII photochemistry. |
| QY_L1 | Quantum yield at light level 1. |
| QY_L2 | Quantum yield at light level 2. |
| QY_L3 | Quantum yield at light level 3. |
| QY_L4 | Quantum yield at light level 4. |
| QY_L5 | Quantum yield at light level 5. |
| QY_L6 | Quantum yield at light level 6. |
| QY_L7 | Quantum yield at light level 7. |
| QY_L8 | Quantum yield at light level 8. |
| QY_L9 | Quantum yield at light level 9. |
| QY_Lss | Quantum yield under stabilized light conditions. |
| QY_D1 | Quantum yield during dark recovery phase 1. |
| QY_D2 | Quantum yield during dark recovery phase 2. |

## Derived Dashboard CSV (`fluorescence_pin_2023.csv`)

| Column Name | Description |
|---|---|
| site | Field site identifier (PIN). |
| year | Measurement year. |
| date | Date of measurement (YYYY-MM-DD). |
| QY_max | Daily mean maximum quantum yield of PSII. |
| NPQ_Lss | Daily mean non-photochemical quenching under stabilized light. |
| n_measurements | Number of tree-level measurements aggregated per day. |
