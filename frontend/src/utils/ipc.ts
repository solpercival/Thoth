/**
 * IPC utilities for frontend-backend communication
 * Provides methods to invoke Electron IPC handlers
 */

export const ipcInvoke = (channel: string, ...args: any[]) => {
  if (window.electron && window.electron.ipcInvoke) {
    return window.electron.ipcInvoke(channel, ...args);
  }
  throw new Error('IPC not available');
};

export const ipcOn = (channel: string, listener: (...args: any[]) => void) => {
  if (window.electron && window.electron.onBackendLog) {
    // For now, this uses the backend log listener
    // Can be extended for custom channels
    window.electron.onBackendLog(listener);
  }
};

export const ipcOff = (channel: string, listener: (...args: any[]) => void) => {
  if (window.electron && window.electron.removeBackendLogListener) {
    window.electron.removeBackendLogListener();
  }
};

// Type definitions for window.electron
declare global {
  interface Window {
    electron?: {
      ipcInvoke: (channel: string, ...args: any[]) => Promise<any>;
      start3CXEnvironment: () => Promise<any>;
      startBackend: () => Promise<any>;
      stopBackend: () => Promise<any>;
      getBackendStatus: () => Promise<any>;
      startApp: (name: string) => Promise<any>;
      stopApp: (name: string) => Promise<any>;
      apiRequest: (method: string, endpoint: string, data?: any) => Promise<any>;
      quitApp: () => Promise<any>;
      showError: (title: string, message: string) => Promise<any>;
      onBackendLog: (callback: (message: string) => void) => void;
      onBackendError: (callback: (error: string) => void) => void;
      onBackendStatusChange: (callback: (status: any) => void) => void;
      removeBackendLogListener: () => void;
      removeBackendErrorListener: () => void;
      removeBackendStatusChangeListener: () => void;
    };
  }
}
