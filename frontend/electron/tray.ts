/**
 * System tray integration
 * Show/hide app window from system tray
 */

import { BrowserWindow, Menu, Tray, app } from 'electron';
import path from 'path';

let tray: Tray | null = null;

export function createTray(window: BrowserWindow): Tray | null {
  // In development: dist/electron/tray.js -> ../../assets
  // Points to frontend/assets
  const iconPath = path.join(__dirname, '..', '..', 'assets', 'tray-icon.png');
  
  // Check if icon exists
  try {
    const fs = require('fs');
    if (!fs.existsSync(iconPath)) {
      console.log('Tray icon not found at:', iconPath);
      return null;
    }
  } catch (e) {
    console.log('Could not check for tray icon:', e);
    return null;
  }
  
  tray = new Tray(iconPath);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show',
      click: () => {
        window.show();
        window.focus();
      },
    },
    {
      label: 'Hide',
      click: () => {
        window.hide();
      },
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        app.quit();
      },
    },
  ]);

  tray.setContextMenu(contextMenu);

  // Toggle window on tray icon click
  tray.on('click', () => {
    if (window.isVisible()) {
      window.hide();
    } else {
      window.show();
      window.focus();
    }
  });

  // Handle window minimize to tray
  window.on('minimize', () => {
    window.hide();
  });

  return tray;
}

export function destroyTray(): void {
  if (tray) {
    tray.destroy();
    tray = null;
  }
}
