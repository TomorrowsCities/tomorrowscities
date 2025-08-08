import React, { createContext, useContext, useReducer, ReactNode } from 'react';

interface LayerData {
  data: any;
  df: any;
  renderOrder: number;
  mapInfoTooltip: string;
  preProcessing: string;
  extraCols: Record<string, any>;
  filterCols?: string[];
  attributesRequired: string[][];
  attributes: string[][];
}

interface AppState {
  infra: string[];
  hazard: string;
  hazardList: string[];
  datetimeAnalysis: Date;
  layers: Record<string, LayerData>;
  center: [number, number];
  selectedLayer: string | null;
  renderCount: number;
  bounds: [[number, number], [number, number]] | null;
  selectedPolicies: number[];
  policies: Record<string, any>;
  metrics: Record<string, any>;
  version: string;
}

type AppAction = 
  | { type: 'SET_LAYER_DATA'; payload: { layerName: string; data: any } }
  | { type: 'SET_HAZARD'; payload: string }
  | { type: 'SET_INFRA'; payload: string[] }
  | { type: 'SET_CENTER'; payload: [number, number] }
  | { type: 'SET_BOUNDS'; payload: [[number, number], [number, number]] }
  | { type: 'SET_SELECTED_POLICIES'; payload: number[] }
  | { type: 'INCREMENT_RENDER_COUNT' }
  | { type: 'RESET_SESSION' };

const initialState: AppState = {
  infra: ["building"],
  hazard: "flood",
  hazardList: ["earthquake", "flood"],
  datetimeAnalysis: new Date(),
  layers: {
    parameter: {
      data: null,
      df: null,
      renderOrder: 0,
      mapInfoTooltip: 'Number of records',
      preProcessing: 'identity_preprocess',
      extraCols: {},
      attributesRequired: [['unnamed: 0']],
      attributes: [['unnamed: 0']]
    },
    landuse: {
      data: null,
      df: null,
      renderOrder: 20,
      mapInfoTooltip: 'Number of landuse zones',
      preProcessing: 'identity_preprocess',
      extraCols: {},
      filterCols: ['luf'],
      attributesRequired: [['geometry', 'zoneid', 'luf', 'population', 'densitycap', 'avgincome']],
      attributes: [['geometry', 'zoneid', 'luf', 'population', 'densitycap', 'floorarat', 'setback', 'avgincome']]
    },
    building: {
      data: null,
      df: null,
      renderOrder: 50,
      mapInfoTooltip: 'Number of buildings',
      preProcessing: 'building_preprocess',
      extraCols: { freqincome: '', ds: 0, node_id: null, hospital_access: true, has_power: true, casualty: 0 },
      filterCols: ['expstr'],
      attributesRequired: [['residents', 'fptarea', 'repvalue', 'nhouse', 'zoneid', 'expstr', 'bldid', 'geometry', 'specialfac']],
      attributes: [['residents', 'fptarea', 'repvalue', 'nhouse', 'zoneid', 'expstr', 'bldid', 'geometry', 'specialfac']]
    },
    household: {
      data: null,
      df: null,
      renderOrder: 0,
      mapInfoTooltip: 'Number of households',
      preProcessing: 'identity_preprocess',
      extraCols: { node_id: null, hospital_access: true, has_power: true, hospital_has_power: true },
      filterCols: ['income'],
      attributesRequired: [['hhid', 'nind', 'income', 'bldid', 'commfacid']],
      attributes: [['hhid', 'nind', 'income', 'bldid', 'commfacid']]
    },
    individual: {
      data: null,
      df: null,
      renderOrder: 0,
      mapInfoTooltip: 'Number of individuals',
      preProcessing: 'identity_preprocess',
      extraCols: { facility_access: true },
      filterCols: ['gender'],
      attributesRequired: [['individ', 'hhid', 'gender', 'age', 'eduattstat', 'head', 'indivfacid']],
      attributes: [['individ', 'hhid', 'gender', 'age', 'eduattstat', 'head', 'indivfacid']]
    },
    intensity: {
      data: null,
      df: null,
      renderOrder: 0,
      mapInfoTooltip: 'Number of intensity measurements',
      preProcessing: 'identity_preprocess',
      extraCols: {},
      filterCols: ['im'],
      attributesRequired: [['geometry', 'im'], ['geometry', 'pga']],
      attributes: [['geometry', 'im'], ['geometry', 'pga']]
    }
  },
  center: [41.01, 28.98],
  selectedLayer: null,
  renderCount: 0,
  bounds: null,
  selectedPolicies: [],
  policies: {
    '1': { id: 1, label: 'P1', description: 'Land and tenure security program' },
    '2': { id: 2, label: 'P2', description: 'Housing retrofitting' },
    '3': { id: 3, label: 'P3', description: 'Investment in water and sanitation' },
    '4': { id: 4, label: 'P4', description: 'Investments in road networks' },
    '5': { id: 5, label: 'P5', description: 'Access to more shelters' },
    '6': { id: 6, label: 'P6', description: 'Funding community networks' },
    '8': { id: 8, label: 'P8', description: 'Cash transfers to vulnerable groups' },
    '9': { id: 9, label: 'P9', description: 'Waste collection and river cleaning program' }
  },
  metrics: {
    "metric1": { "desc": "Number of workers unemployed", "value": 0, "max_value": 100 },
    "metric2": { "desc": "Number of children with no access to education", "value": 0, "max_value": 100 },
    "metric3": { "desc": "Number of households with no access to hospital", "value": 0, "max_value": 100 },
    "metric4": { "desc": "Number of individuals with no access to hospital", "value": 0, "max_value": 100 },
    "metric5": { "desc": "Number of households displaced", "value": 0, "max_value": 100 },
    "metric6": { "desc": "Number of homeless individuals", "value": 0, "max_value": 100 },
    "metric7": { "desc": "Population displacement", "value": 0, "max_value": 100 },
    "metric8": { "desc": "Number of casualties", "value": 0, "max_value": 100 }
  },
  version: '0.6'
};

const AppStateContext = createContext<{
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
} | null>(null);

export const useAppState = () => {
  const context = useContext(AppStateContext);
  if (!context) {
    throw new Error('useAppState must be used within AppStateProvider');
  }
  return context;
};

export const AppStateProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [state, dispatch] = useReducer(appStateReducer, initialState);
  
  return (
    <AppStateContext.Provider value={{ state, dispatch }}>
      {children}
    </AppStateContext.Provider>
  );
};

function appStateReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_LAYER_DATA':
      return {
        ...state,
        layers: {
          ...state.layers,
          [action.payload.layerName]: {
            ...state.layers[action.payload.layerName],
            data: action.payload.data
          }
        }
      };
    case 'SET_HAZARD':
      return { ...state, hazard: action.payload };
    case 'SET_INFRA':
      return { ...state, infra: action.payload };
    case 'SET_CENTER':
      return { ...state, center: action.payload };
    case 'SET_BOUNDS':
      return { ...state, bounds: action.payload };
    case 'SET_SELECTED_POLICIES':
      return { ...state, selectedPolicies: action.payload };
    case 'INCREMENT_RENDER_COUNT':
      return { ...state, renderCount: state.renderCount + 1 };
    case 'RESET_SESSION':
      return { ...initialState, renderCount: state.renderCount + 1 };
    default:
      return state;
  }
}
