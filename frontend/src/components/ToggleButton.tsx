/**
 * Toggle button component
 * A styled button for toggling between two states
 */

import React from 'react';

interface ToggleButtonProps {
  isActive: boolean;
  onToggle: () => void;
  activeLabel?: string;
  inactiveLabel?: string;
  disabled?: boolean;
}

export function ToggleButton({
  isActive,
  onToggle,
  activeLabel = 'Stop',
  inactiveLabel = 'Start',
  disabled = false,
}: ToggleButtonProps) {
  return (
    <button
      onClick={onToggle}
      disabled={disabled}
      style={{
        padding: '10px 24px',
        fontSize: '14px',
        fontWeight: 500,
        border: 'none',
        borderRadius: '4px',
        cursor: disabled ? 'not-allowed' : 'pointer',
        backgroundColor: isActive ? '#dc3545' : '#28a745',
        color: 'white',
        opacity: disabled ? 0.6 : 1,
        transition: 'all 0.2s ease',
      }}
      onMouseEnter={(e) => {
        if (!disabled) {
          e.currentTarget.style.opacity = '0.9';
        }
      }}
      onMouseLeave={(e) => {
        if (!disabled) {
          e.currentTarget.style.opacity = '1';
        }
      }}
    >
      {isActive ? activeLabel : inactiveLabel}
    </button>
  );
}

export default ToggleButton;
