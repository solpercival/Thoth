/**
 * Example React component showing backend integration
 * This demonstrates how to use the Electron IPC bridge
 */

import React, { useState } from 'react';
import { useBackend } from '../hooks/useBackend';

export function BackendStatusExample() {
  const { api, status, error, isLoading } = useBackend();
  const [phoneNumber, setPhoneNumber] = useState('');
  const [shifts, setShifts] = useState<any[]>([]);

  const handleFetchShifts = async (e: React.FormEvent) => {
    e.preventDefault();
    const response = await api('POST', '/api/shifts', {
      phone_number: phoneNumber,
    });

    if (response.success) {
      setShifts(response.data.shifts || []);
    }
  };

  return (
    <div style={{ padding: '20px' }}>
      <h1>Backend Status</h1>

      {/* Status Section */}
      <div
        style={{
          padding: '10px',
          marginBottom: '20px',
          backgroundColor: status?.running ? '#d4edda' : '#f8d7da',
          border: '1px solid #ccc',
          borderRadius: '4px',
        }}
      >
        <strong>Backend Status:</strong> {status?.running ? '✓ Running' : '✗ Stopped'}
        <br />
        <small>URL: {status?.url}</small>
      </div>

      {/* Error Display */}
      {error && (
        <div
          style={{
            padding: '10px',
            marginBottom: '20px',
            backgroundColor: '#f8d7da',
            color: '#721c24',
            border: '1px solid #f5c6cb',
            borderRadius: '4px',
          }}
        >
          <strong>Error:</strong> {error}
        </div>
      )}

      {/* API Test Form */}
      <form onSubmit={handleFetchShifts}>
        <h2>Test API Request</h2>
        <div>
          <label>
            Phone Number:
            <input
              type="text"
              value={phoneNumber}
              onChange={(e) => setPhoneNumber(e.target.value)}
              placeholder="e.g., 0490024573"
              style={{ marginLeft: '10px', padding: '5px' }}
            />
          </label>
        </div>
        <button
          type="submit"
          disabled={isLoading}
          style={{
            marginTop: '10px',
            padding: '8px 16px',
            backgroundColor: '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: isLoading ? 'not-allowed' : 'pointer',
          }}
        >
          {isLoading ? 'Loading...' : 'Fetch Shifts'}
        </button>
      </form>

      {/* Results */}
      {shifts.length > 0 && (
        <div style={{ marginTop: '20px' }}>
          <h3>Shifts ({shifts.length})</h3>
          <ul>
            {shifts.map((shift, index) => (
              <li key={index}>
                {shift.client} - {shift.date} at {shift.time}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default BackendStatusExample;
