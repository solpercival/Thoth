# Thoth Frontend Guide

## Overview

The Thoth frontend is an Electron + React application that provides a desktop interface for the shift management system.

## Project Structure

```
frontend/
├── electron/          # Electron main process
│   ├── main.ts       # Application entry point
│   ├── backend.ts    # Python backend manager
│   ├── config.ts     # Configurationgi
│   ├── preload.ts    # IPC bridge
│   └── tray.ts       # System tray
├── src/              # React application
│   ├── index.tsx     # React entry point
│   ├── components/   # UI components
│   ├── pages/        # Page components
│   ├── hooks/        # Custom React hooks
│   ├── services/     # API services
│   └── types/        # TypeScript definitions
├── assets/           # Static assets (icons, images)
├── public/           # Public files (HTML, static assets)
└── build/            # Production build output
```

## Development

### Quick Start

1. **Install dependencies:**
   ```bash
   cd frontend
   npm install
   ```

2. **Build and run:**
   ```bash
   npm run build           # Build React app
   npm run build:electron  # Compile TypeScript for Electron
   npm run electron        # Start Electron app
   ```

### Development Mode

For development with hot reload:
```bash
npm run electron-dev    # Starts React dev server + Electron
```

## Available Scripts

- `npm start` - Start React development server
- `npm run build` - Build React app for production
- `npm run build:electron` - Compile Electron TypeScript files
- `npm run electron` - Run Electron app (production mode)
- `npm run electron-dev` - Run in development mode with hot reload
- `npm run electron-build` - Build distributable Electron app

## Architecture

### Electron Main Process

- **main.ts**: Creates the application window, manages lifecycle
- **backend.ts**: Spawns and manages the Python Flask backend process
- **config.ts**: Centralized configuration
- **preload.ts**: Secure bridge between Electron and React (exposes `window.electron` API)
- **tray.ts**: System tray integration

### React Renderer Process

- **index.tsx**: Main React entry point with the App component
- **components/**: Reusable UI components
- **pages/**: Full page components (Status, Settings)
- **hooks/**: Custom React hooks (useBackend for API communication)
- **services/**: API service layer
- **types/**: TypeScript type definitions

## Backend Integration

The frontend automatically starts the Python Flask backend located at:
```
../backend/core/call_assistant/app.py
```

The backend runs on port 5000 and provides REST API endpoints.

### Using the Backend

The `useBackend` hook provides easy access to backend functionality:

```tsx
import { useBackend } from '../hooks/useBackend';

function MyComponent() {
  const { status, error, isLoading } = useBackend();
  
  return (
    <div>
      <p>Backend Status: {status?.running ? 'Running' : 'Stopped'}</p>
    </div>
  );
}
```

## Current Status

### ✅ Completed
- Project structure reorganized (removed duplicate renderer/ folder)
- All components consolidated into src/
- Basic UI displaying Thoth icon and title
- Electron app successfully launches and displays UI
- Backend manager configured to start Flask app
- Production build system working

### ⚠️ Known Issues
- Backend requires Python dependencies (pyttsx3, numpy, flask, etc.)
- Some TypeScript errors for window.electron API (non-blocking)

### 🔧 Next Steps
- Install Python dependencies for backend
- Implement full UI with backend controls
- Add proper error handling and user feedback
- Create more complete page components

## Troubleshooting

### Blank white page
- Ensure React build completed successfully (`npm run build`)
- Check that assets (images) are copied to build folder
- Verify JavaScript bundle is not empty (check build/static/js/)

### Backend won't start
- Install Python dependencies: `pip install pyttsx3 flask numpy`
- Verify backend path in electron/backend.ts
- Check Python is available in PATH

### TypeScript errors
- Run `npm run build:electron` to see compilation errors
- Check tsconfig files are properly configured
