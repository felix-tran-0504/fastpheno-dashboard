# Pigments

Leaf pigment concentration exports from the III_db_final **Pigments** collection.

## Source layout

Campaign folders live under each field site and are named by sampling date (or date range):

```
Pigments/
  Pickering/   → PIK
    2023-12-14/
    2023-05-05/
    2022-09-xx/   (month-level when day is unknown)
  Pintendre/   → PIN
    2023-08-22/
    2023-06-21_2023-06-22/
```

Each folder contains the raw/processed files for that sampling event (e.g. PDF reports).

## Dashboard use

1. Choose **Site** (or all sites).
2. Set **From** / **To** date/time — campaigns whose folder dates overlap the range are included.
3. Click **Download data (ZIP)** — the archive preserves `SITE/folder-label/…` paths.

Configure the source root with `FASTPHENO_PIGMENTS_ROOT` (defaults to `III_db_final/Pigments` on this machine).
