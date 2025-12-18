/**
 * Backend process manager
 * Launches, monitors, and communicates with Python Flask backend
 */

import { spawn, ChildProcess } from 'child_process';
import { ipcMain } from 'electron';
import { CONFIG, getBackendUrl } from './config';
import axios, { AxiosInstance } from 'axios';
import { EventEmitter } from 'events';

export class BackendManager extends EventEmitter {
  private process: ChildProcess | null = null;
  private isRunning: boolean = false;
  private httpClient: AxiosInstance;

  constructor() {
    super();
    // Configure HTTP client for backend API calls
    this.httpClient = axios.create({
      baseURL: getBackendUrl(),
      timeout: 5000,
    });
  }

  /**
   * Start the Python Flask backend
   */
  async start(): Promise<boolean> {
    if (this.isRunning) {
      console.log('Backend already running');
      return true;
    }

    return new Promise((resolve) => {
      try {
        console.log('Starting backend...');
        
        // Determine Python executable path
        // In development: use 'python' or 'python3'
        // In production: use bundled Python
        const pythonExe = process.env.PYTHON_EXE || 'python';
        
        // Path to backend - go up from frontend folder to find backend
        const backendPath = '../backend/core/call_assistant/app.py';
        
        // Start Python backend process
        this.process = spawn(pythonExe, [backendPath], {
          cwd: process.cwd(),
          stdio: ['inherit', 'pipe', 'pipe'],
          shell: process.platform === 'win32', // Use shell on Windows
        });

        if (!this.process) {
          throw new Error('Failed to spawn backend process');
        }

        const processId = this.process.pid;
        console.log(`Backend process started with PID: ${processId}`);

        // Handle stdout
        this.process.stdout?.on('data', (data) => {
          const message = data.toString().trim();
          if (message) {
            console.log(`[Backend] ${message}`);
            this.emit('log', message);
          }
        });

        // Handle stderr
        this.process.stderr?.on('data', (data) => {
          const message = data.toString().trim();
          if (message) {
            console.error(`[Backend Error] ${message}`);
            this.emit('error', message);
          }
        });

        // Handle process exit
        this.process.on('exit', (code) => {
          console.log(`Backend process exited with code ${code}`);
          this.isRunning = false;
          this.process = null;
          this.emit('stopped');
        });

        // Wait for backend to be ready (max 10 seconds)
        this.waitForBackend(10000).then((ready) => {
          if (ready) {
            this.isRunning = true;
            console.log('Backend is ready');
            this.emit('started');
            resolve(true);
          } else {
            this.stop();
            console.error('Backend failed to start within timeout');
            this.emit('error', 'Backend startup timeout');
            resolve(false);
          }
        });

      } catch (error) {
        console.error('Error starting backend:', error);
        this.emit('error', String(error));
        resolve(false);
      }
    });
  }

  /**
   * Stop the Python Flask backend
   */
  async stop(): Promise<void> {
    if (!this.process) {
      return;
    }

    return new Promise((resolve) => {
      if (this.process) {
        // Try graceful shutdown first
        this.process.on('exit', () => {
          this.isRunning = false;
          this.process = null;
          console.log('Backend stopped');
          resolve();
        });

        // Kill the process
        this.process.kill();

        // Force kill after 5 seconds if still running
        setTimeout(() => {
          if (this.process) {
            this.process.kill('SIGKILL');
          }
          resolve();
        }, 5000);
      }
    });
  }

  /**
   * Check if backend is running and ready
   */
  private waitForBackend(timeoutMs: number): Promise<boolean> {
    return new Promise((resolve) => {
      const startTime = Date.now();
      const checkInterval = setInterval(async () => {
        try {
          const response = await axios.get(`${getBackendUrl()}/health`, {
            timeout: 1000,
          });
          if (response.status === 200) {
            clearInterval(checkInterval);
            resolve(true);
          }
        } catch {
          // Still waiting for backend to be ready
        }

        if (Date.now() - startTime > timeoutMs) {
          clearInterval(checkInterval);
          resolve(false);
        }
      }, 500);
    });
  }

  /**
   * Make an API request to the backend
   * Usage: backend.api('POST', '/api/shifts', { data })
   */
  async api(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    endpoint: string,
    data?: any
  ): Promise<any> {
    try {
      const response = await this.httpClient({
        method,
        url: endpoint,
        data,
      });
      return {
        success: true,
        data: response.data,
      };
    } catch (error: any) {
      console.error(`API Error [${method} ${endpoint}]:`, error.message);
      return {
        success: false,
        error: error.response?.data?.error || error.message,
      };
    }
  }

  /**
   * Get backend status
   */
  getStatus(): {
    isRunning: boolean;
    url: string;
  } {
    return {
      isRunning: this.isRunning,
      url: getBackendUrl(),
    };
  }
}

// Singleton instance
let backendInstance: BackendManager | null = null;

export function getBackendManager(): BackendManager {
  if (!backendInstance) {
    backendInstance = new BackendManager();
  }
  return backendInstance;
}

/**
 * Setup IPC handlers for backend management
 */
export function setupBackendIPC(): void {
  const backend = getBackendManager();

  // Handle backend start request
  ipcMain.handle(CONFIG.ipc.START_BACKEND, async () => {
    return await backend.start();
  });

  // Handle backend stop request
  ipcMain.handle(CONFIG.ipc.STOP_BACKEND, async () => {
    await backend.stop();
  });

  // Handle backend status request
  ipcMain.handle(CONFIG.ipc.BACKEND_STATUS, () => {
    return backend.getStatus();
  });

  // Handle API requests from renderer
  ipcMain.handle(
    CONFIG.ipc.API_REQUEST,
    async (event, { method, endpoint, data }) => {
      return await backend.api(method, endpoint, data);
    }
  );

  // Emit backend events to renderer
  backend.on('log', (message) => {
    // Send to renderer if window is available
  });

  backend.on('error', (message) => {
    // Send error to renderer
  });
}
