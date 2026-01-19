/**
 * Main Electron process
 * Manages window creation, backend initialization, and IPC communication
 */

import {
  app,
  BrowserWindow,
  Menu,
  ipcMain,
  dialog,
} from 'electron';
import path from 'path';
import { execFile } from 'child_process';
import { CONFIG } from './config';
import { getBackendManager, setupBackendIPC } from './backend';
import { createTray } from './tray';

let mainWindow: BrowserWindow | null = null;
let backendScheduler: NodeJS.Timeout | null = null;

/**
 * Create the main application window
 */
function createWindow(): BrowserWindow {
  const window = new BrowserWindow({
    width: CONFIG.window.width,
    height: CONFIG.window.height,
    minWidth: CONFIG.window.minWidth,
    minHeight: CONFIG.window.minHeight,
    webPreferences: CONFIG.window.webPreferences,
    // In development: dist/electron/main.js -> ../../assets
    // Points to frontend/assets
    icon: path.join(__dirname, '..', '..', 'assets', 'icon.png'),
  });

  // Load the app
  const isDev = process.env.NODE_ENV === 'development';
  const url = isDev 
    ? 'http://localhost:3000'
    : `file://${path.join(__dirname, '..', '..', 'build', 'index.html')}`;
  
  console.log('Loading URL:', url);
  window.loadURL(url);

  // Open DevTools in development
  if (isDev) {
    window.webContents.openDevTools();
  }

  // Handle window closed
  window.on('closed', () => {
    mainWindow = null;
  });

  return window;
}

/**
 * Create application menu
 */
function createMenu(): void {
  const template: any[] = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Exit',
          accelerator: 'CmdOrCtrl+Q',
          click: () => {
            app.quit();
          },
        },
      ],
    },
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
      ],
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'toggleDevTools' },
      ],
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'About',
          click: () => {
            dialog.showMessageBox(mainWindow!, {
              type: 'info',
              title: 'About Thoth',
              message: 'Thoth - Shift Management Assistant',
              detail: 'Version 1.0.0\n\nAI-powered shift scheduling automation',
            });
          },
        },
      ],
    },
  ];

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

/**
 * Start the backend scheduler that checks for 11am daily
 */
function startBackendScheduler(): void {
  if (backendScheduler) {
    clearInterval(backendScheduler);
  }

  const checkAndStartBackend = async () => {
    const now = new Date();
    const hours = now.getHours();
    const minutes = now.getMinutes();
    
    // Log the current time every minute for debugging
    console.log(`[Scheduler Check] Current time: ${now.toLocaleTimeString()} (Hour: ${hours}, Minute: ${minutes})`);

    // Check if current time is between 17:00 PM and 17:59 PM
    if (hours == 17 && minutes >= 0 && minutes < 60) {
      const backend = getBackendManager();
      
      // Only start if not already running
      if (!backend.isRunning) {
        console.log(`[${now.toLocaleTimeString()}] ✓ Time is 17:00 and backend not running - Starting backend...`);
        try {
          await backend.start();
          console.log(`[${now.toLocaleTimeString()}] Backend started successfully`);
        } catch (error) {
          console.error(`[${now.toLocaleTimeString()}] Failed to start backend:`, error);
        }
      } else {
        console.log(`[${now.toLocaleTimeString()}] Time is 11am but backend already running`);
      }
    }
  };

  // Check every minute for 17:00
  backendScheduler = setInterval(checkAndStartBackend, 60000);
  
  // Also check immediately in case it's already 17:00
  checkAndStartBackend();

  console.log('Backend scheduler started - will start backend at 11:00 AM daily');
}

/**
 * Initialize the application
 */
async function initializeApp(): Promise<void> {
  // Create main window first
  mainWindow = createWindow();
  
  // Setup IPC handlers for backend management
  setupBackendIPC(mainWindow);

  createMenu();
  const trayIcon = createTray(mainWindow);
  if (!trayIcon) {
    console.log('Running without system tray icon');
  }

  // Start the backend scheduler - will auto-start at 17:00
  startBackendScheduler();
  
  console.log('Electron app initialized - Backend will start automatically at 17:00 PM');
}

/**
 * App lifecycle events
 */

// Handle 3CX environment startup
ipcMain.handle('start-3cx-environment', async (event) => {
  return new Promise((resolve, reject) => {
    const scriptPath = path.join(__dirname, '../../../scripts/start_3cx_environment.sh');
    
    console.log(`[3CX] Starting environment with script: ${scriptPath}`);
    
    execFile('bash', [scriptPath], { shell: '/bin/bash' }, (error, stdout, stderr) => {
      if (error) {
        console.error('[3CX] Script error:', error);
        reject({
          error: error.message,
          stderr: stderr,
        });
      } else {
        console.log('[3CX] Script completed successfully');
        console.log('[3CX] Output:', stdout);
        resolve({
          success: true,
          message: 'Environment started successfully',
          output: stdout,
        });
      }
    });
  });
});

/**
 * App lifecycle events
 */

// When Electron has finished initialization
app.on('ready', () => {
  initializeApp();
});

// Quit when all windows are closed
// On Windows/Linux, keep app running to maintain 5pm scheduler
app.on('window-all-closed', async () => {
  // Don't quit - keep the app running in background
  // The scheduler will continue to run at 5pm
  if (process.platform === 'darwin') {
    // Only auto-quit on macOS if user explicitly quits
    app.quit();
  }
  // On Windows/Linux, the app stays running
});

// On macOS, re-create window when dock icon is clicked
app.on('activate', async () => {
  if (mainWindow === null) {
    mainWindow = createWindow();
  }
});

// Handle app quit requests from renderer
ipcMain.handle(CONFIG.ipc.APP_QUIT, async () => {
  const backend = getBackendManager();
  await backend.stop();
  app.quit();
});

// Handle show error dialog requests
ipcMain.handle(
  CONFIG.ipc.SHOW_ERROR,
  (event, { title, message }) => {
    if (mainWindow) {
      dialog.showErrorBox(title, message);
    }
  }
);

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
  if (mainWindow) {
    dialog.showErrorBox('Error', 'An unexpected error occurred');
  }
});

export { mainWindow };
