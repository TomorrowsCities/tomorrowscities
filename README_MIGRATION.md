# TomorrowsCities Migration to React + MUI

This document describes the migration from Solara to React + Material-UI framework.

## Architecture Changes

### Before (Solara)
- Python-based reactive web framework
- Direct function calls to backend
- ipyleaflet for maps
- Solara components for UI

### After (React + MUI)
- React frontend with TypeScript
- REST API communication with Python backend
- React Leaflet for maps
- Material-UI components

## Running the Application

### Development Mode

1. Install backend dependencies:
```bash
pip install -r requirements.txt
```

2. Install frontend dependencies:
```bash
cd frontend
npm install
```

3. Start the backend API:
```bash
uvicorn api.main:app --reload --port 8000
```

4. Start the frontend (in another terminal):
```bash
cd frontend
npm start
```

The application will be available at:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000

### Production Build

```bash
cd frontend
npm run build
```

## Key Components Migrated

1. **WebApp** → **App.tsx** with React Router
2. **ExecutePanel** → **ExecutePanel.tsx** with MUI components
3. **MapViewer** → **MapViewer.tsx** with React Leaflet
4. **MetricPanel** → **MetricPanel.tsx** with MUI cards
5. **FileDropMultiple** → **FileDropZone.tsx** with react-dropzone
6. **Authentication** → **AuthContext.tsx** with OAuth2 flow

## State Management

- Solara reactive variables → React Context + useReducer
- Complex nested state preserved in AppStateContext
- All layer data and simulation parameters maintained

## API Endpoints

- `POST /api/layers/upload` - File upload
- `POST /api/simulation/execute` - Run simulation
- `GET /api/metrics/generate` - Calculate metrics
- `GET /api/sessions` - List sessions
- `POST /api/sessions/{name}` - Save session

## Testing

Test all major workflows:
1. File upload and data import
2. Map visualization
3. Simulation execution
4. Metrics display
5. Authentication flow

## Notes

- All existing functionality preserved
- UI matches original Solara interface
- Backend computation engine unchanged
- OAuth2 configuration required for authentication
