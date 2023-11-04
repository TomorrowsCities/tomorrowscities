def building_preprocess(df):
    df['occupancy'] = df['expstr'].apply(lambda x: x.split('+')[-1]).astype('category')
    df['storeys'] = df['expstr'].apply(lambda x: x.split('+')[-2])
    df['code_level'] = df['expstr'].apply(lambda x: x.split('+')[-3]).astype('category')
    df['material'] = df['expstr'].apply(lambda x: "+".join(x.split('+')[:-3])).astype('category')
    return df

def identity_preprocess(df):
    return df