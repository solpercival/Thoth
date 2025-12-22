import React from 'react';
import ReactDOM from 'react-dom/client';

function App() {
  return (
    <div style={{ 
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      alignItems: 'center',
      minHeight: '100vh',
      backgroundColor: '#282c34',
      color: 'white',
      fontFamily: 'Arial, sans-serif'
    }}>
      <img src="./tray-icon.png" alt="Thoth Icon" style={{ width: '200px', height: '200px' }} />
      <h1 style={{ marginTop: '20px' }}>Thoth</h1>
      <p>AI-Powered Shift Management Assistant</p>
    </div>
  );
}

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);