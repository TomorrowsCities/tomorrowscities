import React from 'react';
import {
  Card,
  CardContent,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Box,
  OutlinedInput
} from '@mui/material';
import { useAppState } from '../contexts/AppStateContext';

const FilterPanel: React.FC = () => {
  const { state } = useAppState();

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          Data Filters
        </Typography>
        
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Filter data layers to focus on specific subsets
        </Typography>

        <FormControl fullWidth margin="normal">
          <InputLabel>Building Filters</InputLabel>
          <Select
            multiple
            value={[]}
            input={<OutlinedInput label="Building Filters" />}
            renderValue={(selected) => (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {(selected as string[]).map((value) => (
                  <Chip key={value} label={value} />
                ))}
              </Box>
            )}
          >
            <MenuItem value="residential">Residential</MenuItem>
            <MenuItem value="commercial">Commercial</MenuItem>
            <MenuItem value="industrial">Industrial</MenuItem>
          </Select>
        </FormControl>

        <FormControl fullWidth margin="normal">
          <InputLabel>Damage State</InputLabel>
          <Select
            multiple
            value={[]}
            input={<OutlinedInput label="Damage State" />}
            renderValue={(selected) => (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                {(selected as string[]).map((value) => (
                  <Chip key={value} label={value} />
                ))}
              </Box>
            )}
          >
            <MenuItem value="none">No Damage</MenuItem>
            <MenuItem value="slight">Slight</MenuItem>
            <MenuItem value="moderate">Moderate</MenuItem>
            <MenuItem value="extensive">Extensive</MenuItem>
            <MenuItem value="complete">Complete</MenuItem>
          </Select>
        </FormControl>

        <Typography variant="body2" color="text.secondary" sx={{ mt: 2 }}>
          Filters will be applied to map visualization and metrics calculation
        </Typography>
      </CardContent>
    </Card>
  );
};

export default FilterPanel;
