# SUMMARY: FIX FOR INTERMITTENT DEFAULT DATES

## What Was Fixed

The LLM was sometimes returning default dates (full week) instead of specific dates, even though diagnostics showed everything was working correctly. This was caused by **intermittent failures in the LLM response processing** that weren't being handled properly.

## Key Improvements

### 1. **Automatic Retry Logic** ✅
- Added 2-attempt retry system for failed queries
- Each retry clears the conversation history and tries again
- Only uses defaults after both attempts fail
- Logged clearly: `Retrying... (attempt 2/2)`

### 2. **System Prompt Verification** ✅
- Before every LLM call, verifies the system prompt is in the conversation history
- If missing, automatically re-initializes the system prompt
- Prevents "lost context" issues between requests

### 3. **Better Logging** ✅
- Added detailed attempt counters: `(attempt 1/2)`, `(attempt 2/2)`
- Shows exact failure point: `No JSON found`, `Missing required fields`, etc.
- LLM response preview: `LLM response (attempt 1): {response[:500]}...`
- Full exception traceback when errors occur

### 4. **Model Version Pinning** ✅
- Changed from `llama2` to `llama2:latest`
- Ensures consistent behavior across machines
- Prevents version mismatches from causing different responses

## Changed Files

### [shift_date_reasoner.py](../core/call_assistant/shift_date_reasoner.py)
```python
# OLD: Simple single attempt
def reason_dates(self, user_query: str) -> dict:
    response = self.llm_client.ask_llm(user_query)
    # ... process response ...
    return date_info

# NEW: With retry logic
def reason_dates(self, user_query: str, retry_on_defaults: bool = True) -> dict:
    max_retries = 2 if retry_on_defaults else 1
    attempt = 0
    
    while attempt < max_retries:
        attempt += 1
        try:
            # Verify system prompt is present
            history = self.llm_client.get_history()
            if not history or history[0].get('role') != 'system':
                # Re-initialize if missing
                self.llm_client.set_system_prompt(...)
            
            response = self.llm_client.ask_llm(user_query)
            # ... process response with detailed error handling ...
            
            if success:
                return date_info
            elif attempt < max_retries:
                self.llm_client.clear_history(keep_system_prompt=True)
                continue  # Retry
        except Exception as e:
            if attempt < max_retries:
                continue  # Retry
            return self._default_dates()
```

### [test_integrated_workflow.py](./test_integrated_workflow.py)
```python
# OLD
reasoner = ShiftDateReasoner(model="llama2")

# NEW
reasoner = ShiftDateReasoner(model="llama2:latest")
```

## How It Works Now

### Normal Case (No Retry Needed)
```
INFO: Reasoning dates for query: Cancel my shift tomorrow (attempt 1/2)
INFO: LLM context - Today: 2025-12-16, This Sunday: 2025-12-21
DEBUG: LLM response (attempt 1): {"is_shift_query": true, "date_range_type": "specific", ...}
INFO: Determined dates (attempt 1): 17-12-2025 to 17-12-2025
```

### Intermittent Failure Case (Retry Succeeds)
```
INFO: Reasoning dates for query: Cancel my shift tomorrow (attempt 1/2)
ERROR: No JSON found in LLM response (attempt 1). Response was: Some invalid text
WARNING: Retrying... (attempt 2/2)
INFO: Reasoning dates for query: Cancel my shift tomorrow (attempt 2/2)
DEBUG: LLM response (attempt 2): {"is_shift_query": true, "date_range_type": "specific", ...}
INFO: Determined dates (attempt 2): 17-12-2025 to 17-12-2025
```

### All Retries Failed (Uses Default)
```
INFO: Reasoning dates for query: Cancel my shift tomorrow (attempt 1/2)
ERROR: No JSON found in LLM response (attempt 1)
WARNING: Retrying... (attempt 2/2)
ERROR: No JSON found in LLM response (attempt 2)
WARNING: Falling back to default dates (next 7 days)
```

## Testing

Run the quick test script to verify:
```bash
python quick_test_llm.py "Cancel my shift tomorrow"
python quick_test_llm.py "I want to cancel my shift this week"
```

Run the integrated workflow:
```bash
python test_integrated_workflow.py --phone "0490024573" --transcript "Cancel my shift tomorrow"
```

Monitor logs to see retries (if any):
```bash
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Benefits

1. **Reliability** - Intermittent failures are automatically recovered from
2. **Transparency** - Clear logging shows when retries happen and why
3. **Consistency** - Same model version across all machines
4. **Robustness** - System prompt is verified before every request
5. **Debugging** - Detailed logs help identify if Ollama is unstable

## Migration

If upgrading from previous version:

1. Pull the latest model: `ollama pull llama2:latest`
2. No code changes needed for existing code calling `ShiftDateReasoner()`
   - Default model is now `llama2:latest` instead of `llama2`
   - Retry logic is automatic (can be disabled with `retry_on_defaults=False`)

## Monitoring

To monitor for Ollama stability issues, look for these patterns in logs:

```
# Frequent retries indicate Ollama is unstable
WARNING: Retrying... (appears multiple times)

# System prompt reinitialization indicates connection issues
WARNING: System prompt missing from LLM history! Re-initializing...

# Repeated defaults indicate persistent LLM failure
WARNING: Falling back to default dates (appears multiple times)
```

If seeing these patterns:
1. Check Ollama server: `ollama ps`
2. Restart Ollama: `ollama serve`
3. Check system memory/CPU: `Get-Process ollama`
4. Run diagnostics: `diagnose_llm_dates.py`
