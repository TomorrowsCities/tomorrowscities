import React, { useState } from 'react';
import {
  Card,
  CardContent,
  Typography,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Checkbox,
  FormControlLabel,
  Alert,
  CircularProgress,
  Box,
  FormGroup,
  SelectChangeEvent
} from '@mui/material';
import { useAppState } from '../contexts/AppStateContext';
import { executeSimulation } from '../services/api';

const ExecutePanel: React.FC = () => {
  const { state, dispatch } = useAppState();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleExecute = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const result = await executeSimulation({
        layers: state.layers,
        hazard: state.hazard,
        infra: state.infra,
        policies: state.selectedPolicies,
        parameters: {}
      });
      
      dispatch({ type: 'INCREMENT_RENDER_COUNT' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Simulation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    dispatch({ type: 'RESET_SESSION' });
  };

  const isReadyToRun = () => {
    return state.layers.building?.data && state.layers.household?.data;
  };

  const handleHazardChange = (event: SelectChangeEvent) => {
    dispatch({ type: 'SET_HAZARD', payload: event.target.value });
  };

  const handleInfraChange = (event: SelectChangeEvent<string[]>) => {
    const value = event.target.value;
    dispatch({ type: 'SET_INFRA', payload: typeof value === 'string' ? value.split(',') : value });
  };

  const handlePolicyChange = (policyId: number) => (event: React.ChangeEvent<HTMLInputElement>) => {
    const newPolicies = event.target.checked
      ? [...state.selectedPolicies, policyId]
      : state.selectedPolicies.filter(id => id !== policyId);
    dispatch({ type: 'SET_SELECTED_POLICIES', payload: newPolicies });
  };

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Simulation Settings
        </Typography>
        
        <FormControl fullWidth margin="normal">
          <InputLabel>Hazard Type</InputLabel>
          <Select
            value={state.hazard}
            onChange={handleHazardChange}
            label="Hazard Type"
          >
            {state.hazardList.map((hazard) => (
              <MenuItem key={hazard} value={hazard}>
                {hazard.charAt(0).toUpperCase() + hazard.slice(1)}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <FormControl fullWidth margin="normal">
          <InputLabel>Infrastructure</InputLabel>
          <Select
            multiple
            value={state.infra}
            onChange={handleInfraChange}
            label="Infrastructure"
          >
            <MenuItem value="building">Building</MenuItem>
            <MenuItem value="power">Power</MenuItem>
            <MenuItem value="road">Road</MenuItem>
          </Select>
        </FormControl>

        <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
          Policies
        </Typography>
        <FormGroup>
          {Object.values(state.policies).map((policy: any) => (
            <FormControlLabel
              key={policy.id}
              control={
                <Checkbox
                  checked={state.selectedPolicies.includes(policy.id)}
                  onChange={handlePolicyChange(policy.id)}
                />
              }
              label={`${policy.label}: ${policy.description}`}
            />
          ))}
        </FormGroup>

        {error && (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        )}

        <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
          <Button
            variant="contained"
            onClick={handleExecute}
            disabled={!isReadyToRun() || loading}
            fullWidth
          >
            {loading ? <CircularProgress size={24} /> : 'Execute Simulation'}
          </Button>
          <Button
            variant="outlined"
            onClick={handleReset}
            disabled={loading}
          >
            Reset
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
};

export default ExecutePanel;
