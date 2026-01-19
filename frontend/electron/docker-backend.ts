/**
 * Docker Backend Manager
 * Manages the backend using Docker containers via `docker compose`
 */

import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';
import axios, { AxiosInstance } from 'axios';

export class DockerBackendManager extends EventEmitter {
  private container: ChildProcess | null = null;
  public isRunning: boolean = false;
  private httpClient: AxiosInstance;

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

        const backendDir = `${process.cwd()}/../backend`;

        // Always: docker compose up --build
        this.container = spawn(
          'docker',
          ['compose', 'up', '--build'],
          {
            cwd: backendDir,
            stdio: ['inherit', 'pipe', 'pipe'],
            shell: false,
          }
        );

        if (!this.container) {
          throw new Error('Failed to spawn Docker process');
        }

        // STDOUT
        this.container.stdout?.on('data', (data) => {
          const message = data.toString().trim();
          if (message) {
            console.log(`[Docker Backend] ${message}`);
            this.emit('log', message);
          }
        });

        // STDERR
        this.container.stderr?.on('data', (data) => {
          const message = data.toString().trim();
          if (message) {
            console.log(`[Docker Backend stderr] ${message}`);
            this.emit('log', message);
          }
        });

        // Mark as running after 5 seconds
        setTimeout(() => {
          this.isRunning = true;
          console.log('Docker backend started');
          resolve(true);
        }, 5000);

        // Process closed
        this.container.on('exit', (code) => {
          console.log(`Docker compose exited with code ${code}`);
          this.isRunning = false;
          this.container = null;
          this.emit('stopped');
        });

        this.container.on('error', (err) => {
          console.error('Docker compose process error:', err);
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

        // Proper: docker compose down
        const stopProcess = spawn(
          'docker',
          ['compose', 'down'],
          {
            cwd: backendDir,
            stdio: ['pipe', 'pipe', 'pipe'],
            shell: false,
          }
        );

        stopProcess.on('exit', (code) => {
          console.log(`Docker stop exited with code ${code}`);
          this.isRunning = false;
          resolve(code === 0);
        });

        stopProcess.on('error', (err) => {
          console.error('Error stopping Docker:', err);
          resolve(false);
        });

        // Kill hanging "up" process if needed
        setTimeout(() => {
          if (this.container) {
            console.log('Force killing docker compose up process');
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
