# # Optimised, attribute-safe road clipping and placement
# - Preserves ONLY road attributes after clip (no ROI attrs are introduced)
# - Uses prepared geometries for faster within/intersection checks
# - Avoids per-iteration GeoSeries rotation overhead (uses shapely.affinity.rotate)
# - Explodes geometries efficiently and preserves attributes on segmentization
# - Keeps logic identical where possible, but removes unused pieces and redundant unions

import geopandas as gpd
import pandas as pd
import numpy as np
from shapely.geometry import Point, LineString, MultiLineString, box
from shapely.ops import unary_union
from shapely.affinity import rotate
from shapely.prepared import prep
import math
import random

# --- HELPERS ---
def calculate_road_angle(road_segment):
    """
    Bir LineString veya MultiLineString geometrisinin başlangıç ve bitiş
    noktalarına göre açısını (derece cinsinden) hesaplar.
    """
    line_to_process = None
    
    # Gelen geometrinin tipini kontrol et
    if road_segment.geom_type == 'MultiLineString':
        # Eğer MultiLineString ise ve içinde en az bir çizgi varsa, ilk çizgiyi al
        if road_segment.geoms:
            line_to_process = road_segment.geoms[0]
    elif road_segment.geom_type == 'LineString':
        # Eğer zaten LineString ise, doğrudan kendisini kullan
        line_to_process = road_segment

    # İşlenecek geçerli bir çizgi var mı ve en az 2 noktası var mı diye kontrol et
    if line_to_process and len(line_to_process.coords) >= 2:
        # Koordinatları doğrudan unpack etmek yerine, indekse göre alıyoruz.
        # Bu sayede koordinat (X, Y) de olsa, (X, Y, Z) de olsa sadece ilk iki değeri alırız.
        start_coord = line_to_process.coords[0]
        end_coord = line_to_process.coords[-1]

        sx, sy = start_coord[0], start_coord[1]
        ex, ey = end_coord[0], end_coord[1]
        
        return np.degrees(np.arctan2(ey - sy, ex - sx))
    
    # Eğer geçerli bir çizgi bulunamazsa varsayılan olarak 0.0 açısını döndür.
    return 0.0

def explode_geometry(gdf):
    """Explode multipart geometries; fastest path with geopandas >= 0.8."""
    try:
        return gdf.explode(index_parts=False).reset_index(drop=True)
    except Exception:
        # Fallback for very old versions
        rows = []
        for _, row in gdf.iterrows():
            geom = row.geometry
            if geom is None:
                continue
            if hasattr(geom, "geoms"):
                for part in geom.geoms:
                    d = row.to_dict(); d["geometry"] = part; rows.append(d)
            else:
                rows.append(row.to_dict())
        return gpd.GeoDataFrame(rows, crs=gdf.crs)

def segmentize_lines(roads_gdf):
    """
    Split each (Multi)LineString into straight segments while PRESERVING
    all original road attributes (no ROI attributes added).
    """
    keep_cols = [c for c in roads_gdf.columns if c != "geometry"]
    out = []
    for _, row in roads_gdf.iterrows():
        geom = row.geometry
        if geom is None:
            continue
        if geom.geom_type == "LineString":
            coords = list(geom.coords)
            for i in range(len(coords) - 1):
                d = {c: row[c] for c in keep_cols}
                d["geometry"] = LineString([coords[i], coords[i + 1]])
                out.append(d)
        elif geom.geom_type == "MultiLineString":
            for part in geom.geoms:
                coords = list(part.coords)
                for i in range(len(coords) - 1):
                    d = {c: row[c] for c in keep_cols}
                    d["geometry"] = LineString([coords[i], coords[i + 1]])
                    out.append(d)
    return gpd.GeoDataFrame(out, crs=roads_gdf.crs) if out else gpd.GeoDataFrame(columns=keep_cols + ["geometry"], crs=roads_gdf.crs)

def clip_roads_keep_attrs(roads_gdf, mask_geom):
    """
    Clip roads by mask geometry while KEEPING ONLY road attributes.
    gpd.clip returns left dataset's columns by design → no ROI attributes.
    """
    mask = gpd.GeoDataFrame(geometry=[mask_geom], crs=roads_gdf.crs)
    clipped = gpd.clip(roads_gdf, mask)
    # Remove any helper columns produced by some geopandas versions
    drop_cols = [c for c in clipped.columns if c.startswith("index_") or c == "index"]
    if drop_cols:
        clipped = clipped.drop(columns=drop_cols, errors="ignore")
    return clipped.reset_index(drop=True)

# --- MAIN ---
def generate_city_layout(landuse_layer, building_data, road_network=None):
    """
    Generates city layout with stable, fast, single-core vector workflows.
    - Road clipping preserves original road attributes.
    - ROI (polygon) attributes are never propagated into roads.
    - Returns (final_buildings_gdf, final_roads_gdf) in landuse_layer CRS.
    """
    # DEBUG
    #print("Starting STABLE-FAST generation with SETBACK RULES...")

    # OPTIMIZED: Imports and helpers are defined at the module level, not redefined here.

    # CRS prep
    landuse_projected = landuse_layer.to_crs("EPSG:3395") if landuse_layer.crs.is_geographic else landuse_layer
    road_network_projected = road_network.to_crs(landuse_projected.crs) if road_network is not None else None

    all_placed = []
    # OPTIMIZED: Removed `clipped_roads_all` list as it was unused in the final output.

    for zone_id, buildings_in_zone in building_data.groupby("zoneid"):
        # DEBUG
        # print(f"Processing Zone ID: {zone_id}")
        zone_polys = landuse_projected[landuse_projected["zoneid"] == zone_id].copy()
        if zone_polys.empty or buildings_in_zone.empty:
            continue

        # placement areas (landuse setbacks)
        if "setback" in zone_polys.columns:
            zone_polys["setback"] = pd.to_numeric(zone_polys["setback"], errors="coerce").fillna(0.0)
            zone_polys["placement_area"] = zone_polys.apply(
                lambda r: (r.geometry.buffer(-float(r.setback)) if float(r.setback) > 0.0 else r.geometry), axis=1
            )
        else:
            zone_polys["placement_area"] = zone_polys.geometry

        zone_polys = zone_polys[~zone_polys.placement_area.is_empty]
        if zone_polys.empty:
            continue

        zone_polys = zone_polys.reset_index(drop=True)
        zone_polys["pa_id"] = np.arange(len(zone_polys), dtype=int)
        unified_placement_area = unary_union(zone_polys.placement_area)

        landuse_boundary = unary_union(zone_polys.geometry).boundary
        # OPTIMIZED: `alignment_roads_geom` was calculated but never used, so it has been removed.
        exclusion_zone_geom = landuse_boundary

        # roads: clip by zone placement area; keep only road attrs
        clipped_roads = gpd.GeoDataFrame()
        if road_network_projected is not None:
            clipped_roads = clip_roads_keep_attrs(road_network_projected, unified_placement_area)
            if not clipped_roads.empty:
                # OPTIMIZED: Removed adding `__zone__` and appending to `clipped_roads_all` as it was unused.
                
                # OPTIMIZED: The unary_union for the (unused) alignment_roads_geom was removed.

                if "setback" in clipped_roads.columns:
                    clipped_roads["setback"] = pd.to_numeric(clipped_roads["setback"], errors="coerce").fillna(0.0)
                    buffered = [(g.buffer(dist) if dist > 0.0 else g) for g, dist in zip(clipped_roads.geometry, clipped_roads["setback"])]
                else:
                    buffered = list(clipped_roads.geometry.values)
                road_buffers = unary_union(buffered) if buffered else unary_union(clipped_roads.geometry)
                exclusion_zone_geom = unary_union([road_buffers, exclusion_zone_geom])

        exclusion_prepared = prep(exclusion_zone_geom) if not getattr(exclusion_zone_geom, "is_empty", True) else None

        # --- DÜZELTİLMİŞ HİZALAMA MANTIĞI BAŞLANGICI ---
        # Binaların hizalanacağı geometrileri hazırlıyoruz.
        # Önce parselin dış sınırlarını alıyoruz.
        alignment_geom = landuse_boundary

        # Eğer bölge içinde kırpılmış yollar varsa, bunları da hizalama geometrisine ekliyoruz.
        # Eski koddaki güvenli unary_union yöntemini burada geri getiriyoruz.
        if not clipped_roads.empty:
            # Poligon geometrilerinin sınır çizgilerini (boundary) çıkararak hizalama için kullanıyoruz.
            extracted_geoms = []
            for geom in clipped_roads.geometry:
                if geom.geom_type in ['Polygon', 'MultiPolygon']:
                    extracted_geoms.append(geom.boundary)
                else:
                    extracted_geoms.append(geom)
            alignment_geom = unary_union([unary_union(extracted_geoms), alignment_geom])

        # Hizalama geometrilerini işlemek için GeoDataFrame oluşturuyoruz.
        alignment_gdf = gpd.GeoDataFrame(columns=["geometry", "angle"])
        if not getattr(alignment_geom, "is_empty", True):
            temp_gdf = gpd.GeoDataFrame(geometry=[alignment_geom], crs=zone_polys.crs)
            exploded_gdf = explode_geometry(temp_gdf)
            segments_gdf = segmentize_lines(exploded_gdf)
            if not segments_gdf.empty:
                segments_gdf["angle"] = segments_gdf["geometry"].apply(calculate_road_angle)
                alignment_gdf = segments_gdf
        # --- DÜZELTİLMİŞ HİZALAMA MANTIĞI SONU ---

        # grid
        xmin, ymin, xmax, ymax = unified_placement_area.bounds
        try:
            grid_spacing = float(np.sqrt(float(buildings_in_zone["fptarea"].max()))) * 1.5
        except Exception:
            grid_spacing = 50.0

        xs = np.arange(xmin, xmax, grid_spacing)
        ys = np.arange(ymin, ymax, grid_spacing)
        if xs.size == 0 or ys.size == 0:
            continue

        pts = [Point(x, y) for x in xs for y in ys]
        if not pts:
            continue
        grid_gdf = gpd.GeoDataFrame(geometry=pts, crs=landuse_projected.crs)

        zjoin = gpd.GeoDataFrame(
            zone_polys[["pa_id"]], 
            geometry=zone_polys["placement_area"], 
            crs=zone_polys.crs
        )
        try:
            sjoin_res = gpd.sjoin(grid_gdf, zjoin, how="inner", predicate="within")
        except TypeError:
            sjoin_res = gpd.sjoin(grid_gdf, zjoin, how="inner", op="within")
            
        if sjoin_res.empty:
            continue
        grid_gdf = sjoin_res.drop(columns=["index_right"]).reset_index(drop=True)

        if not alignment_gdf.empty and "angle" in alignment_gdf.columns:
            grid_gdf = gpd.sjoin_nearest(grid_gdf, alignment_gdf[["geometry", "angle"]], how="left")
        else:
            grid_gdf["angle"] = 0.0

        grid_gdf = grid_gdf.sample(frac=1.0).reset_index(drop=True)

        pa_dict = {r.pa_id: prep(r.placement_area) for _, r in zone_polys[["pa_id", "placement_area"]].iterrows()}

        # OPTIMIZATION: Instead of building a GeoDataFrame with pd.concat in a loop,
        # we will collect placed geometries in a simple list. This is much faster.
        placed_geoms_in_zone = []
        
        # IMPROVEMENT: Sort buildings by 'fptarea' descending.
        # This ensures large buildings (Schools, Hospitals) are placed FIRST when space is most available.
        # Convert to list to use as a queue.
        if 'fptarea' in buildings_in_zone.columns:
            # Ensure fptarea is numeric for sorting
            buildings_in_zone['fptarea'] = pd.to_numeric(buildings_in_zone['fptarea'], errors='coerce').fillna(0)
            buildings_in_zone = buildings_in_zone.sort_values(by='fptarea', ascending=False)
            
        building_queue = list(buildings_in_zone.itertuples())

        for _, pt in grid_gdf.iterrows():
            if not building_queue:
                break
            
            # Peek at the current building to place (do not pop yet)
            b = building_queue[0]

            area = float(b.fptarea)
            width = random.uniform(0.7, 1.4) * math.sqrt(area)
            height = area / width
            p = pt.geometry
            ang = float(pt.angle) if pd.notna(pt.angle) else 0.0

            rect = box(p.x - width / 2.0, p.y - height / 2.0, p.x + width / 2.0, p.y + height / 2.0)
            rotated = rotate(rect, ang, origin=(p.x, p.y), use_radians=False)

            pa_prep = pa_dict.get(int(pt.pa_id))
            if pa_prep is None or not pa_prep.contains(rotated):
                continue

            if exclusion_prepared is not None and exclusion_prepared.intersects(rotated):
                continue
            
            # OPTIMIZATION: Check for intersection against previously placed geometries
            # using a temporary GeoSeries to leverage the spatial index (sindex).
            # This avoids the slow, iterative growth of a GeoDataFrame with pd.concat.
            if placed_geoms_in_zone:
                # Create a lightweight GeoSeries on-the-fly to access the sindex
                temp_placed_s = gpd.GeoSeries(placed_geoms_in_zone, crs=landuse_projected.crs)
                # Use sindex to find potential intersections quickly
                possible_matches_idx = list(temp_placed_s.sindex.intersection(rotated.bounds))
                if possible_matches_idx:
                    # Check for actual intersection only on the candidates
                    if temp_placed_s.iloc[possible_matches_idx].intersects(rotated).any():
                        continue

            # If all checks pass, add the new geometry to our list for this zone
            placed_geoms_in_zone.append(rotated)
            
            # SUCCESS: Building placed. Remove from queue and move to next building.
            building_queue.pop(0)
            
            # Append the full attribute record and geometry for the final output
            attrs = b._asdict()
            attrs.pop("Index", None)
            attrs["geometry"] = rotated
            all_placed.append(attrs)
    # DEBUG
    #print("All zones processed. Creating final GeoDataFrames...")

    # Buildings output
    if all_placed:
        final_buildings = gpd.GeoDataFrame(all_placed, crs=landuse_projected.crs).to_crs(landuse_layer.crs)
    else:
        final_buildings = gpd.GeoDataFrame(crs=landuse_layer.crs)

    # --- Roads output (use ORIGINAL road_network; keep only parts that intersect ANY polygon in landuse_layer) ---
    def _final_roads_from_all_polygons(road_network, landuse_layer):
        if road_network is None or road_network.empty:
            return gpd.GeoDataFrame(geometry=[], crs=landuse_layer.crs)
    
        # The original CRS of the input layer
        target_crs = landuse_layer.crs
        # A projected CRS suitable for calculations (meters) / Conformal
        calc_crs = "EPSG:3395" 
    
        roads_in_target = road_network.to_crs(target_crs)
    
        # Use ALL polygons (building + non-building), fix invalids
        lu_poly = landuse_layer[landuse_layer.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].copy()
        if lu_poly.empty:
            return gpd.GeoDataFrame(geometry=[], crs=target_crs)
        lu_poly["geometry"] = lu_poly.geometry.buffer(0)
    
        # Union once for performance, then create the mask
        mask_union = lu_poly.geometry.union_all()
        mask_gdf = gpd.GeoDataFrame(geometry=[mask_union], crs=target_crs)
    
        # --- MODIFICATION START ---
        # Re-project both roads and mask to the calculation CRS before clipping
        roads_for_calc = roads_in_target.to_crs(calc_crs)
        mask_for_calc = mask_gdf.to_crs(calc_crs)
        
        clipped = gpd.clip(roads_for_calc, mask_for_calc)
    
        # Clean up: drop empties/zero-length and exact-geometry dups
        # This length check is now correctly performed on projected data (in meters)
        clipped = clipped[~clipped.geometry.is_empty]
        clipped = clipped[clipped.geometry.length > 0]
        
        if not clipped.empty:
            # Perform remaining cleanup
            clipped["__wkb__"] = clipped.geometry.apply(lambda g: g.wkb if g is not None else None)
            clipped = clipped.drop_duplicates(subset="__wkb__").drop(columns="__wkb__", errors="ignore")
            
            # Convert final, cleaned roads back to the original target CRS
            clipped = clipped.to_crs(target_crs)
        # --- MODIFICATION END ---
            
        return clipped.reset_index(drop=True)
    
    # Call right before returning:
    final_roads = _final_roads_from_all_polygons(road_network, landuse_layer)
    
    return final_buildings#, final_roads
