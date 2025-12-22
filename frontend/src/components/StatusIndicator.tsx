/**
 * Status indicator component
 * Shows a visual indicator of status with color coding
 */

import React from 'react';

interface StatusIndicatorProps {
  status: 'running' | 'stopped' | 'loading' | 'error';
  label?: string;
}

export function StatusIndicator({ status, label }: StatusIndicatorProps) {
  const getColor = () => {
    switch (status) {
      case 'running':
        return '#28a745';
      case 'stopped':
        return '#dc3545';
      case 'loading':
        return '#ffc107';
      case 'error':
        return '#dc3545';
      default:
        return '#6c757d';
    }
  };

  const getIcon = () => {
    switch (status) {
      case 'running':
        return '✓';
      case 'stopped':
        return '✗';
      case 'loading':
        return '⟳';
      case 'error':
        return '⚠';
      default:
        return '○';
    }
  };

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '8px 12px',
        backgroundColor: getColor() + '20',
        border: `1px solid ${getColor()}`,
        borderRadius: '4px',
        fontSize: '14px',
      }}
    >
      <span
        style={{
          fontSize: '18px',
          marginRight: '8px',
          color: getColor(),
        }}
      >
        {getIcon()}
      </span>
      <span style={{ color: getColor(), fontWeight: 500 }}>
        {label || status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    </div>
  );
}

export default StatusIndicator;
