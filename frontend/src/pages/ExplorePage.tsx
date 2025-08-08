import React from 'react';
import { Box, Drawer, Tabs, Tab } from '@mui/material';
import MapViewer from '../components/MapViewer';
import MetricPanel from '../components/MetricPanel';
import FilterPanel from '../components/FilterPanel';

const ExplorePage: React.FC = () => {
  const [selectedTab, setSelectedTab] = React.useState(0);

  return (
    <Box sx={{ display: 'flex', height: 'calc(100vh - 64px)' }}>
      <Drawer
        variant="permanent"
        sx={{
          width: 400,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: 400,
            boxSizing: 'border-box',
            position: 'relative',
          },
        }}
      >
        <Tabs
          value={selectedTab}
          onChange={(_, newValue) => setSelectedTab(newValue)}
          variant="fullWidth"
        >
          <Tab label="SESSIONS" />
          <Tab label="MAP INFO" />
          <Tab label="FILTERS" />
        </Tabs>
        
        <Box sx={{ p: 2, overflow: 'auto' }}>
          {selectedTab === 0 && (
            <Box>
              <div>Session management - Load and save analysis sessions</div>
            </Box>
          )}
          {selectedTab === 1 && (
            <Box>
              <div>Map Info - Layer details and statistics</div>
            </Box>
          )}
          {selectedTab === 2 && <FilterPanel />}
        </Box>
      </Drawer>
      
      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
        <MapViewer />
        <MetricPanel />
      </Box>
    </Box>
  );
};

export default ExplorePage;
