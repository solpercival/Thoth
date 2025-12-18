import React from 'react';

function App() {
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
    </div>
  );
}

export default App;