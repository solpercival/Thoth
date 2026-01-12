/**
 * Preload script
 * Exposes secure IPC bridge to renderer process
 */

import { contextBridge, ipcRenderer } from 'electron';

// IPC channel names (inlined to avoid import issues in preload context)
const IPC_CHANNELS = {
  START_BACKEND: 'backend:start',
  STOP_BACKEND: 'backend:stop',
  BACKEND_STATUS: 'backend:status',
  BACKEND_ERROR: 'backend:error',
  BACKEND_LOG: 'backend:log',
  START_APP: 'app:start',
  STOP_APP: 'app:stop',
  API_REQUEST: 'api:request',
  APP_QUIT: 'app:quit',
  SHOW_ERROR: 'app:show-error',
};

// Define the IPC bridge API
const electronAPI = {
  // Backend control
  startBackend: () => ipcRenderer.invoke(IPC_CHANNELS.START_BACKEND),
  stopBackend: () => ipcRenderer.invoke(IPC_CHANNELS.STOP_BACKEND),
  getBackendStatus: () => ipcRenderer.invoke(IPC_CHANNELS.BACKEND_STATUS),
  // Start/stop named apps (e.g., 'call_assistant_v3', 'odin')
  startApp: (name: string) => ipcRenderer.invoke(IPC_CHANNELS.START_APP, name),
  stopApp: (name: string) => ipcRenderer.invoke(IPC_CHANNELS.STOP_APP, name),

  // API requests
  apiRequest: (method: string, endpoint: string, data?: any) =>
    ipcRenderer.invoke(IPC_CHANNELS.API_REQUEST, { method, endpoint, data }),

  // App control
  quitApp: () => ipcRenderer.invoke(IPC_CHANNELS.APP_QUIT),
  showError: (title: string, message: string) =>
    ipcRenderer.invoke(IPC_CHANNELS.SHOW_ERROR, { title, message }),

  // Listen for backend events
  onBackendLog: (callback: (message: string) => void) =>
    ipcRenderer.on(IPC_CHANNELS.BACKEND_LOG, (event, message) =>
      callback(message)
    ),
  onBackendError: (callback: (error: string) => void) =>
    ipcRenderer.on(IPC_CHANNELS.BACKEND_ERROR, (event, error) =>
      callback(error)
    ),
  onBackendStatusChange: (callback: (status: any) => void) =>
    ipcRenderer.on(IPC_CHANNELS.BACKEND_STATUS, (event, status) =>
      callback(status)
    ),
  // Remove listeners
  removeBackendLogListener: () =>
    ipcRenderer.removeAllListeners(IPC_CHANNELS.BACKEND_LOG),
  removeBackendErrorListener: () =>
    ipcRenderer.removeAllListeners(IPC_CHANNELS.BACKEND_ERROR),
  removeBackendStatusChangeListener: () =>
    ipcRenderer.removeAllListeners(IPC_CHANNELS.BACKEND_STATUS),
};

// Expose to renderer via window.electron
contextBridge.exposeInMainWorld('electron', electronAPI);

// Type definition for TypeScript
declare global {
  interface Window {
    electron: typeof electronAPI;
  }
}

export {};
