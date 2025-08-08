import React, { useEffect, useState } from 'react';
import { MapContainer, TileLayer, GeoJSON, useMap } from 'react-leaflet';
import { Box } from '@mui/material';
import { useAppState } from '../contexts/AppStateContext';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';

delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

const MapViewer: React.FC = () => {
  const { state, dispatch } = useAppState();
  const [mapLayers, setMapLayers] = useState<any[]>([]);

  const createMapLayers = () => {
    const layers: any[] = [];
    Object.entries(state.layers).forEach(([layerName, layer]) => {
      if (layer.data && typeof layer.data === 'object') {
        let geoJsonData;
        
        if (layer.data.type === 'FeatureCollection') {
          geoJsonData = layer.data;
        } else if (layer.data.features) {
          geoJsonData = {
            type: 'FeatureCollection',
            features: layer.data.features
          };
        } else if (Array.isArray(layer.data)) {
          geoJsonData = {
            type: 'FeatureCollection',
            features: layer.data.map((item: any) => ({
              type: 'Feature',
              properties: item.properties || item,
              geometry: item.geometry || null
            }))
          };
        } else {
          return;
        }
        
        layers.push({
          name: layerName,
          data: geoJsonData,
          style: getLayerStyle(layerName)
        });
      }
    });
    setMapLayers(layers);
  };

  const getLayerStyle = (layerName: string) => {
    switch (layerName) {
      case 'building':
        return {
          color: '#ff7800',
          weight: 1,
          opacity: 1,
          fillOpacity: 0.7
        };
      case 'landuse':
        return {
          color: '#00ff00',
          weight: 1,
          opacity: 1,
          fillOpacity: 0.5
        };
      case 'intensity':
        return {
          color: '#ff0000',
          weight: 1,
          opacity: 0.8,
          fillOpacity: 0.6
        };
      default:
        return {
          color: '#3388ff',
          weight: 1,
          opacity: 1,
          fillOpacity: 0.6
        };
    }
  };

  useEffect(() => {
    createMapLayers();
  }, [state.layers, state.renderCount]);

  const MapEvents = () => {
    const map = useMap();
    
    useEffect(() => {
      const handleMoveEnd = () => {
        const bounds = map.getBounds();
        dispatch({
          type: 'SET_BOUNDS',
          payload: [[bounds.getSouth(), bounds.getWest()], [bounds.getNorth(), bounds.getEast()]]
        });
      };

      map.on('moveend', handleMoveEnd);
      return () => {
        map.off('moveend', handleMoveEnd);
      };
    }, [map]);

    return null;
  };

  return (
    <Box sx={{ height: '55vh', width: '100%' }}>
      <MapContainer
        center={state.center}
        zoom={14}
        style={{ height: '100%', width: '100%' }}
      >
        <TileLayer
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        />
        {mapLayers.map((layer, index) => (
          <GeoJSON
            key={`${layer.name}-${index}-${state.renderCount}`}
            data={layer.data}
            style={layer.style}
          />
        ))}
        <MapEvents />
      </MapContainer>
    </Box>
  );
};

export default MapViewer;
