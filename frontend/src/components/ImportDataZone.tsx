import React, { useState } from 'react';
import {
  Box,
  Typography,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Button,
  Alert
} from '@mui/material';
import { ExpandMore } from '@mui/icons-material';
import { useAppState } from '../contexts/AppStateContext';
import FileDropZone from './FileDropZone';

const ImportDataZone: React.FC = () => {
  const { state, dispatch } = useAppState();
  const [selectedLayer, setSelectedLayer] = useState('building');
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);

  const handleFileUpload = (data: any, fileName: string) => {
    try {
      dispatch({
        type: 'SET_LAYER_DATA',
        payload: {
          layerName: selectedLayer,
          data: data
        }
      });
      setUploadStatus(`Successfully uploaded ${fileName} to ${selectedLayer} layer`);
      dispatch({ type: 'INCREMENT_RENDER_COUNT' });
    } catch (error) {
      setUploadStatus(`Failed to upload ${fileName}: ${error}`);
    }
  };

  const generateSampleData = () => {
    const sampleBuildings = {
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: {
            bldid: 1,
            residents: 4,
            fptarea: 100,
            repvalue: 50000,
            nhouse: 1,
            zoneid: 1,
            expstr: 'MR/LWAL+DNO/H1-2',
            specialfac: 0
          },
          geometry: {
            type: 'Point',
            coordinates: [28.98, 41.01]
          }
        },
        {
          type: 'Feature',
          properties: {
            bldid: 2,
            residents: 6,
            fptarea: 150,
            repvalue: 75000,
            nhouse: 1,
            zoneid: 1,
            expstr: 'CR/LWAL+DNO/H1-3',
            specialfac: 0
          },
          geometry: {
            type: 'Point',
            coordinates: [28.985, 41.015]
          }
        }
      ]
    };

    dispatch({
      type: 'SET_LAYER_DATA',
      payload: {
        layerName: 'building',
        data: sampleBuildings
      }
    });

    const sampleHouseholds = [
      { hhid: 1, nind: 4, income: 'medium', bldid: 1, commfacid: 1 },
      { hhid: 2, nind: 6, income: 'high', bldid: 2, commfacid: 1 }
    ];

    dispatch({
      type: 'SET_LAYER_DATA',
      payload: {
        layerName: 'household',
        data: sampleHouseholds
      }
    });

    setUploadStatus('Sample data generated successfully');
    dispatch({ type: 'INCREMENT_RENDER_COUNT' });
  };

  return (
    <Box>
      <Accordion defaultExpanded>
        <AccordionSummary expandIcon={<ExpandMore />}>
          <Typography variant="h6">Upload Data</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <FormControl fullWidth margin="normal">
            <InputLabel>Layer Type</InputLabel>
            <Select
              value={selectedLayer}
              onChange={(e) => setSelectedLayer(e.target.value)}
              label="Layer Type"
            >
              {Object.keys(state.layers).map((layerName) => (
                <MenuItem key={layerName} value={layerName}>
                  {layerName.charAt(0).toUpperCase() + layerName.slice(1)}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FileDropZone
            onFileUpload={handleFileUpload}
            multiple={false}
          />

          {uploadStatus && (
            <Alert 
              severity={uploadStatus.includes('Failed') ? 'error' : 'success'}
              sx={{ mt: 1 }}
            >
              {uploadStatus}
            </Alert>
          )}
        </AccordionDetails>
      </Accordion>

      <Accordion>
        <AccordionSummary expandIcon={<ExpandMore />}>
          <Typography variant="h6">Generate Data</Typography>
        </AccordionSummary>
        <AccordionDetails>
          <Typography variant="body2" gutterBottom>
            Generate sample data for testing the application
          </Typography>
          <Button
            variant="contained"
            onClick={generateSampleData}
            fullWidth
          >
            Generate Sample Data
          </Button>
        </AccordionDetails>
      </Accordion>
    </Box>
  );
};

export default ImportDataZone;
