import React, { useState } from 'react';
import ReactDOM from 'react-dom/client';
import { ToggleButton } from './components/ToggleButton';

function App() {
  const [isRunning, setIsRunning] = useState(false);
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