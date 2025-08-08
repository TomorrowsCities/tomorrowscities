import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { CssBaseline, AppBar, Toolbar, Tabs, Tab, Box } from '@mui/material';
import { AuthProvider } from './contexts/AuthContext';
import { AppStateProvider } from './contexts/AppStateContext';
import EnginePage from './pages/EnginePage';
import ExplorePage from './pages/ExplorePage';
import AccountPage from './pages/AccountPage';
import WelcomePage from './pages/WelcomePage';

const theme = createTheme({
  palette: {
    primary: {
      main: '#1976d2',
    },
  },
});

function App() {
  const [currentTab, setCurrentTab] = React.useState(0);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue);
  };

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AuthProvider>
        <AppStateProvider>
          <Router>
            <AppBar position="static">
              <Toolbar>
                <Tabs value={currentTab} onChange={handleTabChange}>
                  <Tab label="Welcome" component="a" href="/" />
                  <Tab label="Engine" component="a" href="/engine" />
                  <Tab label="Explore" component="a" href="/explore" />
                  <Tab label="Account" component="a" href="/account" />
                </Tabs>
              </Toolbar>
            </AppBar>
            <Routes>
              <Route path="/" element={<WelcomePage />} />
              <Route path="/engine" element={<EnginePage />} />
              <Route path="/explore" element={<ExplorePage />} />
              <Route path="/account" element={<AccountPage />} />
            </Routes>
          </Router>
        </AppStateProvider>
      </AuthProvider>
    </ThemeProvider>
  );
}

export default App;
