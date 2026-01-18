import React, { useState } from 'react';
import ReactDOM from 'react-dom/client';
import { ToggleButton } from './components/ToggleButton';

function App() {
  const [isRunning, setIsRunning] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  
  console.log('App component rendering...');
  
  const handleStart3CX = async () => {
    setIsLoading(true);
    console.log('Starting 3CX...');
    
    try {
      const electron = (window as any).electron;
      if (electron?.ipcInvoke) {
        await electron.ipcInvoke('start-3cx-environment');
        console.log('3CX started');
      } else {
        console.log('IPC not available');
      }
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setIsLoading(false);
    }
  };
  
  return (
    <div style={{ 
      padding: '40px',
      backgroundColor: '#282c34',
      color: 'white',
      minHeight: '100vh',
      fontSize: '24px'
    }}>
      <h1>THOTH APPLICATION</h1>
      <p>If you see this text, React is something lewl</p>
      <img src="/tray-icon.png" alt="Icon" style={{ width: '200px', marginTop: '20px' }} />
      
      <div style={{ marginTop: '40px' }}>
        <ToggleButton 
          isActive={isRunning}
          onToggle={() => setIsRunning(!isRunning)}
          activeLabel="Stop"
          inactiveLabel="Start"
        />
        <p style={{ marginTop: '20px' }}>Status: {isRunning ? 'Running' : 'Stopped'}</p>
      </div>

      <div style={{ marginTop: '40px' }}>
        <ToggleButton 
          isActive={isRunning}
          onToggle={() => setIsRunning(!isRunning)}
          activeLabel="Stop"
          inactiveLabel="Start"
        />
        <p style={{ marginTop: '20px' }}>Status: {isRunning ? 'Running' : 'Stopped'}</p>
      </div>

      <div style={{ marginTop: '40px' }}>
        <button
          onClick={handleStart3CX}
          disabled={isLoading}
          style={{
            padding: '10px 24px',
            fontSize: '14px',
            fontWeight: 500,
            border: 'none',
            borderRadius: '4px',
            cursor: isLoading ? 'not-allowed' : 'pointer',
            backgroundColor: '#007bff',
            color: 'white',
            opacity: isLoading ? 0.6 : 1,
          }}
        >
          {isLoading ? 'Loading...' : 'Start 3CX'}
        </button>
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