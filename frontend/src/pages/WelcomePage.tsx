import React from 'react';
import {
  Box,
  Typography,
  Container,
  Card,
  CardContent,
  Grid,
  Button
} from '@mui/material';
import { useNavigate } from 'react-router-dom';

const WelcomePage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <Container maxWidth="lg" sx={{ mt: 4 }}>
      <Box sx={{ textAlign: 'center', mb: 4 }}>
        <Typography variant="h2" component="h1" gutterBottom>
          TomorrowsCities Decision Support Environment
        </Typography>
        <Typography variant="h5" color="text.secondary" gutterBottom>
          Urban disaster risk assessment and resilience planning platform
        </Typography>
      </Box>

      <Grid container spacing={4}>
        <Grid item xs={12} md={6}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h5" component="h2" gutterBottom>
                Simulation Engine
              </Typography>
              <Typography variant="body1" paragraph>
                Model earthquake, flood, and landslide impacts on urban infrastructure. 
                Simulate the effects of natural hazards on buildings, power networks, and road systems.
              </Typography>
              <Button 
                variant="contained" 
                onClick={() => navigate('/engine')}
                sx={{ mt: 2 }}
              >
                Start Simulation
              </Button>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card sx={{ height: '100%' }}>
            <CardContent>
              <Typography variant="h5" component="h2" gutterBottom>
                Results Explorer
              </Typography>
              <Typography variant="body1" paragraph>
                Explore simulation results, analyze impact metrics, and visualize 
                disaster scenarios on interactive maps.
              </Typography>
              <Button 
                variant="contained" 
                onClick={() => navigate('/explore')}
                sx={{ mt: 2 }}
              >
                Explore Results
              </Button>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h5" component="h2" gutterBottom>
                Key Features
              </Typography>
              <Grid container spacing={2}>
                <Grid item xs={12} sm={6} md={3}>
                  <Typography variant="h6">Data Import</Typography>
                  <Typography variant="body2">
                    Support for GeoJSON, Excel, CSV formats
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Typography variant="h6">Hazard Modeling</Typography>
                  <Typography variant="body2">
                    Earthquake, flood, and landslide simulations
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Typography variant="h6">Policy Analysis</Typography>
                  <Typography variant="body2">
                    Evaluate resilience interventions
                  </Typography>
                </Grid>
                <Grid item xs={12} sm={6} md={3}>
                  <Typography variant="h6">Impact Metrics</Typography>
                  <Typography variant="body2">
                    8 core metrics for disaster assessment
                  </Typography>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Container>
  );
};

export default WelcomePage;
