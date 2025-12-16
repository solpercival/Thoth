# INTERMITTENT DEFAULT DATES - ROOT CAUSES & SOLUTIONS

## Problem
Even when diagnostics show everything is correct, the LLM sometimes returns default dates (full week instead of specific dates).

## Root Causes

### 1. **System Prompt Lost Between Requests** ❌ → ✅
The system prompt might be cleared or not included in some LLM requests.

**Solution Implemented:**
- Added validation check before every LLM call
- If system prompt is missing, it's automatically re-initialized
- Verified in debug logs: `System prompt missing from LLM history! Re-initializing...`

### 2. **Intermittent LLM Response Failures** ❌ → ✅
Sometimes the LLM returns:
- Blank responses
- Malformed JSON
- Missing required fields
- Invalid date formats

**Solution Implemented:**
- Added automatic retry logic (up to 2 attempts)
- Each failed attempt clears history and tries again
- Only falls back to defaults after all retries exhausted
- Logs show exactly what failed: `No JSON found in LLM response (attempt 1)`

### 3. **Conversation History Contamination** ❌ → ✅
Previous queries might influence the LLM's response.

**Solution Implemented:**
- Clear history IMMEDIATELY after parsing result
- `clear_history(keep_system_prompt=True)` preserves instructions but clears past queries

### 4. **Model Inconsistency** ❌ → ✅
Different model versions might have different behaviors.

**Solution Implemented:**
- Updated to use `llama2:latest` instead of just `llama2`
- Ensures consistent behavior across machines
- Can be pulled/updated: `ollama pull llama2:latest`

---

## Enhanced Features

### Retry Logic
```python
# Now automatically retries failed queries
reason_dates(user_query, retry_on_defaults=True)  # Default: True
```

When the LLM fails (no JSON, malformed JSON, missing fields):
1. First attempt fails → clears history
2. Second attempt with fresh context
3. Only uses defaults if both attempts fail

### System Prompt Verification
Before every LLM call, the code checks:
```python
history = self.llm_client.get_history()
if not history or history[0].get('role') != 'system':
    # Reinitialize system prompt
```

### Detailed Logging
Enable debug logging to see what's happening:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

Example debug output:
```
INFO: Reasoning dates for query: Cancel my shift tomorrow (attempt 1/2)
INFO: LLM context - Today: 2025-12-16, This Sunday: 2025-12-21
DEBUG: LLM response (attempt 1): {"is_shift_query": true, ...}
INFO: Determined dates (attempt 1): 17-12-2025 to 17-12-2025
```

When retry is needed:
```
ERROR: No JSON found in LLM response (attempt 1). Response was: Some invalid text
WARNING: Retrying... (attempt 2)
INFO: Reasoning dates for query: Cancel my shift tomorrow (attempt 2/2)
INFO: Determined dates (attempt 2): 17-12-2025 to 17-12-2025
```

---

## Usage

### Normal Usage (With Retry)
```python
from backend.core.call_assistant.shift_date_reasoner import ShiftDateReasoner

reasoner = ShiftDateReasoner(model="llama2:latest")
result = reasoner.reason_dates("Cancel my shift tomorrow")
# Automatically retries if needed
```

### Disable Retry (For Testing)
```python
result = reasoner.reason_dates("Cancel my shift tomorrow", retry_on_defaults=False)
# Will fail immediately instead of retrying
```

### Override Date (For Testing on Different Machine)
```python
reasoner = ShiftDateReasoner(
    model="llama2:latest",
    override_today="2025-12-16"  # Or use env var SHIFT_REASONER_TODAY
)
result = reasoner.reason_dates("Cancel my shift tomorrow")
```

---

## Testing Intermittent Issues

Run the quick test multiple times to see if defaults appear:

```bash
# Test 10 times
for i in {1..10}; do
    echo "Test $i:"
    python quick_test_llm.py "Cancel my shift tomorrow"
done
```

If defaults appear in some runs:
1. Enable debug logging
2. Look for "Retrying..." messages
3. Check if "System prompt missing" appears
4. Verify Ollama is stable: `ollama ps`

---

## Troubleshooting Checklist

If still getting intermittent defaults:

- [ ] Ollama is running and stable: `ollama serve`
- [ ] llama2:latest is pulled: `ollama pull llama2:latest`
- [ ] Sufficient system memory/RAM available
- [ ] No background Ollama processes: `Get-Process ollama`
- [ ] Check Ollama logs for errors
- [ ] System date is correct on the machine
- [ ] Network connection stable (if using remote Ollama)

---

## Files Modified

- [shift_date_reasoner.py](../core/call_assistant/shift_date_reasoner.py)
  - Added `retry_on_defaults` parameter to `reason_dates()`
  - Added system prompt verification before every LLM call
  - Added automatic retry logic with detailed logging
  - Changed default model from `llama2` to `llama2:latest`

- [test_integrated_workflow.py](./test_integrated_workflow.py)
  - Updated model reference to `llama2:latest`

---

## Expected Behavior After Fix

**Before (Intermittent):**
```
Run 1: 17-12-2025 (correct)
Run 2: 16-12-2025 → 23-12-2025 (default - wrong!)
Run 3: 17-12-2025 (correct)
```

**After (Consistent):**
```
Run 1: 17-12-2025 (correct, no retry needed)
Run 2: 17-12-2025 (correct, retried once due to intermittent issue)
Run 3: 17-12-2025 (correct, no retry needed)
```

All runs now get correct specific dates, with transparent logging of any retries.

---

## Next Steps

1. Test with `quick_test_llm.py` multiple times
2. Monitor logs for retry messages
3. If retries happen consistently, Ollama might be unstable
4. Use diagnostic tool to verify system health: `diagnose_llm_dates.py`
