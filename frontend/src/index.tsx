import React, { useState, useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import { ToggleButton } from './components/ToggleButton';

function App() {
  const [isRunning, setIsRunning] = useState(false);
  const [status, setStatus] = useState('Stopped');
  const [error, setError] = useState<string | null>(null);
  const [is3CXLoading, setIs3CXLoading] = useState(false);
  const [status3CX, setStatus3CX] = useState<string | null>(null);

  useEffect(() => {
    // Listen for backend status changes
    if (window.electron?.onBackendStatusChange) {
      window.electron.onBackendStatusChange((status: any) => {
        console.log('Backend status updated:', status);
        setIsRunning(status.isRunning || false);
        setStatus(status.isRunning ? 'Running' : 'Stopped');
      });
    }

    // Listen for backend errors if electron API is available
    if (window.electron?.onBackendError) {
      window.electron.onBackendError((err: string) => {
        setError(err);
        setIsRunning(false);
        setStatus('Error');
      });
    }

    // Initial status check
    if (window.electron?.getBackendStatus) {
      window.electron.getBackendStatus().then((status: any) => {
        console.log('Initial backend status:', status);
        setIsRunning(status.isRunning || false);
        setStatus(status.isRunning ? 'Running' : 'Stopped');
      });
    }

    return () => {
      if (window.electron?.removeBackendStatusChangeListener) {
        window.electron.removeBackendStatusChangeListener();
      }
    };
  }, []);

  const handleToggle = async () => {
    try {
      setError(null);
      if (!isRunning) {
        // Start backend
        setStatus('Starting...');
        await window.electron?.startBackend?.();
        
        // Poll for status until it's actually running
        let attempts = 0;
        const maxAttempts = 30;
        while (attempts < maxAttempts) {
          await new Promise(r => setTimeout(r, 500)); // Wait 500ms between checks
          const status = await window.electron?.getBackendStatus?.();
          console.log(`Status check ${attempts + 1}: ${JSON.stringify(status)}`);
          
          if (status?.isRunning) {
            setIsRunning(true);
            setStatus('Running');
            return;
          }
          attempts++;
        }
        
        // If we get here, timeout - but backend might still be starting
        setStatus('Running (delayed startup)');
        setIsRunning(true);
      } else {
        // Stop backend
        setStatus('Stopping...');
        await window.electron?.stopBackend?.();
        
        // Poll for status until it's actually stopped
        let attempts = 0;
        const maxAttempts = 10;
        while (attempts < maxAttempts) {
          await new Promise(r => setTimeout(r, 500));
          const status = await window.electron?.getBackendStatus?.();
          console.log(`Stop check ${attempts + 1}: ${JSON.stringify(status)}`);
          
          if (!status?.isRunning) {
            setIsRunning(false);
            setStatus('Stopped');
            return;
          }
          attempts++;
        }
        
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

  const handleStart3CX = async () => {
    setIs3CXLoading(true);
    setStatus3CX('Starting 3CX environment...');
    
    try {
      const electron = (window as any).electron;
      if (electron?.ipcInvoke) {
        const result = await electron.ipcInvoke('start-3cx-environment');
        setStatus3CX('✓ 3CX environment started!');
        console.log('3CX result:', result);
      } else {
        setStatus3CX('✗ IPC not available');
      }
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : String(err);
      setStatus3CX(`✗ Error: ${errorMsg}`);
      console.error('Error starting 3CX:', err);
    } finally {
      setIs3CXLoading(false);
    }
  };

  console.log('App component rendering...');
  
  return (
    <div style={{ 
      padding: '40px',
      backgroundColor: '#282c34',  // #282c34
      color: 'white',
      minHeight: '100vh',
      fontSize: '24px',
      width: '100%',
      // Centering part
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      textAlign: 'center'
    }}>
      <h1>HAHS AI POWERED CALL ASSISTANT</h1>
      <p>Welcome to the dashboard!</p>
      <img src="./hahs_logo.png" alt="Icon" style={{ width: '200px', marginTop: '20px' }} />
      
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

      <div style={{ marginTop: '40px', borderTop: '1px solid #555', paddingTop: '20px' }}>
        <h2>3CX Environment</h2>
        <button
          onClick={handleStart3CX}
          disabled={is3CXLoading}
          style={{
            padding: '10px 24px',
            fontSize: '14px',
            fontWeight: 500,
            border: 'none',
            borderRadius: '4px',
            cursor: is3CXLoading ? 'not-allowed' : 'pointer',
            backgroundColor: '#007bff',
            color: 'white',
            opacity: is3CXLoading ? 0.6 : 1,
          }}
        >
          {is3CXLoading ? 'Starting...' : 'Start 3CX Environment'}
        </button>
        {status3CX && (
          <p style={{ marginTop: '15px', color: status3CX.includes('✓') ? '#28a745' : '#ff6b6b' }}>
            {status3CX}
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