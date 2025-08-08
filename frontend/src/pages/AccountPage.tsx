import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Avatar,
  Grid
} from '@mui/material';
import { GitHub, Google } from '@mui/icons-material';
import { useAuth } from '../contexts/AuthContext';

const AccountPage: React.FC = () => {
  const { user, login, logout, loading } = useAuth();

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <Typography>Loading...</Typography>
      </Box>
    );
  }

  if (!user) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
        <Card sx={{ maxWidth: 400, width: '100%' }}>
          <CardContent sx={{ textAlign: 'center' }}>
            <Typography variant="h5" gutterBottom>
              Login
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
              Sign in to access the TomorrowsCities platform
            </Typography>
            
            <Grid container spacing={2}>
              <Grid item xs={12}>
                <Button
                  variant="outlined"
                  fullWidth
                  startIcon={<Google />}
                  onClick={() => login('google')}
                >
                  Login with Google
                </Button>
              </Grid>
              <Grid item xs={12}>
                <Button
                  variant="outlined"
                  fullWidth
                  startIcon={<GitHub />}
                  onClick={() => login('github')}
                >
                  Login with GitHub
                </Button>
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      </Box>
    );
  }

  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '50vh' }}>
      <Card sx={{ maxWidth: 400, width: '100%' }}>
        <CardContent sx={{ textAlign: 'center' }}>
          <Avatar
            src={user.userProfile?.avatar_url || user.userProfile?.picture}
            sx={{ width: 80, height: 80, mx: 'auto', mb: 2 }}
          >
            {user.username.charAt(0).toUpperCase()}
          </Avatar>
          
          <Typography variant="h5" gutterBottom>
            Hello {user.username}
          </Typography>
          
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Logged in as {user.admin ? 'admin' : 'user'}
          </Typography>

          {user.userProfile && (
            <Box sx={{ mb: 2, textAlign: 'left' }}>
              {Object.entries(user.userProfile).map(([key, value]) => (
                <Typography key={key} variant="body2">
                  <strong>{key}:</strong> {String(value)}
                </Typography>
              ))}
            </Box>
          )}

          <Button
            variant="contained"
            color="secondary"
            onClick={logout}
            fullWidth
          >
            Logout
          </Button>
        </CardContent>
      </Card>
    </Box>
  );
};

export default AccountPage;
