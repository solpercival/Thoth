/**
 * Configuration for Electron app
 * Paths, ports, and backend settings
 */

import path from 'path';

export const CONFIG = {
  // Python backend settings
  python: {
    // Backend server port
    port: 5000,
    host: 'localhost',
    // Path to Flask backend relative to app root
    getScriptPath: (appPath: string) => path.join(appPath, '..', 'backend', 'core', 'main.py'),
    // Python executable (will be set based on environment)
    executable: '',
  },

  // Electron window settings
  window: {
    width: 1200,
    height: 800,
    minWidth: 1024,
    minHeight: 600,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  },

  // Paths
  paths: {
    // HTML entry point
    indexUrl: 'http://localhost:3000', // For development (React dev server)
    // For production, use: `file://${path.join(__dirname, '..', 'renderer', 'index.html')}`
  },

  // IPC channels for communication
  ipc: {
    // Backend control
    START_BACKEND: 'backend:start',
    STOP_BACKEND: 'backend:stop',
    BACKEND_STATUS: 'backend:status',
    BACKEND_ERROR: 'backend:error',
    BACKEND_LOG: 'backend:log',
    // App control (start/stop named apps)
    START_APP: 'app:start',
    STOP_APP: 'app:stop',

    // API requests
    API_REQUEST: 'api:request',

    // App control
    APP_QUIT: 'app:quit',
    SHOW_ERROR: 'app:show-error',
  },
};
export const getBackendUrl = (): string => {
  return `http://${CONFIG.python.host}:${CONFIG.python.port}`;
};
