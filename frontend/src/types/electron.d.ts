/**
 * Type definitions for window.electron API
 * Exposed by preload.ts via contextBridge
 */

export interface ElectronAPI {
  // Backend control
  startBackend: () => Promise<void>;
  stopBackend: () => Promise<void>;
  getBackendStatus: () => Promise<{ running: boolean; url: string }>;

  // API requests
  apiRequest: (method: string, endpoint: string, data?: any) => Promise<any>;

  // App control
  quitApp: () => Promise<void>;
  showError: (title: string, message: string) => Promise<void>;

  // Event listeners
  onBackendLog: (callback: (message: string) => void) => void;
  onBackendError: (callback: (error: string) => void) => void;
  removeBackendLogListener: () => void;
  removeBackendErrorListener: () => void;
}

declare global {
  interface Window {
    electron: ElectronAPI;
  }
}

export {};
