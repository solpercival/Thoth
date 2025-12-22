# Thoth Desktop App - Architecture Guide

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER MACHINE                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │         ELECTRON APPLICATION (main.ts)                  │   │
│  │  ┌────────────────────────────────────────────────────┐ │   │
│  │  │  Main Process                                       │ │   │
│  │  │  • Window management                               │ │   │
│  │  │  • Menu creation                                   │ │   │
│  │  │  • IPC handlers                                    │ │   │
│  │  │  • App lifecycle                                   │ │   │
│  │  └────────────────────────────────────────────────────┘ │   │
│  │                        ↕ IPC                               │   │
│  │  ┌────────────────────────────────────────────────────┐ │   │
│  │  │  Backend Manager (backend.ts)                       │ │   │
│  │  │  • Launch Python Flask process                      │ │   │
│  │  │  • Monitor Flask stdout/stderr                      │ │   │
│  │  │  • Provide HTTP client for API calls                │ │   │
│  │  │  • Health check & readiness probes                  │ │   │
│  │  │  • Graceful shutdown                                │ │   │
│  │  └────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                           ↕ IPC                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │         RENDERER PROCESS (React App)                    │   │
│  │  ┌────────────────────────────────────────────────────┐ │   │
│  │  │  Preload Script (preload.ts)                        │ │   │
│  │  │  • Secure IPC bridge                                │ │   │
│  │  │  • Context isolation                                │ │   │
│  │  │  • window.electron API                              │ │   │
│  │  └────────────────────────────────────────────────────┘ │   │
│  │                        ↕ window.electron                    │   │
│  │  ┌────────────────────────────────────────────────────┐ │   │
│  │  │  React Components & Pages                           │ │   │
│  │  │  • Status.tsx - Shift status display                │ │   │
│  │  │  • Settings.tsx - App settings                      │ │   │
│  │  │  • useBackend() hook - API communication            │ │   │
│  │  │  • Error boundaries & loading states                │ │   │
│  │  └────────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │         PYTHON FLASK BACKEND                             │   │
│  │  Child process started by Electron Main                  │   │
│  │  • HTTP Server on localhost:5000                         │   │
│  │  • /health - Health check endpoint                       │   │
│  │  • /api/shifts - Get staff shifts                        │   │
│  │  • /api/shifts/cancel - Cancel shift                     │   │
│  │  • /api/shifts/book - Book shift                         │   │
│  │  • /api/... - Additional endpoints                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│           ↓ HTTP Requests                                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │         EXTERNAL SERVICES                                │   │
│  │  • Playwright (Browser automation)                       │   │
│  │  • Ollama LLM (Date reasoning)                           │   │
│  │  • Ezaango Website (Staff/shift data)                    │   │
│  │  • Email Service (Notifications)                         │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Example: User Wants to Cancel a Shift

1. **User Input** → React Component
   ```
   User enters phone number and clicks "Get Shifts"
   ```

2. **API Request** → useBackend Hook
   ```typescript
   const { api } = useBackend();
   await api('POST', '/api/shifts', { phone_number: '0490024573' });
   ```

3. **IPC Communication** → Preload Script
   ```
   window.electron.apiRequest(...)
   → ipcRenderer.invoke('api:request', ...)
   ```

4. **Main Process Handler** → Backend Manager
   ```typescript
   ipcMain.handle('api:request', async (event, { method, endpoint, data }) => {
     return backend.api(method, endpoint, data);
   });
   ```

5. **HTTP Request** → Flask Backend
   ```
   POST http://localhost:5000/api/shifts
   {
     "phone_number": "0490024573"
   }
   ```

6. **Flask Processing** → Playwright Automation
   ```python
   # Flask receives request
   # Authenticates user
   # Uses Playwright to navigate Ezaango website
   # Finds shifts for the phone number
   # Returns shift data as JSON
   ```

7. **Response** → React Component
   ```javascript
   {
     "success": true,
     "data": {
       "shifts": [
         {
           "id": "shift-123",
           "client": "Acme Corp",
           "date": "19-12-2025",
           "time": "9:00 AM"
         }
       ]
     }
   }
   ```

8. **UI Update** → User Sees Results
   ```
   Component displays list of shifts
   User can click "Cancel" on any shift
   ```

## Component Responsibilities

### Electron Main Process (main.ts)
- ✓ Window lifecycle management
- ✓ Application menu creation
- ✓ IPC handler setup
- ✓ Backend initialization
- ✓ Error handling & dialogs
- ✓ System tray integration

### Backend Manager (backend.ts)
- ✓ Spawn Python child process
- ✓ Monitor process output
- ✓ Health check/readiness probes
- ✓ HTTP API bridge (Axios)
- ✓ Graceful shutdown
- ✓ Error recovery

### Configuration (config.ts)
- ✓ Port numbers
- ✓ IPC channel names
- ✓ File paths
- ✓ Window settings
- ✓ Environment constants

### Preload Script (preload.ts)
- ✓ Expose safe IPC bridge
- ✓ Context isolation
- ✓ window.electron API definition
- ✓ Type definitions for TypeScript

### React Hook (useBackend.ts)
- ✓ Initialize backend on mount
- ✓ Provide api() function
- ✓ Track loading/error states
- ✓ Handle API responses
- ✓ Provide helper methods

### React Components
- ✓ Use useBackend() hook
- ✓ Display data from backend
- ✓ Show loading states
- ✓ Handle errors
- ✓ Submit user input

## Communication Patterns

### 1. Direct IPC Call (No Response)
```typescript
// Example: Quit application
await window.electron.quitApp();
```

### 2. IPC with Response
```typescript
// Example: Get status
const status = await window.electron.getBackendStatus();
// Returns: { isRunning: true, url: "http://localhost:5000" }
```

### 3. Event Listener
```typescript
// Example: Listen for backend logs
window.electron.onBackendLog((message) => {
  console.log('[Backend]', message);
});
```

### 4. API Request
```typescript
// Example: Make HTTP request to backend
const response = await window.electron.apiRequest(
  'POST',
  '/api/shifts',
  { phone_number: '0490024573' }
);
// Returns: { success: true, data: {...} } or { success: false, error: "..." }
```

## Security Considerations

### Context Isolation
- ✓ Main process and renderer process are isolated
- ✓ Renderer cannot directly access Node.js APIs
- ✓ All communication goes through preload script

### Preload Script
- ✓ Only exposes safe methods
- ✓ Validates all input/output
- ✓ Prevents arbitrary code execution

### IPC Channels
- ✓ Named channels (not arbitrary messages)
- ✓ Type-safe (typed parameters)
- ✓ Whitelist of allowed operations

### Backend Communication
- ✓ Only talks to localhost (no external APIs)
- ✓ Can add authentication tokens if needed
- ✓ All data validated in Flask backend

## Error Handling Strategy

### Backend Startup Failure
```
[Electron] → Start Backend
  ↓ (times out after 10 seconds)
[Error] Backend failed to start
  ↓
[User] Dialog: "Failed to start backend service"
  ↓
[Option 1] Retry
[Option 2] Show system requirements
[Option 3] Exit app
```

### API Request Failure
```
[React] → Make API call
  ↓ (request fails)
[Error] API returns { success: false, error: "..." }
  ↓
[Component] Display error message to user
  ↓
[Option 1] Retry request
[Option 2] Try different action
[Option 3] Show help/support
```

### Network Connection Loss
```
[Component] → Makes API call
  ↓ (Flask not responding)
[Error] HTTP timeout (5 seconds)
  ↓
[Hook] Returns error state
  ↓
[Component] Shows "Connection lost" message
  ↓
[Option 1] Show reconnect button
[Option 2] Auto-retry with exponential backoff
[Option 3] Queue requests for retry when online
```

## Deployment & Distribution

### Development
```bash
npm run electron-dev
# Starts React dev server + Electron with hot reload
```

### Production Build
```bash
npm run electron-build
# 1. Build React: npm run build
# 2. Create executables using electron-builder
# 3. Output: dist/Thoth-1.0.0.exe (Windows)
#           dist/Thoth-1.0.0.dmg (macOS)
#           dist/thoth_1.0.0_amd64.deb (Linux)
```

### Bundling Python
For production, bundle Python with the app:
```bash
pyinstaller --onefile --windowed backend/core/main.py
```

Then update config.ts:
```typescript
python: {
  executable: path.join(app.getAppPath(), 'python', 'main.exe')
}
```

## Testing Strategy

### Unit Tests
- Test React components with React Testing Library
- Test utilities and hooks
- Mock backend calls with jest

### Integration Tests
- Test IPC communication
- Test backend startup/shutdown
- Test API requests end-to-end

### E2E Tests
- Test full user workflows
- Test frontend ↔ backend communication
- Use Spectron (Electron testing framework)

## Performance Optimization

### Lazy Loading
```typescript
const Settings = React.lazy(() => import('./pages/Settings'));
```

### Code Splitting
```typescript
// webpack will automatically split code at route boundaries
```

### Memoization
```typescript
const Component = React.memo(MyComponent);
```

### Backend Optimization
- Cache authentication tokens
- Minimize browser automation calls
- Use connection pooling for APIs

## Future Enhancements

1. **Offline Mode**
   - Cache shift data locally (SQLite)
   - Queue actions while offline
   - Sync when connection restored

2. **Analytics**
   - Track feature usage
   - Monitor error rates
   - Performance metrics

3. **Updates**
   - Auto-update mechanism
   - Electron-updater integration
   - Delta updates for smaller downloads

4. **Multi-language Support**
   - i18n framework (react-i18next)
   - Support multiple languages

5. **Advanced Features**
   - Dark mode theme
   - Custom shortcuts
   - Notification center
   - Settings persistence
