import React, { useState } from 'react';
import {
  Box,
  Typography,
  ToggleButton,
  ToggleButtonGroup,
  Grid,
  Tooltip
} from '@mui/material';
import { DataGrid, GridColDef } from '@mui/x-data-grid';
import { useAppState } from '../contexts/AppStateContext';

const MapInfoPanel: React.FC = () => {
  const { state } = useAppState();
  const [viewMode, setViewMode] = useState<'summary' | 'detail'>('summary');

  const handleViewModeChange = (
    event: React.MouseEvent<HTMLElement>,
    newMode: 'summary' | 'detail' | null,
  ) => {
    if (newMode !== null) {
      setViewMode(newMode);
    }
  };

  const renderSummaryView = () => {
    return (
      <Grid container spacing={1}>
        {Object.entries(state.layers).map(([layerName, layer]) => {
          const data = layer.data;
          let count = 0;
          
          if (data) {
            if (Array.isArray(data)) {
              count = data.length;
            } else if (data.type === 'FeatureCollection' && data.features) {
              count = data.features.length;
            } else if (typeof data === 'object') {
              count = Object.keys(data).length;
            }
          }

          return (
            <React.Fragment key={layerName}>
              <Grid item xs={6}>
                <Tooltip title={layer.mapInfoTooltip}>
                  <Typography variant="body2">
                    {layerName}
                  </Typography>
                </Tooltip>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="body2" align="right">
                  {count}
                </Typography>
              </Grid>
            </React.Fragment>
          );
        })}
      </Grid>
    );
  };

  const renderDetailView = () => {
    const selectedLayer = Object.entries(state.layers).find(([_, layer]) => layer.data);
    if (!selectedLayer) {
      return <Typography>No data available</Typography>;
    }

    const [layerName, layer] = selectedLayer;
    const data = layer.data;
    
    if (!data) {
      return <Typography>No data available for {layerName}</Typography>;
    }

    let rows: any[] = [];
    let columns: GridColDef[] = [];

    if (data.type === 'FeatureCollection' && data.features) {
      rows = data.features.map((feature: any, index: number) => ({
        id: index,
        ...feature.properties,
        geometry_type: feature.geometry?.type || 'N/A'
      }));
      
      if (rows.length > 0) {
        columns = Object.keys(rows[0])
          .filter(key => key !== 'id')
          .map(key => ({
            field: key,
            headerName: key.charAt(0).toUpperCase() + key.slice(1),
            width: 150,
            flex: 1
          }));
      }
    } else if (Array.isArray(data)) {
      rows = data.map((item: any, index: number) => ({
        id: index,
        ...item
      }));
      
      if (rows.length > 0) {
        columns = Object.keys(rows[0])
          .filter(key => key !== 'id')
          .map(key => ({
            field: key,
            headerName: key.charAt(0).toUpperCase() + key.slice(1),
            width: 150,
            flex: 1
          }));
      }
    }

    return (
      <Box sx={{ height: 400, width: '100%' }}>
        <Typography variant="h6" gutterBottom>
          {layerName.charAt(0).toUpperCase() + layerName.slice(1)} Data
        </Typography>
        <DataGrid
          rows={rows}
          columns={columns}
          pageSize={10}
          rowsPerPageOptions={[5, 10, 20]}
          disableSelectionOnClick
          sx={{ mt: 1 }}
        />
      </Box>
    );
  };

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
        <Typography variant="body2">
          Engine [v{state.version}]
        </Typography>
      </Box>
      
      <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
        <ToggleButtonGroup
          value={viewMode}
          exclusive
          onChange={handleViewModeChange}
          size="small"
        >
          <ToggleButton value="summary">Summary</ToggleButton>
          <ToggleButton value="detail">Detail</ToggleButton>
        </ToggleButtonGroup>
      </Box>

      {viewMode === 'summary' ? renderSummaryView() : renderDetailView()}
    </Box>
  );
};

export default MapInfoPanel;
