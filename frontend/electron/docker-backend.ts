/**
 * Docker Backend Manager
 * Manages the backend using Docker containers instead of direct Python execution
 */

import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';
import axios, { AxiosInstance } from 'axios';

export class DockerBackendManager extends EventEmitter {
  private container: ChildProcess | null = null;
  public isRunning: boolean = false;
  private httpClient: AxiosInstance;
  private platform: string = process.platform;

  constructor() {
    super();
    this.httpClient = axios.create({
      baseURL: 'http://localhost:5000',
      timeout: 5000,
    });
  }

  /**
   * Start the Docker backend
   */
  async start(): Promise<boolean> {
    if (this.isRunning) {
      console.log('Docker backend already running');
      return true;
    }

    return new Promise((resolve) => {
      try {
        console.log('Starting Docker backend...');
        
        // Get the backend directory relative to frontend
        const backendDir = `${process.cwd()}/../backend`;
        
        // Use docker-compose to start the backend
        const command = this.platform === 'win32' ? 'docker-compose.exe' : 'docker-compose';
        
        this.container = spawn(command, ['up', '--build'], {
          cwd: backendDir,
          stdio: ['inherit', 'pipe', 'pipe'],
          shell: true,
        });

        if (!this.container) {
          throw new Error('Failed to spawn Docker process');
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

        // Wait for container to be healthy
        setTimeout(() => {
          this.isRunning = true;
          console.log('Docker backend started');
          resolve(true);
        }, 5000);

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
        
        const backendDir = `${process.cwd()}/../backend`;
        const command = this.platform === 'win32' ? 'docker-compose.exe' : 'docker-compose';
        
        const stopProcess = spawn(command, ['down'], {
          cwd: backendDir,
          stdio: 'pipe',
          shell: true,
        });

        stopProcess.on('exit', (code) => {
          console.log(`Docker stop command exited with code ${code}`);
          this.isRunning = false;
          resolve(code === 0);
        });

        stopProcess.on('error', (err) => {
          console.error('Error stopping Docker:', err);
          resolve(false);
        });

        // If container doesn't stop after 10 seconds, kill it
        setTimeout(() => {
          if (this.container) {
            console.log('Force killing Docker container');
            this.container.kill('SIGKILL');
          }
        }, 10000);
      } catch (err) {
        console.error('Error stopping Docker:', err);
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
      const response = await this.httpClient.get('/health');
      return { isRunning: true, ...response.data };
    } catch (err) {
      console.log('Backend health check failed:', err);
      return { isRunning: false };
    }
  }
}

export default DockerBackendManager;
