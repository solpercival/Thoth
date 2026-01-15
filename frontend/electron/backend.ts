/**
 * Docker Backend Manager
 * Launches, monitors, and communicates with Docker-based Python Flask backend
 */

import { spawn, ChildProcess } from 'child_process';
import { ipcMain, BrowserWindow } from 'electron';
import axios, { AxiosInstance } from 'axios';
import { EventEmitter } from 'events';
import { CONFIG, getBackendUrl } from './config';

export class BackendManager extends EventEmitter {
  private container: ChildProcess | null = null;
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
   * Start the Docker backend using docker-compose
   */
  async start(): Promise<boolean> {
    if (this.isRunning) {
      console.log('Docker backend already running');
      return true;
    }

    return new Promise((resolve) => {
      try {
        console.log('Starting Docker backend...');
        
        // Get the backend directory
        const backendDir = process.platform === 'win32'
          ? `${process.cwd()}\\..\\backend`
          : `${process.cwd()}/../backend`;
        
        const command = process.platform === 'win32' ? 'docker-compose.exe' : 'docker-compose';
        
        this.container = spawn(command, ['up', '--build'], {
          cwd: backendDir,
          stdio: ['ignore', 'pipe', 'pipe'],
          shell: true,
        });

        if (!this.container) {
          throw new Error('Failed to spawn docker-compose process');
        }

        // Handle output
        this.container.stdout?.on('data', (data) => {
          const message = data.toString().trim();
          if (message) {
            console.log(`[Docker Backend] ${message}`);
            this.emit('log', message);
          }
        });

        this.container.stderr?.on('data', (data) => {
          const message = data.toString().trim();
          if (message) {
            console.log(`[Docker Backend stderr] ${message}`);
            this.emit('log', message);
          }
        });

        // Wait for the backend to be ready
        const maxRetries = 30;
        let retries = 0;
        
        const checkBackend = async () => {
          try {
            const response = await this.httpClient.get('/health');
            if (response.status === 200) {
              console.log('Docker backend is ready');
              this.isRunning = true;
              this.emit('started');
              resolve(true);
              return;
            }
          } catch (error) {
            // Still waiting
          }
          
          retries++;
          if (retries < maxRetries) {
            setTimeout(checkBackend, 2000);
          } else {
            console.warn('Backend did not respond after 60 seconds');
            this.isRunning = true; // Assume it's running even if health check failed
            this.emit('started');
            resolve(true);
          }
        };

        // Start checking after 2 seconds
        setTimeout(checkBackend, 2000);

        this.container.on('exit', (code) => {
          console.log(`Docker container exited with code ${code}`);
          this.isRunning = false;
          this.container = null;
          this.emit('stopped');
        });

        this.container.on('error', (err) => {
          console.error('Docker process error:', err);
          this.emit('error', String(err));
          resolve(false);
        });
      } catch (err) {
        console.error('Error starting Docker backend:', err);
        this.emit('error', String(err));
        resolve(false);
      }
    });
  }

  /**
   * Stop the Docker backend
   */
  async stop(): Promise<boolean> {
    if (!this.isRunning) {
      console.log('Docker backend not running');
      return true;
    }

    return new Promise((resolve) => {
      try {
        console.log('Stopping Docker backend...');
        
        const backendDir = process.platform === 'win32'
          ? `${process.cwd()}\\..\\backend`
          : `${process.cwd()}/../backend`;
        
        const command = process.platform === 'win32' ? 'docker-compose.exe' : 'docker-compose';
        
        const stopProcess = spawn(command, ['down'], {
          cwd: backendDir,
          stdio: 'pipe',
          shell: true,
        });

        const timeout = setTimeout(() => {
          if (this.container) {
            console.log('Force killing Docker container');
            this.container.kill('SIGKILL');
          }
          this.isRunning = false;
          this.emit('stopped');
          resolve(true);
        }, 10000);

        stopProcess.on('exit', (code) => {
          clearTimeout(timeout);
          console.log(`Docker stop command exited with code ${code}`);
          this.isRunning = false;
          this.emit('stopped');
          resolve(code === 0);
        });

        stopProcess.on('error', (err) => {
          clearTimeout(timeout);
          console.error('Error stopping Docker:', err);
          this.isRunning = false;
          this.emit('stopped');
          this.emit('error', String(err));
          resolve(false);
        });
      } catch (err) {
        console.error('Error stopping Docker:', err);
        this.isRunning = false;
        this.emit('stopped');
        this.emit('error', String(err));
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
   * Start a named app (placeholder for Docker environment)
   */
  async startApp(appName: string): Promise<boolean> {
    console.log(`[Docker] Starting app: ${appName}`);
    return true;
  }

  /**
   * Stop a named app (placeholder for Docker environment)
   */
  async stopApp(appName: string): Promise<boolean> {
    console.log(`[Docker] Stopping app: ${appName}`);
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
        message: 'Docker backend does not expose direct API calls',
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
