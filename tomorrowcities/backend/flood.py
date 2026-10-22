"""Validated, linear-memory interpolation of flood depth/damage curves."""

import re

import geopandas as gpd
import numpy as np
import pandas as pd
from affine import Affine
from pyproj import CRS
from rasterio.transform import rowcol
from shapely.geometry import Polygon


STANDARD_DEPTH_COLUMNS = ['hw0', 'hw0_5', 'hw1', 'hw1_5', 'hw2', 'hw3', 'hw4', 'hw5', 'hw6']


def flood_curve_columns(frame):
    """Recognize the usual hw columns and optional deeper-water knots in metres."""
    missing = set(STANDARD_DEPTH_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing flood vulnerability columns: {sorted(missing)}")
    pairs = []
    for column in frame.columns:
        match = re.fullmatch(r'hw(\d+)(?:_(\d+))?', str(column))
        if match:
            depth = float(match[1] + ('.' + match[2] if match[2] else ''))
            pairs.append((depth, column))
    pairs.sort()
    depths = np.array([x[0] for x in pairs], dtype=float)
    if (np.diff(depths) <= 0).any():
        raise ValueError('Flood curve depth knots must be unique')
    return depths, [x[1] for x in pairs]


def validate_flood_vulnerability(frame):
    if 'expstr' not in frame or frame.expstr.isna().any() or frame.expstr.duplicated().any():
        raise ValueError('Flood vulnerability requires unique, non-null expstr values')
    depths, columns = flood_curve_columns(frame)
    values = frame[columns].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError('Flood vulnerability has missing/non-finite values or uncovered exposure classes')
    if ((values < 0) | (values > 1)).any() or (np.diff(values, axis=1) < -1e-10).any():
        raise ValueError('Flood damage ratios must be within [0, 1] and nondecreasing')
    if not np.allclose(values[:, 0], 0):
        raise ValueError('Zero flood depth must have zero damage')
    return depths, columns


def interpolate_flood_rows(depths, knots, curves):
    """Interpolate curve j at depth j without creating an N x N array.

    Beyond the last knot hold the last value. A multi-storey curve may have a
    maximum below one; crossing its last knot must not imply total destruction.
    Optional deeper-water knots allow explicit continuation of those curves.
    """
    d = np.asarray(depths, dtype=float)
    x = np.asarray(knots, dtype=float)
    y = np.asarray(curves, dtype=float)
    if y.shape != (len(d), len(x)) or len(x) < 2 or (np.diff(x) <= 0).any():
        raise ValueError('Invalid flood interpolation array dimensions or knots')
    if not np.isfinite(d).all() or not np.isfinite(y).all():
        raise ValueError('Flood depths and vulnerability values must be finite')
    lower = np.clip(np.searchsorted(x, d, side='right') - 1, 0, len(x) - 2)
    weight = np.clip((d - x[lower]) / (x[lower + 1] - x[lower]), 0, 1)
    rows = np.arange(len(d))
    return y[rows, lower] * (1 - weight) + y[rows, lower + 1] * weight


def join_sampled_flood_depth(buildings, hazard):
    """Join already sampled raster depths by ID, without nearest-point leakage."""
    if hazard.bldid.duplicated().any() or hazard.bldid.isna().any():
        raise ValueError('Sampled flood hazard must have one record per bldid')
    joined = buildings.merge(hazard[['bldid', 'im']], on='bldid', how='left', validate='one_to_one')
    if joined.im.isna().any() or not np.isfinite(joined.im).all() or (joined.im < 0).any():
        raise ValueError('Sampled flood hazard requires finite nonnegative depth for every building')
    joined['distance'] = 0.0
    return joined


def raster_flood_cells(hazard):
    """Recover the exact imported TIFF cell footprints from lightweight metadata."""
    metadata = hazard.attrs.get('raster_grid')
    if not metadata:
        return None
    transform = Affine(*metadata['transform'])
    width, height = int(metadata['width']), int(metadata['height'])
    if width <= 0 or height <= 0 or transform.determinant == 0:
        raise ValueError('Invalid imported raster grid')
    points = hazard.to_crs(CRS.from_user_input(metadata['crs']))
    rows, cols = rowcol(transform, points.geometry.x, points.geometry.y)
    rows, cols = np.asarray(rows), np.asarray(cols)
    if ((rows < 0) | (rows >= height) | (cols < 0) | (cols >= width)).any():
        raise ValueError('Flood points do not match the imported raster grid')
    center_x = transform.a*(cols+.5) + transform.b*(rows+.5) + transform.c
    center_y = transform.d*(cols+.5) + transform.e*(rows+.5) + transform.f
    tolerance = max(abs(transform.a), abs(transform.b), abs(transform.d), abs(transform.e))*1e-5
    if not (np.allclose(center_x, points.geometry.x, atol=tolerance, rtol=0) and
            np.allclose(center_y, points.geometry.y, atol=tolerance, rtol=0)):
        raise ValueError('Flood points were moved relative to their raster cells; reload the TIFF')
    cells = [Polygon([transform*(col,row), transform*(col+1,row),
                      transform*(col+1,row+1), transform*(col,row+1)])
             for row,col in zip(rows,cols)]
    return gpd.GeoDataFrame({'im': points['im'].to_numpy()}, geometry=cells, crs=points.crs)


def join_road_flood_depth(roads, hazard, max_distance):
    """Assign nearest flood measurements within the metric distance cutoff.

    TIFF inputs use the maximum depth of cells intersecting the road, with no
    extrapolation beyond those cells. Point-only inputs use the distance cutoff.
    Keep one row per input road in its original order. At equal nearest point
    distances use the largest measured depth, independently of source order.
    Zero distance means exact intersection; GeoPandas max_distance=0 is invalid,
    so apply the inclusive cutoff after the nearest join.
    """
    cutoff = float(max_distance)
    if not np.isfinite(cutoff) or cutoff < 0:
        raise ValueError('Flood distance must be finite and nonnegative')
    if roads.crs is None or not roads.crs.is_projected or roads.crs != hazard.crs:
        raise ValueError('Road flood sampling requires the same projected metric CRS')
    if not all(np.isclose(axis.unit_conversion_factor, 1) for axis in roads.crs.axis_info[:2]):
        raise ValueError('Road flood sampling requires CRS units in metres')
    original_index = roads.index.copy()
    left = roads.drop(columns=['im', 'distance', 'index_intensity'], errors='ignore').reset_index(drop=True)
    right = hazard[['im', 'geometry']].copy()
    right['im'] = pd.to_numeric(right['im'], errors='coerce')
    right = right[np.isfinite(right['im']) & (right['im'] >= 0) &
                  right.geometry.notna() & ~right.geometry.is_empty]
    if left.empty or right.empty:
        left['im'], left['distance'] = 0.0, np.inf
        left.index = original_index
        return left
    right.attrs = hazard.attrs.copy()
    cells = raster_flood_cells(right)
    if cells is not None:
        cells = cells.to_crs(roads.crs)
        joined = gpd.sjoin(left, cells, how='left', rsuffix='intensity', predicate='intersects')
        joined = joined.sort_values('im', ascending=False, kind='stable')
        joined = joined.loc[~joined.index.duplicated()].sort_index()
        joined['distance'] = np.where(joined['im'].notna(), 0.0, np.inf)
        joined['im'] = joined['im'].fillna(0.0)
        joined = joined.drop(columns='index_intensity', errors='ignore')
        joined.index = original_index
        return joined
    joined = gpd.sjoin_nearest(left, right, how='left', rsuffix='intensity', distance_col='distance')
    joined = joined.sort_values(['distance', 'im'], ascending=[True, False], kind='stable')
    joined = joined.loc[~joined.index.duplicated()].sort_index()
    joined.loc[joined['distance'].isna() | (joined['distance'] > cutoff), 'im'] = 0.0
    joined['im'] = joined['im'].fillna(0.0)
    joined = joined.drop(columns='index_intensity', errors='ignore')
    joined.index = original_index
    return joined
