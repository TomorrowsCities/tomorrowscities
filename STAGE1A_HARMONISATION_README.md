# TCDSE Stage 1A — Guided Data Harmonisation intake

This patch adds an isolated Solara page for guided, non-destructive data intake
and source profiling. It is not yet a harmonisation engine.

## Files
- `tomorrowcities/pages/harmonisation.py` — new page
- `navigation.patch` — navigation/public-route edits for `tomorrowcities/pages/__init__.py`

## Enabled in this increment
- CSV, TSV, delimited TXT
- XLSX
- JSON objects/arrays and a common `data: [...]` response shape
- JSON Lines (`.jsonl`, `.ndjson`)
- GeoJSON FeatureCollections (properties plus geometry metadata for inspection)

A Shapefile ZIP is checked for expected components, but actual spatial loading is
not enabled until GeoPandas/GDAL behaviour is verified in the target container.
Legacy XLS may require `xlrd`; if unavailable, the user receives an actionable
message recommending XLSX or CSV.

## Planned, not enabled
Parquet, Shapefile ingestion, GeoPackage, KML/KMZ, GeoTIFF, PDF/OCR,
NetCDF/GRIB, and API/database/cloud connections. These need dedicated reader,
validation and (where applicable) credential/security workflows.

## Safety boundaries
- 25 MB upload limit; 100,000-row tabular reader cap.
- Uploaded content remains in application memory; no persistent writes.
- No mapping, transformation, export, AI inference or fabrication of missing data.
- GeoJSON geometry is shown as inspection metadata; this build does not validate
  coordinate reference systems, geometry validity or spatial coverage.

## Apply in a development checkout, not inside the running Azure container
1. Create a feature branch and confirm the working tree is clean:
   ```bash
   git switch -c feature/tcdse-harmonisation-stage1a
   git status --short
   ```
2. Copy `tomorrowcities/pages/harmonisation.py` into that path in the checkout.
3. From the repository root, apply the navigation patch:
   ```bash
   git apply navigation.patch
   ```
4. Review:
   ```bash
   git diff --check
   git diff
   ```
5. Test locally:
   ```bash
   solara run tomorrowcities.pages --host 127.0.0.1 --port 8765
   ```

## Before release
Test route discovery/access, each reader with valid/malformed/empty/oversized
examples, upload error handling, and memory behaviour. Verify the actual Azure
Container Apps deployment mechanism; do not assume a build-and-push workflow
automatically deploys the app. Do not modify the running container or production data.
