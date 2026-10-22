"""Bounded map previews coloured by intensity, independently of point density."""

import base64
from html import escape
from io import BytesIO
import json

import ipyleaflet
import numpy as np
import pandas as pd
from PIL import Image
from pyproj import Transformer
from scipy.spatial import cKDTree


EARTHQUAKE_COLORS = ("#ffffcc", "#ffeda0", "#fed976", "#feb24c",
                     "#fd8d3c", "#fc4e2a", "#e31a1c", "#b10026")
FLOOD_COLORS = ("#deebf7", "#c6dbef", "#9ecae1", "#6baed6",
                "#4292c6", "#2171b5", "#08519c", "#08306b")
MAX_PREVIEW_SIDE = 2048


def intensity_palette(hazard):
    if hazard == "flood":
        return FLOOD_COLORS, "Light blue → dark blue"
    return EARTHQUAKE_COLORS, "Yellow → orange → dark red"


def intensity_scale(hazard, earthquake_unit, maximum):
    if hazard == "flood":
        return "Flood depth (m)", np.array([0, .25, .5, 1, 2, 4, 8, 16]), True
    if hazard == "earthquake":
        bounds = np.array([0, .025, .05, .1, .2, .4, .8, 1.6])
        if earthquake_unit != "g":
            bounds *= 9.81
        unit = "g" if earthquake_unit == "g" else "m/s²"
        return f"Ground acceleration ({unit})", bounds, True
    return "Intensity (input units)", np.linspace(0, maximum, len(EARTHQUAKE_COLORS) + 1)[:-1], False


def intensity_color_indices(values, bounds):
    # A threshold belongs to the lighter interval; the final colour is open-ended.
    return np.searchsorted(bounds[1:], values, side="left")


def intensity_legend_html(title, bounds, open_ended, maximum, colors, direction):
    rows = []
    for index, color in enumerate(colors):
        low = bounds[index]
        last = index == len(colors) - 1
        high = maximum if last else bounds[index + 1]
        label = (f"> {low:g}" if last and open_ended
                 else f"{'>' if index == 0 else ''}{low:g} – {high:g}")
        rows.append(
            f'<div style="display:flex;align-items:center;gap:6px;margin:3px 0">'
            f'<span style="width:22px;height:13px;background:{color};'
            f'border:1px solid #999;flex-shrink:0"></span><span>{label}</span></div>'
        )
    return (
        '<div style="font-size:12px;line-height:1.4;margin-bottom:10px">'
        f'<strong>{escape(title)}</strong>' + ''.join(rows) +
        f'<div style="margin-top:5px">{escape(direction)}: increasing intensity.</div>'
        '<div>Zero / no data: transparent.</div>'
        '<div>Preview: maximum value per display cell.</div></div>'
    )


def create_intensity_layer(df, click_handler, hazard, earthquake_unit="m/s2", name="intensity"):
    """Rasterise a display copy; retain original values and geometry for analysis."""
    column = "pga" if "pga" in df.columns else "im"
    values = pd.to_numeric(df[column], errors="coerce").to_numpy(dtype=float, na_value=np.nan)
    valid = np.isfinite(values) & (values > 0) & df.geometry.geom_type.eq("Point").to_numpy()
    positions = np.flatnonzero(valid)
    layer = ipyleaflet.LayerGroup(layers=(), name=name, bottom=False)
    layer.intensity_legend_html = ""
    if not len(positions):
        return layer

    geometry = df.geometry.iloc[positions]
    to_mercator = Transformer.from_crs(df.crs or 4326, 3857, always_xy=True)
    x, y = to_mercator.transform(geometry.x.to_numpy(), geometry.y.to_numpy())
    x, y = np.asarray(x), np.asarray(y)
    valid_xy = np.isfinite(x) & np.isfinite(y) & (np.abs(y) <= 20037508.35)
    x, y = x[valid_xy], y[valid_xy]
    values = values[positions][valid_xy]
    positions = positions[valid_xy]
    if not len(values):
        return layer

    # Estimate a display cell from nearby source points, using bounded workspace.
    points = np.column_stack((x[:30000], y[:30000]))
    if len(points) > 1:
        distances = cKDTree(points).query(points, k=2)[0][:, 1]
        distances = distances[distances > 1e-6]
    else:
        distances = np.array([])
    native_size = float(np.median(distances)) if len(distances) else 100.0
    unique_x, unique_y = np.unique(points[:, 0]), np.unique(points[:, 1])
    regular_grid = len(unique_x) * len(unique_y) <= len(points) * 4
    cell_x = float(np.median(np.diff(unique_x))) if regular_grid and len(unique_x) > 1 else native_size
    cell_y = float(np.median(np.diff(unique_y))) if regular_grid and len(unique_y) > 1 else native_size
    left, right = float(x.min() - cell_x / 2), float(x.max() + cell_x / 2)
    bottom, top = float(y.min() - cell_y / 2), float(y.max() + cell_y / 2)
    width = max(1, min(MAX_PREVIEW_SIDE, int(round((right - left) / cell_x))))
    height = max(1, min(MAX_PREVIEW_SIDE, int(round((top - bottom) / cell_y))))
    cols = np.clip(((x - left) / (right - left) * width).astype(int), 0, width - 1)
    rows = np.clip(((top - y) / (top - bottom) * height).astype(int), 0, height - 1)
    grid = np.zeros((height, width), dtype=float)
    np.maximum.at(grid, (rows, cols), values)

    title, bounds, open_ended = intensity_scale(hazard, earthquake_unit, float(values.max()))
    colors, direction = intensity_palette(hazard)
    palette = np.array([tuple(bytes.fromhex(color[1:])) for color in colors], dtype=np.uint8)
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    wet = grid > 0
    rgba[wet, :3] = palette[intensity_color_indices(grid[wet], bounds)]
    rgba[wet, 3] = 255
    stream = BytesIO()
    Image.fromarray(rgba).save(stream, format="PNG")
    to_lonlat = Transformer.from_crs(3857, 4326, always_xy=True)
    west, south = to_lonlat.transform(left, bottom)
    east, north = to_lonlat.transform(right, top)
    preview = ipyleaflet.ImageOverlay(
        url="data:image/png;base64," + base64.b64encode(stream.getvalue()).decode("ascii"),
        bounds=((south, west), (north, east)), opacity=1,
        name=name, pane="intensityPane", options=["pane"], bottom=False,
    )

    # Keep the existing lightweight click targets; invisible until hovered.
    if len(positions) > 5000:
        positions = positions[np.linspace(0, len(positions) - 1, 5000, dtype=int)]
    clickable = df.iloc[positions]
    if clickable.crs is not None:
        clickable = clickable.to_crs(4326)
    info = ipyleaflet.GeoJSON(
        data=json.loads(clickable.to_json()), name=f"{name}-info",
        pane="intensityPane", options=["pane"], bottom=False,
        point_style={"radius": 5, "opacity": 0, "fillOpacity": 0, "weight": 0},
        style={"opacity": 0, "fillOpacity": 0, "weight": 0},
        hover_style={"opacity": 1, "fillOpacity": .15, "weight": 2, "color": "#ffffff"},
    )
    info.on_click(click_handler)
    layer.layers = (preview, info)
    layer.intensity_legend_html = intensity_legend_html(
        title, bounds, open_ended, float(values.max()), colors, direction,
    )
    return layer
