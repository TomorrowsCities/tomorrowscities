import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, Polygon
from shapely.ops import polygonize, unary_union


OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


def _bbox_query(bounds):
    minx, miny, maxx, maxy = bounds
    return f"{miny},{minx},{maxy},{maxx}"


def _build_overpass_query(bounds):
    bbox = _bbox_query(bounds)
    return f"""
    [out:json][timeout:90];
    (
      way["building"]({bbox});
      relation["building"]({bbox});
      way["highway"]({bbox});
    );
    out geom;
    """


def _parse_road_setback(tags):
    width_raw = tags.get("width")
    if width_raw is not None:
        width_text = str(width_raw).strip().lower().replace("meters", "").replace("meter", "").replace("m", "").strip()
        try:
            width_value = float(width_text)
            if width_value > 0:
                return max(width_value / 2.0, 2.0)
        except ValueError:
            pass
    return 5.0


def _relation_outer_polygons(relation_element):
    outer_lines = []
    for member in relation_element.get("members", []):
        if member.get("role") != "outer":
            continue
        geometry = member.get("geometry", [])
        if len(geometry) < 4:
            continue
        coords = [(node["lon"], node["lat"]) for node in geometry]
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        outer_lines.append(LineString(coords))

    if not outer_lines:
        return []

    merged = unary_union(outer_lines)
    return [geom for geom in polygonize(merged) if not geom.is_empty]


def _elements_to_gdf(elements):
    building_records = []
    road_records = []

    for element in elements:
        tags = element.get("tags", {})
        osm_id = element.get("id")
        element_type = element.get("type", "unknown")

        if "building" in tags:
            if element_type == "way":
                geometry = element.get("geometry", [])
                if len(geometry) >= 4:
                    coords = [(node["lon"], node["lat"]) for node in geometry]
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])
                    polygon = Polygon(coords)
                    if polygon.is_valid and not polygon.is_empty:
                        building_records.append(
                            {
                                "id": osm_id,
                                "source": "osm",
                                "osm_type": element_type,
                                "feature_type": "building",
                                "setback": 0.0,
                                "population": 0,
                                "geometry": polygon,
                            }
                        )
            elif element_type == "relation":
                for polygon in _relation_outer_polygons(element):
                    building_records.append(
                        {
                            "id": osm_id,
                            "source": "osm",
                            "osm_type": element_type,
                            "feature_type": "building",
                            "setback": 0.0,
                            "population": 0,
                            "geometry": polygon,
                        }
                    )

        if "highway" in tags and element_type == "way":
            geometry = element.get("geometry", [])
            if len(geometry) >= 2:
                coords = [(node["lon"], node["lat"]) for node in geometry]
                line = LineString(coords)
                if line.is_valid and not line.is_empty:
                    road_records.append(
                        {
                            "id": osm_id,
                            "source": "osm",
                            "osm_type": element_type,
                            "feature_type": "road",
                            "highway": tags.get("highway"),
                            "setback": _parse_road_setback(tags),
                            "population": 0,
                            "geometry": line,
                        }
                    )

    records = building_records + road_records
    if not records:
        return gpd.GeoDataFrame(columns=["id", "source", "osm_type", "feature_type", "setback", "population", "geometry"], geometry="geometry", crs="EPSG:4326")

    return gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")


def fetch_osm_constraints(landuse_gdf):
    """Fetch OSM building and road geometries intersecting the uploaded land-use area."""
    if landuse_gdf is None or landuse_gdf.empty:
        raise ValueError("Land-use layer must be loaded before fetching OSM exclusion features.")

    landuse_wgs84 = landuse_gdf if landuse_gdf.crs == "EPSG:4326" else landuse_gdf.to_crs("EPSG:4326")
    query = _build_overpass_query(landuse_wgs84.total_bounds)
    payload = urlencode({"data": query}).encode("utf-8")
    response_data = None
    last_error = None
    for overpass_url in OVERPASS_URLS:
        request = Request(
            overpass_url,
            data=payload,
            headers={
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                "User-Agent": "expo-data-generator/1.0",
            },
        )

        try:
            with urlopen(request, timeout=120) as response:
                response_data = response.read().decode("utf-8")
                break
        except (HTTPError, URLError, TimeoutError) as exc:
            last_error = exc
            continue

    if response_data is None:
        raise RuntimeError(f"OSM fetch failed from all configured Overpass endpoints. Last error: {last_error}")

    osm_json = json.loads(response_data)
    osm_gdf = _elements_to_gdf(osm_json.get("elements", []))
    if osm_gdf.empty:
        return osm_gdf

    landuse_mask = landuse_wgs84[["geometry"]].copy()
    landuse_union = unary_union(landuse_mask.geometry)
    osm_gdf = osm_gdf[osm_gdf.geometry.intersects(landuse_union)].copy()
    osm_gdf.reset_index(drop=True, inplace=True)
    return osm_gdf


def merge_constraints(existing_gdf, new_gdf):
    """Merge existing and newly fetched constraint layers into a single GeoDataFrame."""
    if new_gdf is None or new_gdf.empty:
        return existing_gdf

    if existing_gdf is None or existing_gdf.empty:
        merged = new_gdf.copy()
    else:
        left = existing_gdf.copy()
        right = new_gdf.copy()
        if left.crs is None:
            left = left.set_crs("EPSG:4326")
        if right.crs is None:
            right = right.set_crs("EPSG:4326")
        right = right.to_crs(left.crs)
        merged = pd.concat([left, right], ignore_index=True)

    return gpd.GeoDataFrame(merged, geometry="geometry", crs=merged.crs if hasattr(merged, "crs") else "EPSG:4326")
