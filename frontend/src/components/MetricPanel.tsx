import React, { useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Grid,
  LinearProgress,
  Avatar
} from '@mui/material';
import { useAppState } from '../contexts/AppStateContext';
import { generateMetrics } from '../services/api';

const MetricPanel: React.FC = () => {
  const { state } = useAppState();
  const [metrics, setMetrics] = useState<Record<string, any>>(state.metrics);
  const [loading, setLoading] = useState(false);

  const metricIcons = [
    '/icons/metric1.png',
    '/icons/metric2.png',
    '/icons/metric3.png',
    '/icons/metric4.png',
    '/icons/metric5.png',
    '/icons/metric6.png',
    '/icons/metric7.png',
    '/icons/metric8.png'
  ];

  useEffect(() => {
    if (state.bounds) {
      loadMetrics();
    }
  }, [state.bounds, state.renderCount]);

  const loadMetrics = async () => {
    setLoading(true);
    try {
      const result = await generateMetrics(state.bounds);
      setMetrics(result);
    } catch (error) {
      console.error('Failed to load metrics:', error);
      setMetrics(state.metrics);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ width: '100%', mt: 2, p: 2 }}>
      <Typography variant="h4" align="center" gutterBottom sx={{ fontWeight: 'bold' }}>
        IMPACTS
      </Typography>
      
      {loading && <LinearProgress sx={{ mb: 2 }} />}
      
      <Grid container spacing={2} justifyContent="center">
        {Object.entries(metrics).map(([key, metric], index) => (
          <Grid item xs={12} sm={6} md={3} key={key}>
            <Card sx={{ textAlign: 'center', minHeight: 120 }}>
              <CardContent>
                <Avatar
                  sx={{ 
                    width: 40, 
                    height: 40, 
                    mx: 'auto', 
                    mb: 1,
                    bgcolor: 'primary.main'
                  }}
                >
                  {index + 1}
                </Avatar>
                <Typography variant="h6" component="div">
                  {metric.value || 0}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {metric.desc}
                </Typography>
                {metric.max_value > 0 && (
                  <LinearProgress
                    variant="determinate"
                    value={(metric.value / metric.max_value) * 100}
                    sx={{ mt: 1 }}
                  />
                )}
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};

export default MetricPanel;
