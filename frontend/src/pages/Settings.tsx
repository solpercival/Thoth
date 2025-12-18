/**
 * Settings page
 * Configure application preferences and options
 */

import React, { useState } from 'react';

export function SettingsPage() {
  const [autoStart, setAutoStart] = useState(false);
  const [notifications, setNotifications] = useState(true);
  const [theme, setTheme] = useState<'light' | 'dark'>('light');

  const handleSave = () => {
    // TODO: Implement settings persistence
    alert('Settings saved!');
  };

  return (
    <div style={{ padding: '20px', maxWidth: '800px', margin: '0 auto' }}>
      <h1>Settings</h1>

      {/* General Settings */}
      <div
        style={{
          padding: '20px',
          marginBottom: '20px',
          border: '1px solid #ddd',
          borderRadius: '8px',
          backgroundColor: '#f8f9fa',
        }}
      >
        <h2 style={{ marginTop: 0 }}>General</h2>

        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={autoStart}
              onChange={(e) => setAutoStart(e.target.checked)}
              style={{ marginRight: '8px' }}
            />
            <span>Start backend automatically on app launch</span>
          </label>
        </div>

        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'flex', alignItems: 'center', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={notifications}
              onChange={(e) => setNotifications(e.target.checked)}
              style={{ marginRight: '8px' }}
            />
            <span>Enable notifications</span>
          </label>
        </div>

        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', marginBottom: '8px' }}>
            <strong>Theme:</strong>
          </label>
          <select
            value={theme}
            onChange={(e) => setTheme(e.target.value as 'light' | 'dark')}
            style={{
              padding: '8px',
              borderRadius: '4px',
              border: '1px solid #ccc',
              fontSize: '14px',
            }}
          >
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </div>
      </div>

      {/* Backend Settings */}
      <div
        style={{
          padding: '20px',
          marginBottom: '20px',
          border: '1px solid #ddd',
          borderRadius: '8px',
          backgroundColor: '#f8f9fa',
        }}
      >
        <h2 style={{ marginTop: 0 }}>Backend Configuration</h2>
        <p style={{ color: '#666', fontSize: '14px' }}>
          Advanced settings for the backend service. Changes require restart.
        </p>

        <div style={{ marginBottom: '16px' }}>
          <label style={{ display: 'block', marginBottom: '8px' }}>
            <strong>Backend Port:</strong>
          </label>
          <input
            type="number"
            defaultValue={8000}
            style={{
              padding: '8px',
              borderRadius: '4px',
              border: '1px solid #ccc',
              fontSize: '14px',
              width: '100px',
            }}
          />
        </div>
      </div>

      {/* Save Button */}
      <button
        onClick={handleSave}
        style={{
          padding: '12px 24px',
          fontSize: '14px',
          fontWeight: 500,
          border: 'none',
          borderRadius: '4px',
          cursor: 'pointer',
          backgroundColor: '#007bff',
          color: 'white',
        }}
      >
        Save Settings
      </button>
    </div>
  );
}

export default SettingsPage;
