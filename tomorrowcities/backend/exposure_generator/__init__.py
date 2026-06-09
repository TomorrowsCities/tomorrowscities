import io
import os
import tempfile
from typing import Iterable, List

import geopandas as gpd
import pandas as pd

from .data_processing import process_data
from .osm_constraints import fetch_osm_constraints, merge_constraints


def read_geospatial_bytes(filename: str, data: bytes) -> gpd.GeoDataFrame:
    ext = os.path.splitext(filename)[1].lower()
    if ext in [".zip", ".rar", ".gpkg", ".kml"]:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_file:
            tmp_file.write(data)
            tmp_file_path = tmp_file.name
        try:
            gdf = gpd.read_file(tmp_file_path)
        finally:
            try:
                os.remove(tmp_file_path)
            except OSError:
                pass
    else:
        gdf = gpd.read_file(io.BytesIO(data))
    return gdf.reset_index(drop=True)


def read_multiple_geospatial_bytes(files: Iterable[dict]) -> gpd.GeoDataFrame | None:
    gdf_list: List[gpd.GeoDataFrame] = []
    for fileinfo in files:
        if not fileinfo.get("data"):
            continue
        gdf = read_geospatial_bytes(fileinfo["name"], fileinfo["data"])
        if gdf.crs is None:
            gdf = gdf.set_crs("EPSG:4326")
        gdf_list.append(gdf.to_crs("EPSG:4326"))
    if not gdf_list:
        return None
    merged = pd.concat(gdf_list, ignore_index=True)
    return gpd.GeoDataFrame(merged, geometry="geometry", crs="EPSG:4326")


def read_excel_bytes(data: bytes) -> io.BytesIO:
    file_obj = io.BytesIO(data)
    file_obj.seek(0)
    return file_obj
