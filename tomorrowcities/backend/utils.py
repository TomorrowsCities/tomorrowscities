import pandas as pd
import geopandas as gpd

def inject_columns(df, extra_cols):
    if  isinstance(df, gpd.GeoDataFrame) or isinstance(df, pd.DataFrame):
        for col, val in extra_cols.items():
            df[col] = val
    return df

def building_preprocess(df, extra_cols):
    df['occupancy'] = df['expstr'].apply(lambda x: x.split('+')[-1]).astype('category')
    df['storeys'] = df['expstr'].apply(lambda x: x.split('+')[-2])
    df['code_level'] = df['expstr'].apply(lambda x: x.split('+')[-3]).astype('category')
    df['material'] = df['expstr'].apply(lambda x: "+".join(x.split('+')[:-3])).astype('category')

    df = inject_columns(df, extra_cols)

    return df

def identity_preprocess(df, extra_cols):
    df = inject_columns(df, extra_cols)
    return df

class ParameterFile:
    def __init__(self, content: bytes):
        self.df_nc = pd.read_excel(content,sheet_name=1,header=None)
        self.ipdf = pd.read_excel(content,sheet_name=2, header=None)
        self.df1 = pd.read_excel(content,sheet_name=3, header=None)
        self.df2 = pd.read_excel(content,sheet_name=4, header=None)
        self.df3 = pd.read_excel(content,sheet_name=5, header=None)

    def get_sheets(self):
        return (self.df_nc, self.ipdf, self.df1, self.df2, self.df3)