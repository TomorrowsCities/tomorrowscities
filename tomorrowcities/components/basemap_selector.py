"""One active tile layer, with a separate checkbox-style radio selector."""

import ipyleaflet
import solara
from solara.alias import rv
from xyzservices import TileProvider


def _esri_gray_canvas(tone):
    # ResourceURL from the service's WMTS GetCapabilities (EPSG:3857).
    service = f"World_{tone}_Gray_Base"
    return TileProvider(
        name=f"Esri.{tone}GrayCanvas",
        url=("https://services.arcgisonline.com/arcgis/rest/services/Canvas/"
             f"{service}/MapServer/WMTS/tile/1.0.0/Canvas_{service}/"
             "default/GoogleMapsCompatible/{z}/{y}/{x}"),
        max_zoom=16,
        attribution="Esri, HERE, Garmin, (c) OpenStreetMap contributors, and the GIS user community",
        html_attribution=(
            'Tiles &copy; <a href="https://www.esri.com/">Esri</a>, HERE, Garmin, '
            '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> '
            'contributors, and the GIS user community'
        ),
    )


BASEMAPS = {
    "OpenStreetMap": ipyleaflet.basemaps.OpenStreetMap.Mapnik,
    "OpenTopoMap": ipyleaflet.basemaps.OpenTopoMap,
    "Esri WorldStreetMap": ipyleaflet.basemaps.Esri.WorldStreetMap,
    "Esri WorldImagery": ipyleaflet.basemaps.Esri.WorldImagery,
    "Esri Light Gray": _esri_gray_canvas("Light"),
    "Esri Dark Gray": _esri_gray_canvas("Dark"),
}
DEFAULT_BASEMAP = "OpenStreetMap"


def create_basemap_layer(name):
    provider = BASEMAPS[name]
    return ipyleaflet.TileLayer.element(
        url=provider.build_url(), name=name, base=True,
        attribution=provider.html_attribution,
        max_native_zoom=provider.get("max_zoom", 18), max_zoom=23,
    )


@solara.component
def BasemapSelector(value, on_value):
    def select(name):
        if name in BASEMAPS:
            on_value(name)

    with solara.Div(style={"width": "210px", "max-width": "60vw"}):
        solara.Style("""
        /* The native control remains responsible for data overlays only. */
        .tc-single-basemap .leaflet-control-layers-base,
        .tc-single-basemap .leaflet-control-layers-separator {
            display: none;
        }
        .tc-basemap-options {
            max-height: 32vh;
            overflow-y: auto;
            padding: 8px 2px 4px;
        }
        .tc-basemap-options .v-radio {
            min-height: 28px;
            margin-bottom: 4px !important;
        }
        .tc-basemap-options .v-label {
            font-size: 13px;
        }
        """)
        with solara.Details(summary="Basemaps", expand=False):
            # A mandatory radio group prevents clearing the active choice;
            # square icons provide the requested checkbox appearance.
            with solara.Div(classes=["tc-basemap-options"]):
                with rv.RadioGroup(v_model=value, on_v_model=select, mandatory=True,
                                   dense=True, hide_details=True, class_="ma-0 pa-0"):
                    for name in BASEMAPS:
                        rv.Radio(label=name, value=name,
                                 off_icon="mdi-checkbox-blank-outline",
                                 on_icon="mdi-checkbox-marked")
