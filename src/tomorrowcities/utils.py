import io
import fiona
import geopandas as gpd

def read_zipshp(file):
  zipshp = io.BytesIO(open(file, 'rb').read())
  with fiona.BytesCollection(zipshp.read()) as src:
    crs = src.crs
    gdf = gpd.GeoDataFrame.from_features(src, crs=crs)
  return gdf