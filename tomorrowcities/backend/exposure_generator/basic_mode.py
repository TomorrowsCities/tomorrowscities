import pandas as pd
import geopandas as gpd

from . import read_geospatial_bytes


URBAN_ATLAS_CLASSES = [
    "Continuous urban fabric (S.L. : > 80%)",
    "Discontinuous dense urban fabric (S.L. : 50% - 80%)",
    "Discontinuous medium density urban fabric (S.L. : 30% - 50%)",
    "Discontinuous low density urban fabric (S.L. : 10% - 30%)",
    "Discontinuous very low density urban fabric (S.L. : < 10%)",
    "Isolated structures",
    "Industrial, commercial, public, military and private units",
    "Fast transit roads and associated land",
    "Other roads and associated land",
    "Railways and associated land",
    "Port areas",
    "Airports",
    "Mineral extraction and dump sites",
    "Construction sites",
    "Land without current use",
    "Green urban areas",
    "Sports and leisure facilities",
    "Arable land (annual crops)",
    "Permanent crops (vineyards, fruit trees, olive groves)",
    "Pastures",
    "Complex and mixed cultivation patterns",
    "Forests",
    "Herbaceous vegetation associations (natural grassland, moors)",
    "Open spaces with little or no vegetation (beaches, dunes, bare rocks, glaciers)",
    "Wetlands",
    "Water",
]


BASIC_MODE_CONFIG = {
    "Kenya": {
        "file": "tomorrowcities/assets/data/distribution_catalogues/kenya_distribution_file.xlsx",
        "density_caps": [200, 150, 100, 50, 30] + [0] * 21,
    },
    "Tanzania": {
        "file": "tomorrowcities/assets/data/distribution_catalogues/tanzania_distribution_file.xlsx",
        "density_caps": [180, 130, 80, 30, 10] + [0] * 21,
    },
    "Turkiye": {
        "file": "tomorrowcities/assets/data/distribution_catalogues/turkiye_distribution_file.xlsx",
        "density_caps": [200, 150, 100, 50, 30] + [0] * 21,
    },
    "Nepal": {
        "file": "tomorrowcities/assets/data/distribution_catalogues/nepal_distribution_file.xlsx",
        "density_caps": [200, 150, 100, 50, 30] + [0] * 21,
    },
    "Bangladesh": {
        "file": "tomorrowcities/assets/data/distribution_catalogues/bangladesh_distribution_file.xlsx",
        "density_caps": [200, 150, 100, 50, 30] + [0] * 21,
    },
}


INCOME_OPTIONS = ["veryLowIncome", "lowIncome", "midIncome", "highIncome", "None"]
RESIDENTIAL_CLASSES = set(URBAN_ATLAS_CLASSES[:5])


def create_basic_mapping_table(landuse_gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    base_df = pd.DataFrame(landuse_gdf.drop(columns="geometry", errors="ignore")).reset_index(drop=True)
    base_df["mapped_luf"] = "Select appropriate class..."
    base_df["mapped_avgincome"] = "Select average income..."
    base_df["mapped_population"] = 0.0
    base_df["mapped_setback"] = 0.0
    return base_df


def normalize_basic_mapping_table(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    non_res_mask = (~df["mapped_luf"].isin(RESIDENTIAL_CLASSES)) & (df["mapped_luf"] != "Select appropriate class...")
    df.loc[non_res_mask, "mapped_avgincome"] = "None"

    res_mask = df["mapped_luf"].isin(RESIDENTIAL_CLASSES) & (df["mapped_avgincome"] == "Select average income...")
    df.loc[res_mask, "mapped_avgincome"] = "midIncome"

    df["mapped_population"] = pd.to_numeric(df["mapped_population"], errors="coerce").fillna(0.0)
    df["mapped_setback"] = pd.to_numeric(df["mapped_setback"], errors="coerce").fillna(0.0)
    return df


def validate_basic_mapping_table(df: pd.DataFrame):
    if (df["mapped_luf"] == "Select appropriate class...").any():
        raise ValueError("One or more rows have no Land Use Type selected.")
    if (df["mapped_avgincome"] == "Select average income...").any():
        raise ValueError("One or more rows have no Average Income selected.")
    invalid_luf = sorted(set(df["mapped_luf"]) - set(URBAN_ATLAS_CLASSES))
    invalid_income = sorted(set(df["mapped_avgincome"]) - set(INCOME_OPTIONS))
    if invalid_luf:
        raise ValueError(f"Invalid land-use values in mapping table: {', '.join(invalid_luf[:5])}")
    if invalid_income:
        raise ValueError(f"Invalid income values in mapping table: {', '.join(invalid_income[:5])}")


def prepare_basic_landuse(file_name: str, file_bytes: bytes, country: str, edited_df: pd.DataFrame) -> gpd.GeoDataFrame:
    validate_basic_mapping_table(edited_df)
    gdf = read_geospatial_bytes(file_name, file_bytes)
    if len(gdf) != len(edited_df):
        raise ValueError("Mapping table row count does not match the uploaded land-use layer.")

    gdf["zoneid"] = range(1, len(gdf) + 1)
    gdf["avgincome"] = edited_df["mapped_avgincome"].values
    gdf["luf"] = edited_df["mapped_luf"].values
    gdf["population"] = pd.to_numeric(edited_df["mapped_population"], errors="coerce").fillna(0)
    gdf["setback"] = pd.to_numeric(edited_df["mapped_setback"], errors="coerce").fillna(0)

    caps = BASIC_MODE_CONFIG[country]["density_caps"]
    luf_to_cap = dict(zip(URBAN_ATLAS_CLASSES, caps))
    gdf["densitycap"] = gdf["luf"].map(luf_to_cap).fillna(0)
    return gdf
