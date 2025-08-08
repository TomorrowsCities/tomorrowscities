import axios from 'axios';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const uploadFile = async (formData: FormData, onProgress?: (progress: any) => void) => {
  return api.post('/api/layers/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: onProgress,
  });
};

export const executeSimulation = async (data: {
  layers: any;
  hazard: string;
  infra: string[];
  policies: number[];
  parameters: any;
}) => {
  return api.post('/api/simulation/execute', data);
};

export const generateMetrics = async (bounds: any) => {
  const response = await api.get('/api/metrics/generate', {
    params: { bounds: JSON.stringify(bounds) }
  });
  return response.data;
};

export const loadSession = async (sessionName: string) => {
  const response = await api.get(`/api/sessions/${sessionName}`);
  return response.data;
};

export const saveSession = async (sessionName: string, data: any) => {
  return api.post(`/api/sessions/${sessionName}`, data);
};

export const listSessions = async () => {
  const response = await api.get('/api/sessions');
  return response.data;
};

export default api;
