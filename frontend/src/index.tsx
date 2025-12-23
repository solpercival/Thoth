import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import { ToggleButton } from './components/ToggleButton';

function App() {
  const [isRunning, setIsRunning] = useState(false);
  const [status, setStatus] = useState('Stopped');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // Listen for backend errors if electron API is available
    if (window.electron?.onBackendError) {
      window.electron.onBackendError((err: string) => {
        setError(err);
        setIsRunning(false);
        setStatus('Error');
      });
    }
  }, []);

  const handleToggle = async () => {
    try {
      setError(null);
      if (!isRunning) {
        // Start backend
        setStatus('Starting...');
        await window.electron?.startBackend?.();
        setIsRunning(true);
        setStatus('Running');
      } else {
        // Stop backend
        setStatus('Stopping...');
        await window.electron?.stopBackend?.();
        setIsRunning(false);
        setStatus('Stopped');
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      setError(errorMsg);
      setStatus('Error');
      setIsRunning(false);
    }
  };

  console.log('App component rendering...');
  
  return (
    <div style={{ 
      padding: '40px',
      backgroundColor: '#282c34',
      color: 'white',
      minHeight: '100vh',
      fontSize: '24px'
    }}>
      <h1>THOTH APPLICATION</h1>
      <p>If you see this text, React is working!</p>
      <img src="./tray-icon.png" alt="Icon" style={{ width: '200px', marginTop: '20px' }} />
      
      <div style={{ marginTop: '40px' }}>
        <ToggleButton 
          isActive={isRunning}
          onToggle={handleToggle}
          activeLabel="Stop"
          inactiveLabel="Start"
        />
        <p style={{ marginTop: '20px' }}>Status: {status}</p>
        {error && (
          <p style={{ marginTop: '10px', color: '#ff6b6b' }}>
            Error: {error}
          </p>
        )}
      </div>
    </div>
  );
}

// Bootstrap React
const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);