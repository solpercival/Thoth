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
import { CONFIG } from './config';
import { getBackendManager, setupBackendIPC } from './backend';
import { createTray } from './tray';

let mainWindow: BrowserWindow | null = null;

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
 * Initialize the application
 */
async function initializeApp(): Promise<void> {
  // Setup IPC handlers for backend management
  setupBackendIPC();

  // Create main window
  mainWindow = createWindow();
  createMenu();
  const trayIcon = createTray(mainWindow);
  if (!trayIcon) {
    console.log('Running without system tray icon');
  }

  // Start backend automatically (optional for now)
  try {
    const backend = getBackendManager();
    const started = await backend.start();

    if (!started) {
      console.log('Backend failed to start - you can start it manually from the UI');
      // Don't show error dialog, just log it
    } else {
      console.log('Backend started successfully');
    }
  } catch (error) {
    console.log('Backend startup error (non-fatal):', error);
  }
}

/**
 * App lifecycle events
 */

// When Electron has finished initialization
app.on('ready', () => {
  initializeApp();
});

// Quit when all windows are closed
app.on('window-all-closed', async () => {
  const backend = getBackendManager();
  await backend.stop();

  // On macOS, apps stay active until the user quits explicitly
  if (process.platform !== 'darwin') {
    app.quit();
  }
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
