"""Stage 1A: guided, non-destructive TCDSE data intake and profiling."""
from io import BytesIO
import json
from pathlib import PurePosixPath
import zipfile

import pandas as pd
import solara

from ..components.file_drop import FileDrop

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_ROWS = 100_000
PLANNED_FORMATS = {
    ".parquet": "Parquet support is planned but is not enabled in this Stage 1A build..",
    ".gpkg": "GeoPackage support is planned but is not enabled in this Stage 1A build.",
    ".kml": "KML/KMZ support is planned but is not enabled in this Stage 1A build.",
    ".kmz": "KML/KMZ support is planned but is not enabled in this Stage 1A build.",
    ".tif": "GeoTIFF raster support is planned for a separate geospatial ingestion path.",
    ".tiff": "GeoTIFF raster support is planned for a separate geospatial ingestion path.",
    ".pdf": "PDF/OCR ingestion needs a separate extraction and human-verification workflow.",
    ".nc": "NetCDF climate data needs a specialist reader and is not enabled in Stage 1A.",
    ".grib": "GRIB weather data needs a specialist reader and is not enabled in Stage 1A.",
    ".xml": "XML support requires a source-specific parser and is not enabled in Stage 1A.",
}


def _suffix(filename):
    name = PurePosixPath(str(filename).replace("\\", "/")).name.lower()
    if name.endswith(".shp.zip"):
        return ".shp.zip"
    return "." + name.rsplit(".", 1)[-1] if "." in name else ""


def _read_json(content, line_delimited=False):
    text = content.decode("utf-8-sig")
    if line_delimited:
        records = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"JSON Lines parsing failed on line {line_number}: {exc.msg}.") from exc
        if not records:
            raise ValueError("No JSON records were found in the file.")
        return pd.json_normalize(records, sep=".")

    parsed = json.loads(text)
    if isinstance(parsed, list):
        return pd.json_normalize(parsed, sep=".")
    if isinstance(parsed, dict):
        if parsed.get("type") == "FeatureCollection" and isinstance(parsed.get("features"), list):
            rows = []
            for feature in parsed["features"]:
                if not isinstance(feature, dict):
                    continue
                row = dict(feature.get("properties") or {})
                geometry = feature.get("geometry")
                row["__geometry_type"] = geometry.get("type") if isinstance(geometry, dict) else None
                row["__geometry_json"] = json.dumps(geometry, ensure_ascii=False) if geometry else None
                rows.append(row)
            return pd.DataFrame(rows)
        if isinstance(parsed.get("data"), list):
            return pd.json_normalize(parsed["data"], sep=".")
        return pd.json_normalize(parsed, sep=".")
    raise ValueError("The JSON root must be an object or an array of records.")


def _read_uploaded_dataset(filename, content):
    if not content:
        raise ValueError("The uploaded file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("The file exceeds the 25 MB Stage 1A limit.")

    suffix = _suffix(filename)
    buffer = BytesIO(content)

    if suffix == ".csv":
        return pd.read_csv(buffer, nrows=MAX_ROWS)
    if suffix == ".tsv":
        return pd.read_csv(buffer, sep="\t", nrows=MAX_ROWS)
    if suffix == ".txt":
        try:
            return pd.read_csv(buffer, sep=None, engine="python", nrows=MAX_ROWS)
        except Exception as exc:
            raise ValueError("Could not identify a delimiter in this TXT file. Save it as CSV or TSV.") from exc
    if suffix in {".xlsx", ".xls"}:
        try:
            return pd.read_excel(buffer, nrows=MAX_ROWS)
        except ImportError as exc:
            if suffix == ".xls":
                raise ValueError(
                    "This legacy XLS file needs the optional 'xlrd' reader, which is not confirmed. "
                    "Please save it as XLSX or CSV."
                ) from exc
            raise ValueError("The Excel reader is unavailable. Please try CSV or contact the administrator.") from exc
        except Exception as exc:
            raise ValueError(
                "The Excel file could not be read. Check that it is not password-protected "
                "and contains a readable worksheet."
            ) from exc
    if suffix in {".json", ".jsonl", ".ndjson", ".geojson"}:
        try:
            return _read_json(content, line_delimited=suffix in {".jsonl", ".ndjson"})
        except UnicodeDecodeError as exc:
            raise ValueError("The file is not UTF-8 encoded.") from exc
        except json.JSONDecodeError as exc:
            raise ValueError("The JSON file is invalid. Check its structure and syntax.") from exc

    if suffix in {".zip", ".shp.zip"}:
        try:
            with zipfile.ZipFile(BytesIO(content)) as archive:
                names = [n.lower() for n in archive.namelist() if not n.endswith("/")]
                if not (any(n.endswith(".shp") for n in names)
                        and any(n.endswith(".shx") for n in names)
                        and any(n.endswith(".dbf") for n in names)):
                    raise ValueError(
                        "This ZIP does not appear to contain a complete Shapefile bundle. "
                        "Include .shp, .shx and .dbf files, plus .prj when available."
                    )
        except zipfile.BadZipFile as exc:
            raise ValueError("This ZIP file is damaged or invalid.") from exc
        raise ValueError(
            "A Shapefile bundle was detected, but spatial feature loading is not enabled in this build. "
            "GeoJSON is supported for initial inspection."
        )

    if suffix in PLANNED_FORMATS:
        raise ValueError(PLANNED_FORMATS[suffix])
    raise ValueError(
        "This format is not enabled yet. Available now: CSV, TSV, delimited TXT, XLSX, JSON, "
        "JSON Lines (.jsonl/.ndjson) and GeoJSON. See the format guide below."
    )


def _profile_dataframe(dataframe):
    diagnostics = []
    for position, column in enumerate(dataframe.columns):
        series = dataframe.iloc[:, position]
        diagnostics.append({
            "source_column": str(column),
            "inferred_type": str(series.dtype),
            "missing_count": int(series.isna().sum()),
            "missing_percent": round(float(series.isna().mean() * 100), 2) if len(series) else 0.0,
            "distinct_values": int(series.nunique(dropna=True)),
        })
    return pd.DataFrame(diagnostics)


@solara.component
def Page():
    filename, set_filename = solara.use_state("")
    dataframe, set_dataframe = solara.use_state(None)
    source_kind, set_source_kind = solara.use_state("")
    error_message, set_error_message = solara.use_state("")
    upload_notice, set_upload_notice = solara.use_state("")

    def on_file(fileinfo):
        set_error_message("")
        set_upload_notice("")
        try:
            name = str(fileinfo.get("name", "uploaded file"))
            content = fileinfo.get("data")
            if content is None:
                raise ValueError("The upload did not provide file content. Please try again.")
            df = _read_uploaded_dataset(name, content)
            if len(df.columns) == 0:
                raise ValueError("No tabular columns were detected in the uploaded file.")
            suffix = _suffix(name)
            kind = "GeoJSON feature attributes (geometry retained as inspection metadata)" if suffix == ".geojson" else "Tabular dataset"
            row_note = f" The preview is capped at {MAX_ROWS:,} rows." if len(df) >= MAX_ROWS else ""
            set_filename(name)
            set_dataframe(df)
            set_source_kind(kind)
            set_upload_notice(f"{kind} loaded in memory. No source or cloud data has been changed.{row_note}")
        except Exception as exc:
            set_filename("")
            set_dataframe(None)
            set_source_kind("")
            set_error_message(str(exc))

    with solara.Column(gap="12px"):
        solara.Title("Data Harmonisation")
        solara.Markdown(
            """
            # TCDSE Data Harmonisation

            Bring a dataset in a supported format. The system checks whether it can
            read the file, previews the content and profiles the source before any
            mapping or transformation is considered.

            **Stage 1A safety boundary:** uploads remain in application memory.
            This page does not write to Azure storage, alter source files, or invent
            missing observations, building classes or vulnerability curves.
            """
        )
        with solara.Card():
            solara.Markdown("## 1. Add your data")
            solara.Markdown(
                "**Available now:** CSV, TSV, delimited TXT, XLSX, JSON, JSON Lines "
                "(`.jsonl`/`.ndjson`) and GeoJSON. Maximum upload size: 25 MB; tabular "
                f"preview capped at {MAX_ROWS:,} rows. Legacy XLS may require an additional reader."
            )
            FileDrop(
                label="Drop a supported data file here, or click to browse",
                on_file=on_file,
                lazy=False,
                uid="tcdse-harmonisation-upload",
            )
            if upload_notice:
                solara.Success(upload_notice)
            if error_message:
                solara.Error(error_message)

        with solara.Card():
            solara.Markdown("## 2. Format guide")
            solara.Markdown(
                """
                **Available in this build**
                - Tables: `.csv`, `.tsv`, delimited `.txt`, `.xlsx`
                - Structured records: `.json`, `.jsonl`, `.ndjson`
                - Geographic features: `.geojson` (attributes and geometry metadata are shown; spatial validation is not yet performed)

                **Planned ingestion paths**
                - `.xls` after verifying/installing the legacy Excel reader
                - Shapefile bundles (`.zip` containing `.shp`, `.shx` and `.dbf`)
                - Parquet, GeoPackage, KML/KMZ and GeoTIFF
                - PDF/scanned reports (table extraction/OCR with human confirmation)
                - NetCDF/GRIB climate data and API/database/cloud connections

                Unsupported formats are not silently converted. The page explains what is
                missing and suggests a supported route.
                """
            )

        if dataframe is not None:
            with solara.Card():
                solara.Markdown("## 3. Source profile")
                solara.Markdown(
                    f"**File:** `{filename}`  \n**Detected content:** {source_kind}  \n"
                    f"- Rows loaded: **{len(dataframe):,}**  \n"
                    f"- Columns: **{len(dataframe.columns):,}**  \n"
                    f"- Duplicate column names: **{int(dataframe.columns.duplicated().sum())}**"
                )
                solara.Markdown("### Column-level diagnostics")
                solara.DataFrame(_profile_dataframe(dataframe))
                solara.Markdown("### Preview (first 20 rows)")
                solara.DataFrame(dataframe.head(20))
            with solara.Card():
                solara.Markdown("## 4. Next step")
                solara.Markdown(
                    """
                    Source inspection is complete. Target-schema mapping, harmonisation,
                    export and persistent storage are not enabled in Stage 1A.

                    Later stages should suggest mappings but require confirmation where
                    semantics or units are uncertain, and retain source provenance,
                    transformation rules, confidence and human-review status.
                    """
                )
        else:
            with solara.Card():
                solara.Markdown("## Workflow status")
                solara.Markdown(
                    "1. Identify/read supported format — **pending**\n"
                    "2. Preview and profile source — **pending**\n"
                    "3. Map to a target schema — **not enabled in Stage 1A**\n"
                    "4. Validate, harmonise and export — **not enabled in Stage 1A**"
                )
