/**
 * Native Python Backend Manager
 * Launches Flask backend directly using Python virtual environment
 */

import { spawn, ChildProcess } from 'child_process';
import { ipcMain, BrowserWindow } from 'electron';
import axios, { AxiosInstance } from 'axios';
import { EventEmitter } from 'events';
import { CONFIG, getBackendUrl } from './config';
import path from 'path';

export class BackendManager extends EventEmitter {
  private process: ChildProcess | null = null;
  public isRunning: boolean = false;
  private appProcesses: Map<string, ChildProcess> = new Map();
  private httpClient: AxiosInstance;
  private platform: string = process.platform;

  constructor() {
    super();
    this.httpClient = axios.create({
      baseURL: getBackendUrl(),
      timeout: 5000,
    });
  }

  /**
   * Start the Flask backend using Python virtual environment
   * Automatically detects Windows or Linux/macOS and uses the correct venv paths
   */
  async start(): Promise<boolean> {
    if (this.isRunning) {
      console.log('Backend already running');
      return true;
    }

    return new Promise((resolve) => {
      try {
        const platformName = this.platform === 'win32' ? 'Windows' : 
                            this.platform === 'darwin' ? 'macOS' : 'Linux';
        console.log(`Starting native Python Flask backend on ${platformName}...`);

        // Get backend directory - from frontend/dist/electron -> backend
        const backendDir = path.join(process.cwd(), '..', 'backend');
        const venvDir = path.join(process.cwd(), '..', '.venv');
        
        console.log('Backend directory:', backendDir);
        console.log('Venv directory:', venvDir);

        // Determine Python executable path from venv based on OS
        // Windows: .venv/Scripts/python.exe
        // Linux/macOS: venv/bin/python
        let pythonExe: string;
        if (this.platform === 'win32') {
          pythonExe = path.join(venvDir, 'Scripts', 'python.exe');
        } else {
          pythonExe = path.join(venvDir, 'bin', 'python');
        }

        console.log('Using Python executable:', pythonExe);

        // Verify Python executable exists
        const fs = require('fs');
        if (!fs.existsSync(pythonExe)) {
          const errorMsg = `Python executable not found at: ${pythonExe}\nPlease create a virtual environment: python -m venv venv`;
          console.error(errorMsg);
          this.emit('error', errorMsg);
          resolve(false);
          return;
        }

        // Set environment variables for Flask
        // No need to "activate" venv - using Python executable directly handles it
        const env = {
          ...process.env,
          FLASK_APP: 'odin/app.py',
          FLASK_ENV: 'development',
          PYTHONUNBUFFERED: '1',
          // Ensure venv's site-packages are used
          VIRTUAL_ENV: venvDir,
        };

        // Start Flask using python -m flask run
        this.process = spawn(
          pythonExe,
          ['-m', 'flask', 'run', '--host=0.0.0.0', '--port=5000'],
          {
            cwd: backendDir,
            env: env,
            stdio: ['ignore', 'pipe', 'pipe'],
            shell: false,
          }
        );

        if (!this.process) {
          throw new Error('Failed to spawn Python Flask process');
        }

        // Handle stdout
        this.process.stdout?.on('data', (data) => {
          const msg = data.toString().trim();
          if (msg) {
            console.log(`[Flask Backend] ${msg}`);
            this.emit('log', msg);
          }
        });

        // Handle stderr
        this.process.stderr?.on('data', (data) => {
          const msg = data.toString().trim();
          if (msg) {
            console.log(`[Flask Backend stderr] ${msg}`);
            this.emit('log', msg);
          }
        });

        // Health check logic
        const maxRetries = 30;
        let retryCount = 0;

        const checkHealth = async () => {
          try {
            const res = await this.httpClient.get('/health');
            if (res.status === 200) {
              console.log('✓ Backend is ready and responding');
              this.isRunning = true;
              this.emit('started');
              return resolve(true);
            }
          } catch (_) {
            // Health check failed, will retry
          }

          retryCount++;
          if (retryCount < maxRetries) {
            setTimeout(checkHealth, 2000);
          } else {
            console.warn('Backend health check timed out; assuming running');
            this.isRunning = true;
            this.emit('started');
            resolve(true);
          }
        };

        // Start health checks after 3 seconds
        setTimeout(checkHealth, 3000);

        // Handle process exit
        this.process.on('exit', (code) => {
          console.log(`Backend process exited with code: ${code}`);
          this.isRunning = false;
          this.process = null;
          this.emit('stopped');
        });

        // Handle process errors
        this.process.on('error', (err) => {
          console.error('Backend process error:', err);
          this.emit('error', String(err));
          resolve(false);
        });

      } catch (err) {
        console.error('Error starting backend:', err);
        this.emit('error', String(err));
        resolve(false);
      }
    });
  }

  async stop(): Promise<boolean> {
    if (!this.isRunning) {
      console.log('Backend not running');
      return true;
    }

    return new Promise((resolve) => {
      try {
        console.log('Stopping Python Flask backend...');

        if (!this.process) {
          this.isRunning = false;
          this.emit('stopped');
          resolve(true);
          return;
        }

        // Set a timeout for force kill
        const killTimeout = setTimeout(() => {
          if (this.process) {
            console.warn('Force killing backend process...');
            this.process.kill('SIGKILL');
          }
          this.isRunning = false;
          this.emit('stopped');
          resolve(true);
        }, 5000);

        // Try graceful shutdown first
        this.process.on('exit', () => {
          clearTimeout(killTimeout);
          console.log('Backend stopped gracefully');
          this.isRunning = false;
          this.emit('stopped');
          resolve(true);
        });

        // Send SIGTERM for graceful shutdown
        this.process.kill('SIGTERM');

      } catch (err) {
        console.error('Error stopping backend:', err);
        this.isRunning = false;
        this.emit('stopped');
        resolve(false);
      }
    });
  }

  /**
   * Get backend status
   */
  async getStatus(): Promise<any> {
    if (!this.isRunning) {
      return { isRunning: false };
    }

    try {
      const response = await this.httpClient.get('/status');
      return { isRunning: true, ...response.data };
    } catch (err) {
      console.log('Backend health check failed');
      // Mark as not running if we can't reach it
      this.isRunning = false;
      return { isRunning: false };
    }
  }

  /**
   * Start a named app (not used in native mode)
   */
  async startApp(appName: string): Promise<boolean> {
    console.log(`[Native] Starting app: ${appName} - Not implemented`);
    return true;
  }

  /**
   * Stop a named app (not used in native mode)
   */
  async stopApp(appName: string): Promise<boolean> {
    console.log(`[Native] Stopping app: ${appName} - Not implemented`);
    return true;
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
export function setupBackendIPC(mainWindow: BrowserWindow | null): void {
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
    return { isRunning: backend.isRunning };
  });

  // Handle API requests from renderer
  ipcMain.handle(
    CONFIG.ipc.API_REQUEST,
    async (event, { method, endpoint, data }) => {
      return {
        success: true,
        message: 'Native backend API calls can be added here',
      };
    }
  );

  // Handle starting/stopping named apps
  ipcMain.handle(CONFIG.ipc.START_APP, async (event, appName: string) => {
    return await backend.startApp(appName);
  });

  ipcMain.handle(CONFIG.ipc.STOP_APP, async (event, appName: string) => {
    return await backend.stopApp(appName);
  });

  // Emit backend events to renderer
  backend.on('started', () => {
    console.log('Backend started event - notifying renderer');
    if (mainWindow && mainWindow.webContents) {
      mainWindow.webContents.send(CONFIG.ipc.BACKEND_STATUS, { isRunning: true });
    }
  });

  backend.on('stopped', () => {
    console.log('Backend stopped event - notifying renderer');
    if (mainWindow && mainWindow.webContents) {
      mainWindow.webContents.send(CONFIG.ipc.BACKEND_STATUS, { isRunning: false });
    }
  });

  backend.on('log', (message) => {
    if (mainWindow && mainWindow.webContents) {
      mainWindow.webContents.send(CONFIG.ipc.BACKEND_LOG, message);
    }
  });

  backend.on('error', (message) => {
    if (mainWindow && mainWindow.webContents) {
      mainWindow.webContents.send(CONFIG.ipc.BACKEND_ERROR, message);
    }
  });
}
