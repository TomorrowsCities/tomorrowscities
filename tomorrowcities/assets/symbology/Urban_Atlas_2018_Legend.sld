<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld"
    xmlns:se="http://www.opengis.net/se"
    xmlns:ogc="http://www.opengis.net/ogc"
    xmlns:xlink="http://www.w3.org/1999/xlink"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    version="1.1.0"
    xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.1.0/StyledLayerDescriptor.xsd">
  <NamedLayer>
    <se:Name>Urban_Atlas_2018_Legend</se:Name>
    <UserStyle>
      <se:Name>Urban Atlas 2018 Legend</se:Name>
      <se:Description>
        <se:Title>Urban Atlas 2018 LCLU classes</se:Title>
        <se:Abstract>Converted from the uploaded ArcGIS .lyr legend. Rules symbolize polygons by the code_2018 attribute.</se:Abstract>
      </se:Description>
      <se:FeatureTypeStyle>
      <se:Rule>
        <se:Name>11100</se:Name>
        <se:Description>
          <se:Title>11100: Continuous Urban fabric (S.L. &gt; 80%)</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>11100</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#800000</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>11210</se:Name>
        <se:Description>
          <se:Title>11210: Discontinuous Dense Urban Fabric (S.L.: 50% - 80%)</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>11210</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#BF0000</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>11220</se:Name>
        <se:Description>
          <se:Title>11220: Discontinuous Medium Density Urban Fabric (S.L.: 30% - 50%)</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>11220</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#FF4040</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>11230</se:Name>
        <se:Description>
          <se:Title>11230: Discontinuous Low Density Urban Fabric (S.L.: 10% - 30%)</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>11230</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#FF8080</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>11240</se:Name>
        <se:Description>
          <se:Title>11240: Discontinuous very low density urban fabric (S.L. &lt; 10%)</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>11240</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#FFBFBF</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>11300</se:Name>
        <se:Description>
          <se:Title>11300: Isolated Structures</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>11300</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#CC6666</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>12100</se:Name>
        <se:Description>
          <se:Title>12100: Industrial, commercial, public, military and private units</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>12100</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#CC4DF2</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>12210</se:Name>
        <se:Description>
          <se:Title>12210: Fast transit roads and associated land</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>12210</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#959595</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>12220</se:Name>
        <se:Description>
          <se:Title>12220: Other roads and associated land</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>12220</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#B3B3B3</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>12230</se:Name>
        <se:Description>
          <se:Title>12230: Railways and associated land</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>12230</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#595959</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>12300</se:Name>
        <se:Description>
          <se:Title>12300: Port areas</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>12300</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#E6CCCC</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>12400</se:Name>
        <se:Description>
          <se:Title>12400: Airports</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>12400</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#E6CCE6</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>13100</se:Name>
        <se:Description>
          <se:Title>13100: Mineral extraction and dump sites</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>13100</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#734D37</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>13300</se:Name>
        <se:Description>
          <se:Title>13300: Construction sites</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>13300</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#B9A56E</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>13400</se:Name>
        <se:Description>
          <se:Title>13400: Land without current use</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>13400</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#874545</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>14100</se:Name>
        <se:Description>
          <se:Title>14100: Green urban areas</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>14100</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#8CDC00</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>14200</se:Name>
        <se:Description>
          <se:Title>14200: Sports and leisure facilities</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>14200</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#AFD2A5</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>21000</se:Name>
        <se:Description>
          <se:Title>21000: Arable land (annual crops)</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>21000</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#FFFFA8</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>22000</se:Name>
        <se:Description>
          <se:Title>22000: Permanent crops</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>22000</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#F2A64D</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>23000</se:Name>
        <se:Description>
          <se:Title>23000: Pastures</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>23000</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#E6E64D</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>24000</se:Name>
        <se:Description>
          <se:Title>24000: Complex and mixed cultivation patterns</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>24000</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#FFE64D</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>25000</se:Name>
        <se:Description>
          <se:Title>25000: Orchards</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>25000</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#F2CC80</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>31000</se:Name>
        <se:Description>
          <se:Title>31000: Forests</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>31000</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#008C00</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>32000</se:Name>
        <se:Description>
          <se:Title>32000: Herbaceous vegetation associations</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>32000</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#CCF24D</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>33000</se:Name>
        <se:Description>
          <se:Title>33000: Open spaces with little or no vegetations</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>33000</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#CCFFCC</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>40000</se:Name>
        <se:Description>
          <se:Title>40000: Wetlands</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>40000</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#A6A6FF</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      <se:Rule>
        <se:Name>50000</se:Name>
        <se:Description>
          <se:Title>50000: Water</se:Title>
        </se:Description>
        <ogc:Filter>
          <ogc:PropertyIsEqualTo>
            <ogc:PropertyName>code_2018</ogc:PropertyName>
            <ogc:Literal>50000</ogc:Literal>
          </ogc:PropertyIsEqualTo>
        </ogc:Filter>
        <se:PolygonSymbolizer>
          <se:Fill>
            <se:SvgParameter name="fill">#80F2E6</se:SvgParameter>
          </se:Fill>
          <se:Stroke>
            <se:SvgParameter name="stroke">#666666</se:SvgParameter>
            <se:SvgParameter name="stroke-width">0.1</se:SvgParameter>
          </se:Stroke>
        </se:PolygonSymbolizer>
      </se:Rule>
      </se:FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>
