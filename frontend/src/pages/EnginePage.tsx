import React from 'react';
import { Box, Grid, Drawer, Tabs, Tab } from '@mui/material';
import MapViewer from '../components/MapViewer';
import ExecutePanel from '../components/ExecutePanel';
import MetricPanel from '../components/MetricPanel';
import ImportDataZone from '../components/ImportDataZone';
import FilterPanel from '../components/FilterPanel';
import MapInfoPanel from '../components/MapInfoPanel';

const EnginePage: React.FC = () => {
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
          <Tab label="DATA IMPORT" />
          <Tab label="SETTINGS" />
          <Tab label="MAP INFO" />
        </Tabs>
        
        <Box sx={{ p: 2, overflow: 'auto' }}>
          {selectedTab === 0 && <ImportDataZone />}
          {selectedTab === 1 && (
            <>
              <ExecutePanel />
              <FilterPanel />
            </>
          )}
          {selectedTab === 2 && (
            <MapInfoPanel />
          )}
        </Box>
      </Drawer>
      
      <Box sx={{ flexGrow: 1, display: 'flex', flexDirection: 'column' }}>
        <MapViewer />
        <MetricPanel />
      </Box>
    </Box>
  );
};

export default EnginePage;
