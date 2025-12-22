# SOLUTION: Why LLM Returns Default Dates on Another Machine

## TL;DR

The LLM is falling back to default dates when the **system date** on the other machine doesn't match your reference machine. The system prompt includes context about "today's date," and if it's wrong, the LLM gets confused.

**Quick Fix for Testing on Another Machine:**
```powershell
# Before running tests, set environment variable to your reference date
$env:SHIFT_REASONER_TODAY = "2025-12-16"

# Then run your test
python test_integrated_workflow.py --phone "0490024573" --transcript "Cancel my shift tomorrow"
```

---

## What Was Added

### 1. Date Override Support (shift_date_reasoner.py)
The `ShiftDateReasoner` now accepts an `override_today` parameter:

```python
# Override via parameter
reasoner = ShiftDateReasoner(
    model="llama2", 
    override_today="2025-12-16"  # Forces this date
)

# Override via environment variable
$env:SHIFT_REASONER_TODAY = "2025-12-16"
reasoner = ShiftDateReasoner(model="llama2")  # Auto-reads env var
```

### 2. Enhanced Error Logging (shift_date_reasoner.py)
When the LLM falls back to defaults, you now see exactly why:

```
INFO: ShiftDateReasoner initialized - Today: 2025-12-16 (Tuesday)
INFO: Reasoning dates for query: Cancel my shift tomorrow
ERROR: No JSON found in LLM response. Response was: [LLM's actual response]
WARNING: Falling back to default dates (next 7 days)
```

### 3. Diagnostic Tool (diagnose_llm_dates.py)
Run this on any machine to identify the problem:

```bash
python diagnose_llm_dates.py
```

Checks:
- System date and timezone
- Ollama server connectivity
- LLM model availability
- System prompt generation
- Date interpretation accuracy
- Default date behavior

### 4. Quick Test Helper (quick_test_llm.py)
Fast way to test LLM on another machine:

```bash
# Test with your reference date
python quick_test_llm.py --override "2025-12-16" "Cancel my shift tomorrow"

# Or use environment variable
$env:SHIFT_REASONER_TODAY = "2025-12-16"
python quick_test_llm.py "Cancel my shift tomorrow"
```

### 5. Complete Troubleshooting Guide (LLM_DEBUGGING.md)
Detailed guide covering:
- Root causes of default date fallback
- Solution 1: Environment variable override
- Solution 2: Parameter override
- Solution 3: Fixing Ollama issues
- Solution 4: Fixing model issues
- Checklist before deployment

---

## Real-World Example

### Scenario: Testing on Two Machines

**Your Machine (Reference):**
- Date: December 16, 2025 (Tuesday)
- System Prompt: "Today's date: 2025-12-16 (Tuesday)"
- Query: "Cancel my shift tomorrow"
- LLM Response: {"start_date": "17-12-2025", "end_date": "17-12-2025"} ✓

**Other Machine (Problem):**
- Date: December 15, 2025 (Monday) - or completely different
- System Prompt: "Today's date: 2025-12-15 (Monday)"
- Query: "Cancel my shift tomorrow" (but LLM doesn't know what "tomorrow" means now)
- LLM Response: Confused, returns JSON error → Falls back to defaults
- Result: {"start_date": "15-12-2025", "end_date": "22-12-2025"} ✗

**Solution:**
```powershell
# Set the date to match your reference machine
$env:SHIFT_REASONER_TODAY = "2025-12-16"

# Now the other machine uses correct context
python test_integrated_workflow.py --phone "0490024573" --transcript "Cancel my shift tomorrow"
# Result: {"start_date": "17-12-2025", "end_date": "17-12-2025"} ✓
```

---

## Testing It Out

### Test 1: Verify Your Machine Works
```bash
python diagnose_llm_dates.py
# Should show all [OK] checks

python quick_test_llm.py "Cancel my shift tomorrow"
# Should show tomorrow's date (17-12-2025)
```

### Test 2: Simulate Another Machine's Date
```bash
# Override date to Dec 15 (one day earlier)
python quick_test_llm.py --override "2025-12-15" "Cancel my shift tomorrow"
# Should show 16-12-2025 (tomorrow relative to Dec 15)
```

### Test 3: Full Integration Test with Override
```bash
$env:SHIFT_REASONER_TODAY = "2025-12-16"
python test_integrated_workflow.py --phone "0490024573" --transcript "Cancel my shift tomorrow"
# Should work correctly with proper date reasoning
```

---

## Why This Happens

1. **System Prompt Contains Date Context**
   ```
   Today's date: {today_date} ({day_of_week})
   This Sunday is: {sunday_date}
   ```

2. **LLM Uses Context to Reason About Relative Dates**
   - "Tomorrow" → today's date + 1 day
   - "This week" → today to this Sunday
   - "Next week" → Sunday to next Saturday

3. **When Context is Wrong**
   - LLM gets confused about what "tomorrow" means
   - Falls back to default (next 7 days)
   - Code detects this and logs: "Falling back to default dates"

4. **With Correct Context via Override**
   - LLM understands relative dates correctly
   - Returns specific dates as expected
   - Code logs successful reasoning

---

## Files Created/Modified

### Modified Files
- `backend/core/call_assistant/shift_date_reasoner.py`
  - Added `override_today` parameter
  - Added `SHIFT_REASONER_TODAY` environment variable support
  - Enhanced logging for debugging

### New Files
- `backend/automation/diagnose_llm_dates.py` - Full diagnostic tool
- `backend/automation/quick_test_llm.py` - Quick test helper
- `backend/automation/LLM_DEBUGGING.md` - Detailed troubleshooting guide
- `backend/automation/WHY_LLM_DEFAULTS.md` - Root cause analysis
- `backend/automation/SOLUTION_LLM_DATES.md` - This file

---

## Deployment Checklist

Before deploying to another machine:

- [ ] Run `python diagnose_llm_dates.py` - all checks should pass
- [ ] Ollama is running: `ollama serve`
- [ ] llama2 model is installed: `ollama list | grep llama2`
- [ ] Test with override date: `python quick_test_llm.py --override "2025-12-16" "..."`
- [ ] If tests pass with override, Ollama and models are correct
- [ ] If tests fail with override, check LLM response format

---

## Quick Reference Commands

```powershell
# Set override date for all following tests
$env:SHIFT_REASONER_TODAY = "2025-12-16"

# Run full diagnostics
python diagnose_llm_dates.py

# Quick test with override
python quick_test_llm.py --override "2025-12-16" "Cancel my shift tomorrow"

# Full integration test with override
python test_integrated_workflow.py --phone "0490024573" --transcript "Cancel my shift tomorrow"

# Clear override when done
Remove-Item env:SHIFT_REASONER_TODAY
```

---

## Support

If you're still seeing "default dates" after trying these solutions:

1. Run `python diagnose_llm_dates.py` and check all outputs
2. Look for `[WARN]` or `[FAIL]` messages
3. Check detailed logs in code output
4. Share the diagnostic output with the development team

Common issues:
- Ollama not running → Run `ollama serve`
- Wrong model → Run `ollama pull llama2`
- System date is way off → Set `SHIFT_REASONER_TODAY` environment variable
