/**
 * Example API usage patterns
 * Copy and modify these examples for your use cases
 */

import { useBackend } from '../hooks/useBackend';
import { useState } from 'react';
import 'electron';

/**
 * Example 1: Fetch shifts for a user
 */
export function GetShiftsExample() {
  const { api, isLoading, error } = useBackend();
  const [phoneNumber, setPhoneNumber] = useState('');
  const [shifts, setShifts] = useState<any[]>([]);

  const handleFetchShifts = async (e: React.FormEvent) => {
    e.preventDefault();
    
    const response = await api('POST', '/api/shifts', {
      phone_number: phoneNumber
    });

    if (response.success) {
      setShifts(response.data.shifts || []);
    }
  };

  return (
    <div>
      <h2>Get Shifts</h2>
      <form onSubmit={handleFetchShifts}>
        <input
          type="text"
          value={phoneNumber}
          onChange={(e) => setPhoneNumber(e.target.value)}
          placeholder="Enter phone number"
        />
        <button type="submit" disabled={isLoading}>
          {isLoading ? 'Loading...' : 'Get Shifts'}
        </button>
      </form>
      
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      
      {shifts.length > 0 && (
        <ul>
          {shifts.map((shift) => (
            <li key={shift.id}>
              {shift.client} - {shift.date} at {shift.time}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/**
 * Example 2: Cancel a shift
 */
export function CancelShiftExample() {
  const { api, isLoading, error } = useBackend();
  const [shiftId, setShiftId] = useState('');
  const [success, setSuccess] = useState(false);

  const handleCancelShift = async () => {
    const response = await api('POST', '/api/shifts/cancel', {
      shift_id: shiftId
    });

    if (response.success) {
      setSuccess(true);
      setShiftId('');
      // Clear success message after 2 seconds
      setTimeout(() => setSuccess(false), 2000);
    }
  };

  return (
    <div>
      <h2>Cancel Shift</h2>
      <input
        type="text"
        value={shiftId}
        onChange={(e) => setShiftId(e.target.value)}
        placeholder="Enter shift ID"
      />
      <button onClick={handleCancelShift} disabled={isLoading}>
        {isLoading ? 'Cancelling...' : 'Cancel Shift'}
      </button>
      
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      {success && <p style={{ color: 'green' }}>✓ Shift cancelled successfully</p>}
    </div>
  );
}

/**
 * Example 3: Book a shift
 */
export function BookShiftExample() {
  const { api, isLoading, error } = useBackend();
  const [shiftId, setShiftId] = useState('');

  const handleBookShift = async () => {
    const response = await api('POST', '/api/shifts/book', {
      shift_id: shiftId
    });

    if (response.success) {
      alert('Shift booked successfully!');
      setShiftId('');
    }
  };

  return (
    <div>
      <h2>Book Shift</h2>
      <input
        type="text"
        value={shiftId}
        onChange={(e) => setShiftId(e.target.value)}
        placeholder="Enter shift ID"
      />
      <button onClick={handleBookShift} disabled={isLoading || !shiftId}>
        {isLoading ? 'Booking...' : 'Book Shift'}
      </button>
      
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
    </div>
  );
}

/**
 * Example 4: Using helper methods from useBackend hook
 */
export function HelperMethodsExample() {
  const { getShifts, cancelShift, bookShift, isLoading, error } = useBackend();
  const [phoneNumber, setPhoneNumber] = useState('');

  const handleGetShifts = async () => {
    const response = await getShifts(phoneNumber);
    console.log('Shifts:', response.data);
  };

  const handleCancel = async (shiftId: string) => {
    const response = await cancelShift(shiftId);
    console.log('Cancelled:', response.success);
  };

  const handleBook = async (shiftId: string) => {
    const response = await bookShift(shiftId);
    console.log('Booked:', response.success);
  };

  return (
    <div>
      <h2>Using Helper Methods</h2>
      <input
        type="text"
        value={phoneNumber}
        onChange={(e) => setPhoneNumber(e.target.value)}
        placeholder="Phone number"
      />
      <button onClick={handleGetShifts} disabled={isLoading}>Get Shifts</button>
      
      {error && <p>{error}</p>}
    </div>
  );
}

/**
 * Example 5: Making custom API requests
 */
export function CustomApiExample() {
  const { api, isLoading } = useBackend();

  const handleCustomRequest = async () => {
    // GET request
    const getResponse = await api('GET', '/api/custom-endpoint');
    console.log('GET response:', getResponse);

    // POST request with complex data
    const postResponse = await api('POST', '/api/custom-endpoint', {
      data: {
        nested: {
          value: 'test'
        }
      }
    });
    console.log('POST response:', postResponse);

    // PUT request
    const putResponse = await api('PUT', '/api/custom-endpoint', {
      id: '123',
      updated: true
    });
    console.log('PUT response:', putResponse);

    // DELETE request
    const deleteResponse = await api('DELETE', '/api/custom-endpoint');
    console.log('DELETE response:', deleteResponse);
  };

  return (
    <button onClick={handleCustomRequest} disabled={isLoading}>
      Make Custom API Calls
    </button>
  );
}

/**
 * Example 6: Error handling and retry logic
 */
export function ErrorHandlingExample() {
  const { api, isLoading, error } = useBackend();

  const handleWithRetry = async () => {
    const maxRetries = 3;
    let lastError = null;

    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        const response = await api('GET', '/api/shifts');
        
        if (response.success) {
          console.log('Success on attempt', attempt);
          return response.data;
        } else {
          lastError = response.error;
          console.log(`Attempt ${attempt} failed: ${response.error}`);
        }
      } catch (err) {
        lastError = err;
        console.log(`Attempt ${attempt} error:`, err);
      }

      // Wait before retrying
      if (attempt < maxRetries) {
        await new Promise(r => setTimeout(r, 1000 * attempt));
      }
    }

    console.error('All retry attempts failed:', lastError);
    return null;
  };

  return (
    <button onClick={handleWithRetry} disabled={isLoading}>
      Request with Retry Logic
    </button>
  );
}

/**
 * Example 7: Form with validation and submission
 */
export function FormSubmissionExample() {
  const { api, isLoading, error } = useBackend();
  const [formData, setFormData] = useState({
    phone: '',
    action: 'get-shifts'
  });
  const [response, setResponse] = useState<any>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validation
    if (!formData.phone) {
      alert('Please enter a phone number');
      return;
    }

    // API call based on action
    let apiResponse;
    switch (formData.action) {
      case 'get-shifts':
        apiResponse = await api('POST', '/api/shifts', {
          phone_number: formData.phone
        });
        break;
      case 'check-status':
        apiResponse = await api('GET', `/api/user/${formData.phone}`);
        break;
      default:
        return;
    }

    if (apiResponse.success) {
      setResponse(apiResponse.data);
    } else {
      alert(`Error: ${apiResponse.error}`);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <h2>Form with Validation</h2>
      
      <input
        type="text"
        value={formData.phone}
        onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
        placeholder="Phone number"
        required
      />

      <select
        value={formData.action}
        onChange={(e) => setFormData({ ...formData, action: e.target.value })}
      >
        <option value="get-shifts">Get Shifts</option>
        <option value="check-status">Check Status</option>
      </select>

      <button type="submit" disabled={isLoading}>
        {isLoading ? 'Loading...' : 'Submit'}
      </button>

      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      
      {response && (
        <pre>{JSON.stringify(response, null, 2)}</pre>
      )}
    </form>
  );
}

/**
 * Example 8: Polling backend status
 */
export function PollingExample() {
  const { status, isLoading } = useBackend();

  const handlePoll = async () => {
    const pollInterval = setInterval(async () => {
      if (!window.electron) return;
      const currentStatus = await window.electron.getBackendStatus();
      console.log('Backend status:', currentStatus);

      if (!currentStatus.running) {
        console.warn('Backend went down!');
        clearInterval(pollInterval);
      }
    }, 5000); // Check every 5 seconds

    // Stop polling after 1 minute
    setTimeout(() => clearInterval(pollInterval), 60000);
  };

  return (
    <div>
      <h2>Backend Polling</h2>
      <p>Status: {status?.running ? '✓ Running' : '✗ Not Running'}</p>
      <button onClick={handlePoll} disabled={isLoading}>
        Start Polling Backend
      </button>
    </div>
  );
}

/**
 * Example 9: Batch operations
 */
export function BatchOperationsExample() {
  const { api } = useBackend();

  const handleBatchCancel = async (shiftIds: string[]) => {
    const results = await Promise.all(
      shiftIds.map(id => api('POST', '/api/shifts/cancel', { shift_id: id }))
    );

    const successful = results.filter(r => r.success).length;
    console.log(`Cancelled ${successful}/${shiftIds.length} shifts`);
  };

  return (
    <button onClick={() => handleBatchCancel(['shift-1', 'shift-2', 'shift-3'])}>
      Batch Cancel Shifts
    </button>
  );
}

/**
 * Example 10: Real-time UI updates
 */
export function RealtimeExample() {
  const { api } = useBackend();
  const [shifts, setShifts] = useState<any[]>([]);

  const startRefreshing = () => {
    const interval = setInterval(async () => {
      const response = await api('GET', '/api/shifts');
      if (response.success) {
        setShifts(response.data.shifts || []);
      }
    }, 10000); // Refresh every 10 seconds

    return () => clearInterval(interval);
  };

  return (
    <div>
      <button onClick={startRefreshing}>
        Start Auto-Refresh
      </button>
      <ul>
        {shifts.map(shift => (
          <li key={shift.id}>{shift.client}</li>
        ))}
      </ul>
    </div>
  );
}
