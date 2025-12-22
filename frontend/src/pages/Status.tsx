/**
 * Status page
 * Shows the current status of the backend and system
 */

import React from 'react';
import { useBackend } from '../hooks/useBackend';
import StatusIndicator from '../components/StatusIndicator';
import ToggleButton from '../components/ToggleButton';
import { useState } from 'react';

export function StatusPage() {
  const { status, error, isLoading } = useBackend();

  const handleToggleBackend = async () => {
    if (!window.electron) {
      alert('Electron API not available. Please run with Electron.');
      return;
    }
    
    if (status?.running) {
      // TODO: stopBackend method needs to be implemented in electron preload
      console.warn('stopBackend not yet implemented');
    } else {
      await window.electron.startBackend();
    }
  };

  // Local app controls
  const [callV3Running, setCallV3Running] = useState(false);
  const [odinRunning, setOdinRunning] = useState(false);

  // Sync local running flags with backend-reported status
  React.useEffect(() => {
    if (status?.apps) {
      setCallV3Running(!!status.apps['call_assistant_v3']);
      setOdinRunning(!!status.apps['odin']);
    }
  }, [status]);

  const toggleApp = async (name: string, running: boolean) => {
    if (!window.electron) {
      alert('Electron API not available. Please run with Electron.');
      return;
    }

    if (running) {
      await window.electron.stopApp(name);
      if (name === 'call_assistant_v3') setCallV3Running(false);
      if (name === 'odin') setOdinRunning(false);
    } else {
      await window.electron.startApp(name);
      if (name === 'call_assistant_v3') setCallV3Running(true);
      if (name === 'odin') setOdinRunning(true);
    }
  };

  return (
    <div style={{ padding: '20px', maxWidth: '800px', margin: '0 auto' }}>
      <h1>System Status</h1>

      {/* Backend Status */}
      <div
        style={{
          padding: '20px',
          marginBottom: '20px',
          border: '1px solid #ddd',
          borderRadius: '8px',
          backgroundColor: '#f8f9fa',
        }}
      >
        <h2 style={{ marginTop: 0 }}>Backend Service</h2>
        <div style={{ marginBottom: '16px' }}>
          <StatusIndicator
            status={isLoading ? 'loading' : status?.running ? 'running' : 'stopped'}
            label={isLoading ? 'Checking...' : status?.running ? 'Running' : 'Stopped'}
          />
        </div>

        {status?.url && (
          <p style={{ margin: '8px 0', color: '#666' }}>
            <strong>URL:</strong> {status.url}
          </p>
        )}

        <ToggleButton
          isActive={status?.running || false}
          onToggle={handleToggleBackend}
          disabled={isLoading}
          activeLabel="Stop Backend"
          inactiveLabel="Start Backend"
        />
      </div>

      {/* App Controls */}
      <div
        style={{
          padding: '20px',
          marginBottom: '20px',
          border: '1px solid #ddd',
          borderRadius: '8px',
          backgroundColor: '#f8f9fa',
        }}
      >
        <h2 style={{ marginTop: 0 }}>App Controls</h2>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', marginBottom: 12 }}>
          <div style={{ flex: 1 }}>
            <strong>Call Assistant V3</strong>
            <div style={{ fontSize: 12, color: '#666' }}>Starts backend/thoth/core/call_assistant/app_v3.py</div>
          </div>
          <ToggleButton
            isActive={callV3Running}
            onToggle={() => toggleApp('call_assistant_v3', callV3Running)}
            activeLabel="Stop"
            inactiveLabel="Start"
            disabled={isLoading}
          />
        </div>

        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <div style={{ flex: 1 }}>
            <strong>Odin App</strong>
            <div style={{ fontSize: 12, color: '#666' }}>Starts backend/odin/app.py</div>
          </div>
          <ToggleButton
            isActive={odinRunning}
            onToggle={() => toggleApp('odin', odinRunning)}
            activeLabel="Stop"
            inactiveLabel="Start"
            disabled={isLoading}
          />
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div
          style={{
            padding: '16px',
            marginBottom: '20px',
            backgroundColor: '#f8d7da',
            color: '#721c24',
            border: '1px solid #f5c6cb',
            borderRadius: '8px',
          }}
        >
          <h3 style={{ marginTop: 0 }}>Error</h3>
          <p style={{ margin: 0 }}>{error}</p>
        </div>
      )}

      {/* Additional Info */}
      <div
        style={{
          padding: '20px',
          border: '1px solid #ddd',
          borderRadius: '8px',
          backgroundColor: '#fff',
        }}
      >
        <h3 style={{ marginTop: 0 }}>About</h3>
        <p>Thoth is an AI-powered shift management assistant.</p>
        <p style={{ marginBottom: 0 }}>
          The backend service must be running to process shift requests and interact with
          the scheduling system.
        </p>
      </div>
    </div>
  );
}

export default StatusPage;
