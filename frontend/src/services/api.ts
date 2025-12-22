/**
 * API service for making backend requests
 * This wraps the Electron IPC bridge for cleaner usage
 */

export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
}

export class ApiService {
  /**
   * Make an API request through Electron IPC
   */
  static async request<T = any>(
    method: 'GET' | 'POST' | 'PUT' | 'DELETE',
    endpoint: string,
    data?: any
  ): Promise<ApiResponse<T>> {
    try {
      if (!window.electron) {
        throw new Error('Electron API not available');
      }

      const response = await window.electron.apiRequest(method, endpoint, data);
      return response;
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : String(error),
      };
    }
  }

  /**
   * Convenience methods for common operations
   */
  static async getShifts(phoneNumber: string) {
    return this.request('POST', '/api/shifts', { phone_number: phoneNumber });
  }

  static async cancelShift(shiftId: string) {
    return this.request('POST', '/api/shifts/cancel', { shift_id: shiftId });
  }

  static async bookShift(shiftId: string) {
    return this.request('POST', '/api/shifts/book', { shift_id: shiftId });
  }

  /**
   * Backend control methods
   */
  static async startBackend() {
    if (!window.electron) {
      throw new Error('Electron API not available');
    }
    return window.electron.startBackend();
  }

  static async stopBackend() {
    if (!window.electron) {
      throw new Error('Electron API not available');
    }
    return window.electron.stopBackend();
  }

  static async getBackendStatus() {
    if (!window.electron) {
      throw new Error('Electron API not available');
    }
    return window.electron.getBackendStatus();
  }
}

export default ApiService;
