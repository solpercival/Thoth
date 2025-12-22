/**
 * Hook for secure backend API communication
 * Usage: const { api, status, error } = useBackend();
 */

import { useState, useCallback, useEffect } from 'react';
import 'electron';

declare global {
  interface Window {
    electron?: {
      startBackend: () => Promise<void>;
      getBackendStatus: () => Promise<BackendStatus>;
      removeBackendErrorListener: () => void;
      apiRequest: (method: string, endpoint: string, data?: any) => Promise<ApiResponse>;
    };
  }
}

interface ApiResponse {
  success: boolean;
  data?: any;
  error?: string;
}

interface BackendStatus {
  running: boolean;
  url: string;
}

export function useBackend() {
  const [status, setStatus] = useState<BackendStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Initialize backend
  useEffect(() => {
    const initialize = async () => {
      try {
        // Check if Electron API is available
        if (!window.electron) {
          setError('Electron API not available - running in browser mode');
          return;
        }

        // Start backend if not already running
        await window.electron.startBackend();

        // Get backend status
        const backendStatus = await window.electron.getBackendStatus();
        setStatus(backendStatus);
      } catch (err) {
        setError(String(err));
      }
    };

    initialize();

    // Cleanup on unmount
    return () => {
      if (window.electron) {
        window.electron.removeBackendErrorListener();
      }
    };
  }, []);

  // Make API request
  const api = useCallback(
    async (
      method: 'GET' | 'POST' | 'PUT' | 'DELETE',
      endpoint: string,
      data?: any
    ): Promise<ApiResponse> => {
      setIsLoading(true);
      setError(null);

      try {
        if (!window.electron) {
          throw new Error('Electron API not available');
        }

        const response = await window.electron.apiRequest(
          method,
          endpoint,
          data
        );

        if (!response.success) {
          setError(response.error || 'Unknown error');
        }

        return response;
      } catch (err) {
        const errorMsg = String(err);
        setError(errorMsg);
        return { success: false, error: errorMsg };
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  return {
    api,
    status,
    error,
    isLoading,
    // Helper methods
    getShifts: (phone: string) =>
      api('POST', '/api/shifts', { phone_number: phone }),
    cancelShift: (shiftId: string) =>
      api('POST', '/api/shifts/cancel', { shift_id: shiftId }),
    bookShift: (shiftId: string) =>
      api('POST', '/api/shifts/book', { shift_id: shiftId }),
  };
}
