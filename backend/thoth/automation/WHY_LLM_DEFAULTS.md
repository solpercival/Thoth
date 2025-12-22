# WHY LLM RETURNS DEFAULT DATES ON ANOTHER MACHINE - ROOT CAUSE ANALYSIS

## The Problem
LLM is falling back to default dates (full week instead of specific dates) when running on another machine, but works fine on your machine.

## Root Cause
The LLM's behavior depends heavily on the **system prompt context**, which includes:
```
Today's date: 2025-12-16 (Tuesday)
This Sunday is: 21-12-2025
```

When you run the code on a different machine with a different system date, the LLM receives completely different context and may fall back to defaults.

**Example:**
- Your machine: December 16, 2025 (Tuesday)
  - System prompt: "Today's date: 2025-12-16 (Tuesday)"
  - LLM works correctly ✓

- Other machine: December 15, 2025 (Monday) 
  - System prompt: "Today's date: 2025-12-15 (Monday)"
  - LLM confused about relative dates → falls back to defaults ✗

## Solutions Implemented

### 1. **Date Override Capability** ✅
Added ability to override the system date for testing:

**Via Environment Variable:**
```powershell
$env:SHIFT_REASONER_TODAY = "2025-12-16"
python test_integrated_workflow.py --phone "0490024573" --transcript "Cancel my shift tomorrow"
```

**Via Code:**
```python
from backend.core.call_assistant.shift_date_reasoner import ShiftDateReasoner
reasoner = ShiftDateReasoner(model="llama2", override_today="2025-12-16")
```

### 2. **Enhanced Logging** ✅
Added detailed logging to show exactly why defaults are being used:
```
INFO: ShiftDateReasoner initialized - Today: 2025-12-16 (Tuesday)
INFO: Reasoning dates for query: Cancel my shift tomorrow
ERROR: No JSON found in LLM response
WARNING: Falling back to default dates (next 7 days)
```

### 3. **Diagnostic Tool** ✅
New `diagnose_llm_dates.py` script checks everything:
```bash
python diagnose_llm_dates.py
```

Verifies:
- System date and time
- Ollama server connectivity
- LLM model availability
- System prompt generation
- LLM response format
- Date parsing accuracy

### 4. **Quick Test Helper** ✅
New `quick_test_llm.py` script for quick testing:
```bash
python quick_test_llm.py --override "2025-12-16" "Cancel my shift tomorrow"
```

### 5. **Troubleshooting Guide** ✅
New `LLM_DEBUGGING.md` file explains:
- How to identify the root cause
- Common issues and fixes
- Checklist before deployment
- Environment variable setup

---

## How to Use This On Another Machine

### Step 1: Check Everything
```bash
python diagnose_llm_dates.py
```

### Step 2: If Ollama Not Running
```bash
ollama serve
```

### Step 3: If llama2 Not Installed
```bash
ollama pull llama2
```

### Step 4: Test with Override Date
```powershell
# Set environment variable
$env:SHIFT_REASONER_TODAY = "2025-12-16"

# Run test
python test_integrated_workflow.py --phone "0490024573" --transcript "Cancel my shift tomorrow"
```

### Step 5: Verify Output
You should see:
- Specific dates (e.g., "17-12-2025 → 17-12-2025")
- NOT default dates ("16-12-2025 → 23-12-2025")
- Reasoning with `<CNCL>` or `<SHOW>` flag

---

## Key Changes Made

### shift_date_reasoner.py
- ✅ Added `override_today` parameter to `__init__`
- ✅ Added `SHIFT_REASONER_TODAY` environment variable support
- ✅ Enhanced logging with system prompt context
- ✅ Detailed error messages when falling back to defaults
- ✅ Exception traceback logging for debugging

### New Files Created
- ✅ `diagnose_llm_dates.py` - Comprehensive diagnostic tool
- ✅ `quick_test_llm.py` - Quick testing helper
- ✅ `LLM_DEBUGGING.md` - Complete troubleshooting guide

---

## Why This Matters

1. **Reproducibility**: You can now test on any machine by overriding the date
2. **Visibility**: Detailed logs show exactly why defaults are being used
3. **Debugging**: Diagnostic tool quickly identifies the root cause
4. **Reliability**: No more mysterious failures on different machines

---

## Files Modified
- [shift_date_reasoner.py](../core/call_assistant/shift_date_reasoner.py)

## Files Created
- [diagnose_llm_dates.py](./diagnose_llm_dates.py)
- [quick_test_llm.py](./quick_test_llm.py)
- [LLM_DEBUGGING.md](./LLM_DEBUGGING.md)
