import io
from io import BytesIO
import pandas as pd
import geopandas as gpd
import fiona
import numpy as np
import random

def read_zipshp(file):
    zipshp = io.BytesIO(file.read())
    with fiona.BytesCollection(zipshp.read()) as src:
        crs = src.crs
        gdf = gpd.GeoDataFrame.from_features(src, crs=crs)
    return gdf

def dist2vector(d_value, d_number, d_limit, shuffle_or_not):
    x = np.squeeze(d_value)
    w = np.squeeze(d_number)
    n = d_limit
    reps = np.round(w).astype('int32')
    
    if reps.size > 1:
        # Prevent negative reps[-1] caused by rounding if the sum of other elements exceeds n.
        diff = n - np.sum(reps)
        if diff != 0:
            # We need to adjust reps so that sum(reps) == n and all reps >= 0.
            # Convert to list of mutable integers
            reps_list = reps.tolist()
            
            if diff > 0:
                # Need to add 'diff' total counts. Give to the largest bins first.
                for _ in range(diff):
                    idx = np.argmax(reps_list)
                    reps_list[idx] += 1
            else:
                # Need to subtract 'abs(diff)' total counts. Subtract from largest bins first to avoid < 0
                for _ in range(abs(diff)):
                    # Get index of maximum value that is > 0
                    valid_indices = [i for i, v in enumerate(reps_list) if v > 0]
                    if not valid_indices:
                        break # Cannot reduce further
                    idx = max(valid_indices, key=lambda i: reps_list[i])
                    reps_list[idx] -= 1
                    
            reps = np.array(reps_list, dtype='int32')
    else:
        reps = np.array([n])
        
    y = np.repeat(x, reps)
    if shuffle_or_not == 'shuffle':
        random.shuffle(y)
    #return [str(element) for element in y]
    # Fix: sayısalsa çıktı sayısal kalır (eduAttStat, age, gender vb.), x zaten string ise çıktı yine string olur (lrs_types, avg_income_types vb.)
    return list(y)

# Function to save shapefile and zip it for download
def save_shapefile_with_bytesio(dataframe, directory):
    dataframe.to_file(f"{directory}/Exposure_Building.shp", driver='ESRI:Shapefile')
    zipObj = ZipFile(f"{directory}/Exposure_Building_zip.zip", 'w')
    zipObj.write(f"{directory}/Exposure_Building.shp", arcname='Exposure_Building.shp')
    zipObj.write(f"{directory}/Exposure_Building.cpg", arcname='Exposure_Building.cpg')
    zipObj.write(f"{directory}/Exposure_Building.dbf", arcname='Exposure_Building.dbf')
    zipObj.write(f"{directory}/Exposure_Building.prj", arcname='Exposure_Building.prj')
    zipObj.write(f"{directory}/Exposure_Building.shx", arcname='Exposure_Building.shx')
    zipObj.close()

# Function to convert DataFrame to Excel for download
def to_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Sheet1')
    writer.close()
    processed_data = output.getvalue()
    return processed_data