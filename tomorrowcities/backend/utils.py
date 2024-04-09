import pandas as pd
import geopandas as gpd
import xml
import numpy as np

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
    

def getText(node):
    nodelist = node.childNodes
    rc = []
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc.append(node.data)
    return ''.join(rc)


def read_gem_xml_vulnerability(dom):
    d = dict()
    node = dom.getElementsByTagName('vulnerabilityModel')[0]
    for i in range(node.attributes.length):
        d[node.attributes.item(i).name] = node.attributes.item(i).value 

    d['description'] = getText(dom.getElementsByTagName('description')[0])
    d['vulnerabilityFunctions'] = []
    for node in dom.getElementsByTagName('vulnerabilityFunction'):
        v = dict()
        for i in range(node.attributes.length):
            v[node.attributes.item(i).name] = node.attributes.item(i).value 
        imls = node.getElementsByTagName('imls')[0]
        v['imt'] = imls.getAttribute('imt')
        v['imls'] = np.fromstring(getText(imls),dtype=float, sep=' ')
        v['meanLRs'] = np.fromstring(getText(node.getElementsByTagName('meanLRs')[0]),dtype=float, sep=' ')
        v['covLRs'] = np.fromstring(getText(node.getElementsByTagName('covLRs')[0]),dtype=float, sep=' ')
        d['vulnerabilityFunctions'].append(v)
    return d


def read_gem_xml_fragility(dom):
    d = dict()
    node = dom.getElementsByTagName('fragilityModel')[0]
    for i in range(node.attributes.length):
        d[node.attributes.item(i).name] = node.attributes.item(i).value 

    d['description'] = getText(dom.getElementsByTagName('description')[0])
    d['fragilityFunctions'] = []
    for node in dom.getElementsByTagName('fragilityFunction'):
        v = dict()
        for i in range(node.attributes.length):
            v[node.attributes.item(i).name] = node.attributes.item(i).value 
        imls = node.getElementsByTagName('imls')[0]
        v['imt'] = imls.getAttribute('imt')
        v['noDamageLimit'] = imls.getAttribute('noDamageLimit')
        v['imls'] = np.fromstring(getText(imls),dtype=float, sep=' ')

         
        for poesnode in node.getElementsByTagName('poes'):
            poedict = dict()
            for i in range(poesnode.attributes.length):
                poedict[poesnode.attributes.item(i).name] = poesnode.attributes.item(i).value 
            poedict['data'] = np.fromstring(getText(poesnode),dtype=float, sep=' ')
            v[poedict['ls']] = poedict['data']
        d['fragilityFunctions'].append(v)
    return d


def read_gem_xml(data: [bytes]):
    content_as_string = data.decode('utf-8')
    content_as_string = content_as_string.replace('\n','')
    dom = xml.dom.minidom.parseString(content_as_string)
    d = dict()
    if len(dom.getElementsByTagName('vulnerabilityModel')) > 0:
        d = read_gem_xml_vulnerability(dom)
    elif len(dom.getElementsByTagName('fragilityModel')) > 0:
        d = read_gem_xml_fragility(dom)
    return d