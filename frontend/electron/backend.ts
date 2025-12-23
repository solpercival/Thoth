/**
 * Backend process manager
 * Launches, monitors, and communicates with Python Flask backend
 */

import { spawn, ChildProcess, execFile } from 'child_process';
import { ipcMain } from 'electron';
import path from 'path';
import fs from 'fs';
import { CONFIG, getBackendUrl } from './config';
import axios, { AxiosInstance } from 'axios';
import { EventEmitter } from 'events';

export class BackendManager extends EventEmitter {
  private process: ChildProcess | null = null;
  private isRunning: boolean = false;
  // Map of named app processes (e.g., call_assistant_v3, odin)
  private appProcesses: Map<string, ChildProcess> = new Map();
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
        console.log('__dirname:', __dirname);
        console.log('process.cwd():', process.cwd());
        
        // Determine Python executable path
        // Prefer env var, then common venv locations, then 'python'
        let pythonExe = process.env.PYTHON_EXE || 'python';
        const _candidates = [
          path.join(process.cwd(), '..', 'venv', 'Scripts', 'python.exe'),
          path.join(process.cwd(), 'venv', 'Scripts', 'python.exe'),
          path.join(__dirname, '..', '..', 'venv', 'Scripts', 'python.exe'),
          path.join(__dirname, '..', '..', '..', 'venv', 'Scripts', 'python.exe'),
        ];
        for (const c of _candidates) {
          try {
            if (fs.existsSync(c)) {
              pythonExe = c;
              break;
            }
          } catch (_) {}
        }
        console.log(`Using Python executable: ${pythonExe}`);
        // Diagnostics: log PATH and ComSpec availability to help debug ENOENT
        try {
          console.log('process.env.PATH=', process.env.PATH);
          console.log('process.env.ComSpec=', process.env.ComSpec);
          const cmdPath = process.env.ComSpec || 'C:\\Windows\\System32\\cmd.exe';
          console.log('cmd exists:', fs.existsSync(cmdPath), cmdPath);
          console.log('python exists:', fs.existsSync(pythonExe), pythonExe);
        } catch (diagErr) {
          console.warn('Diagnostics failed', diagErr);
        }

        // If chosen pythonExe doesn't exist and is an absolute path, try fallbacks
        if ((pythonExe.includes('\\') || pythonExe.includes('/')) && !fs.existsSync(pythonExe)) {
          console.log(`Python path not found: ${pythonExe}, trying fallbacks...`);
          const fallbacks = ['py', 'py.exe', 'python', 'python3'];
          for (const fb of fallbacks) {
            try {
              // Quick test: try to spawn with --version
              const testProc = spawn(fb, ['--version'], {
                stdio: 'pipe',
                shell: false,
              });
              testProc.on('exit', (code) => {
                if (code === 0) {
                  pythonExe = fb;
                  console.log(`Found working fallback Python: ${fb}`);
                }
              });
              testProc.on('error', () => {});
            } catch (_) {}
          }
        }
        
        // Path to backend - use cwd as anchor (more reliable than __dirname in packaged app)
        let backendPath = path.resolve(process.cwd(), '..', 'backend', 'thoth', 'core', 'call_assistant', 'app_v3.py');
        if (!fs.existsSync(backendPath)) {
          // Fallback: try __dirname approach
          backendPath = path.resolve(__dirname, '..', '..', 'backend', 'thoth', 'core', 'call_assistant', 'app_v3.py');
        }
        console.log('Backend script path:', backendPath);
        console.log('Backend script exists:', fs.existsSync(backendPath));

        // Start Python backend process with UTF-8 encoding
        this.process = spawn(pythonExe, [backendPath], {
          cwd: path.dirname(backendPath),
          stdio: ['inherit', 'pipe', 'pipe'],
          shell: false,
          env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
        });

        if (!this.process) {
          throw new Error('Failed to spawn backend process');
        }

        // Report spawn errors and attempt execFile fallback then shell-based fallback for ENOENT
        let triedBackendFallback = false;
        this.process.on('error', (err: any) => {
          console.error('Backend process spawn error:', err);
          this.emit('error', String(err));

          if (!triedBackendFallback && err && err.code === 'ENOENT') {
            triedBackendFallback = true;
            // First try execFile (avoids shell quoting issues)
            try {
              console.log('Attempting execFile fallback for backend');
              const child2 = execFile(pythonExe, [backendPath], { cwd: path.dirname(backendPath) });
              this.process = child2 as unknown as ChildProcess;
              child2.stdout?.on('data', (data) => {
                const message = data.toString().trim();
                if (message) {
                  console.log(`[Backend] ${message}`);
                  this.emit('log', message);
                }
              });
              child2.stderr?.on('data', (data) => {
                const message = data.toString().trim();
                if (message) {
                  console.error(`[Backend Error] ${message}`);
                  this.emit('error', message);
                }
              });
              child2.on('exit', (code) => {
                console.log(`Backend process exited with code ${code}`);
                this.isRunning = false;
                this.process = null;
                this.emit('stopped');
              });
              return;
            } catch (execErr) {
              console.error('execFile fallback failed for backend:', execErr);
              this.emit('error', String(execErr));
            }

            // Last resort: try shell-based spawn
            try {
              const cmd = `"${pythonExe}" "${backendPath}"`;
              console.log('Attempting shell fallback for backend:', cmd);
              const child3 = spawn(cmd, {
                cwd: path.dirname(backendPath),
                stdio: ['inherit', 'pipe', 'pipe'],
                shell: true,
              });
              this.process = child3;
              child3.stdout?.on('data', (data) => {
                const message = data.toString().trim();
                if (message) {
                  console.log(`[Backend] ${message}`);
                  this.emit('log', message);
                }
              });
              child3.stderr?.on('data', (data) => {
                const message = data.toString().trim();
                if (message) {
                  console.error(`[Backend Error] ${message}`);
                  this.emit('error', message);
                }
              });
              child3.on('exit', (code) => {
                console.log(`Backend process exited with code ${code}`);
                this.isRunning = false;
                this.process = null;
                this.emit('stopped');
              });
            } catch (fallbackErr) {
              console.error('Shell fallback failed for backend:', fallbackErr);
              this.emit('error', String(fallbackErr));
            }
          }
        });

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
   * Start a named Python app by script name.
   * Supported names: 'call_assistant_v3', 'odin'
   */
  async startApp(appName: string): Promise<boolean> {
    if (this.appProcesses.has(appName)) {
      console.log(`${appName} already running`);
      return true;
    }

    try {
      // Choose python executable: env, venv, or default
      let pythonExe = process.env.PYTHON_EXE || 'python';
      const _candidates = [
        path.join(process.cwd(), 'venv', 'Scripts', 'python.exe'),
        path.join(process.cwd(), 'venv', 'bin', 'python'),
        path.join(__dirname, '..', '..', 'venv', 'Scripts', 'python.exe'),
        path.join(__dirname, '..', '..', 'venv', 'bin', 'python'),
      ];
      for (const c of _candidates) {
        try {
          if (fs.existsSync(c)) {
            pythonExe = c;
            break;
          }
        } catch (_) {}
      }
      // Fallback to py launcher or unqualified python if path not found
      if ((pythonExe.includes('\\') || pythonExe.includes('/')) && !fs.existsSync(pythonExe)) {
        const fallbacks = ['py', 'py.exe', 'python', 'python3'];
        for (const fb of fallbacks) {
          try {
            const testProc = spawn(fb, ['--version'], { stdio: 'pipe', shell: false });
            let found = false;
            testProc.on('exit', (code) => {
              if (code === 0 && !found) {
                found = true;
                pythonExe = fb;
              }
            });
            testProc.on('error', () => {});
          } catch (_) {}
        }
      }
      let scriptPath = '';
      switch (appName) {
        case 'call_assistant_v3':
          scriptPath = path.resolve(__dirname, '..', '..', 'backend', 'thoth', 'core', 'call_assistant', 'app_v3.py');
          break;
        case 'odin':
          scriptPath = path.resolve(__dirname, '..', '..', 'backend', 'odin', 'app.py');
          break;
        default:
          throw new Error(`Unknown app name: ${appName}`);
      }

      console.log(`Starting app ${appName} (${scriptPath}) with python ${pythonExe}`);

      let child: ChildProcess;
      try {
        child = spawn(pythonExe, [scriptPath], {
          cwd: path.dirname(scriptPath),
          stdio: ['inherit', 'pipe', 'pipe'],
          shell: false,
          env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
        });
      } catch (err) {
        console.error('Failed to spawn child process for', appName, err);
        this.emit('error', String(err));
        return false;
      }

      let triedFallback = false;
      child.on('error', (err: any) => {
        console.error(`${appName} process spawn error:`, err);
        this.emit('error', String(err));

        if (!triedFallback && err && err.code === 'ENOENT') {
          triedFallback = true;
          // Try execFile fallback
          try {
            console.log(`Attempting execFile fallback for ${appName}`);
            const child2 = execFile(pythonExe, [scriptPath], { cwd: path.dirname(scriptPath) });
            this.appProcesses.set(appName, child2 as unknown as ChildProcess);
            (child2 as ChildProcess).stdout?.on('data', (data) => {
              const msg = data.toString().trim();
              if (msg) this.emit('log', `[${appName}] ${msg}`);
            });
            (child2 as ChildProcess).stderr?.on('data', (data) => {
              const msg = data.toString().trim();
              if (msg) this.emit('error', `[${appName}] ${msg}`);
            });
            (child2 as ChildProcess).on('exit', (code) => {
              console.log(`${appName} exited with code ${code}`);
              this.appProcesses.delete(appName);
              this.emit('stopped', appName);
            });
            return;
          } catch (execErr) {
            console.error(`execFile fallback failed for ${appName}:`, execErr);
            this.emit('error', String(execErr));
          }

          // Last resort: shell fallback
          try {
            const cmd = `"${pythonExe}" "${scriptPath}"`;
            console.log(`Attempting shell fallback for ${appName}:`, cmd);
            const child3 = spawn(cmd, {
              cwd: path.dirname(scriptPath),
              stdio: ['inherit', 'pipe', 'pipe'],
              shell: true,
            });
            this.appProcesses.set(appName, child3);
            child3.stdout?.on('data', (data) => {
              const msg = data.toString().trim();
              if (msg) this.emit('log', `[${appName}] ${msg}`);
            });
            child3.stderr?.on('data', (data) => {
              const msg = data.toString().trim();
              if (msg) this.emit('error', `[${appName}] ${msg}`);
            });
            child3.on('exit', (code) => {
              console.log(`${appName} exited with code ${code}`);
              this.appProcesses.delete(appName);
              this.emit('stopped', appName);
            });
            return;
          } catch (fallbackErr) {
            console.error(`Shell fallback for ${appName} failed:`, fallbackErr);
            this.emit('error', String(fallbackErr));
          }
        }
      });

      child.stdout?.on('data', (data) => {
        const msg = data.toString().trim();
        if (msg) this.emit('log', `[${appName}] ${msg}`);
      });

      child.stderr?.on('data', (data) => {
        const msg = data.toString().trim();
        if (msg) this.emit('error', `[${appName}] ${msg}`);
      });

      child.on('exit', (code) => {
        console.log(`${appName} exited with code ${code}`);
        this.appProcesses.delete(appName);
        this.emit('stopped', appName);
      });

      this.appProcesses.set(appName, child);
      return true;
    } catch (err) {
      console.error('Error starting app', appName, err);
      this.emit('error', String(err));
      return false;
    }
  }

  async stopApp(appName: string): Promise<boolean> {
    const child = this.appProcesses.get(appName);
    if (!child) return true;

    return new Promise((resolve) => {
      try {
        child.on('exit', () => {
          this.appProcesses.delete(appName);
          resolve(true);
        });

        // Try graceful termination
        try {
          child.kill();
        } catch (_) {
          // ignore
        }

        // Force kill after timeout
        setTimeout(() => {
          try {
            child.kill('SIGKILL');
          } catch (_) {}
          resolve(true);
        }, 5000);
      } catch (err) {
        console.error('Error stopping app', appName, err);
        resolve(false);
      }
    });
  }

  /**
   * Stop the Python Flask backend
   */
  async stop(): Promise<void> {
    if (!this.process) {
      this.isRunning = false;
      return;
    }

    return new Promise((resolve) => {
      if (this.process) {
        const proc = this.process;
        
        // Try graceful shutdown first
        const exitHandler = () => {
          this.isRunning = false;
          this.process = null;
          console.log('Backend stopped');
          resolve();
        };
        
        proc.on('exit', exitHandler);

        // Kill the process
        proc.kill();

        // Force kill after 5 seconds if still running
        setTimeout(() => {
          if (this.process === proc) {
            proc.kill('SIGKILL');
          }
          this.isRunning = false;
          this.process = null;
          resolve();
        }, 5000);
      } else {
        resolve();
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
    apps: { [name: string]: boolean };
  } {
    const appsStatus: { [name: string]: boolean } = {};
    // include known apps and whether their process exists
    ['call_assistant_v3', 'odin'].forEach((name) => {
      appsStatus[name] = this.appProcesses.has(name);
    });

    return {
      isRunning: this.isRunning,
      url: getBackendUrl(),
      apps: appsStatus,
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

  // Handle starting/stopping named apps
  ipcMain.handle(CONFIG.ipc.START_APP, async (event, appName: string) => {
    return await backend.startApp(appName);
  });

  ipcMain.handle(CONFIG.ipc.STOP_APP, async (event, appName: string) => {
    return await backend.stopApp(appName);
  });

  // Emit backend events to renderer
  backend.on('log', (message) => {
    // Send to renderer if window is available
  });

  backend.on('error', (message) => {
    // Send error to renderer
  });
}
