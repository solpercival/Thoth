# LLM DATE REASONING TROUBLESHOOTING GUIDE

## Problem: "LLM is returning default dates (full week) instead of specific dates on another machine"

The LLM falling back to defaults is a clear indicator that something is wrong with the input context or the LLM isn't receiving the proper system prompt. Here's how to diagnose and fix it.

---

## Root Causes & Solutions

### 1. **OLLAMA SERVER NOT RUNNING** ❌ → ✅
**Symptom:** Code always returns next 7 days, debug logs show connection errors

**Check:**
```powershell
# On Windows
Get-Process ollama
# If nothing appears, Ollama is not running

# On macOS/Linux
ps aux | grep ollama
```

**Fix:**
```powershell
# Windows: Start Ollama
ollama serve

# Or if installed as service, restart it
```

### 2. **DIFFERENT SYSTEM DATE ON THE OTHER MACHINE** ❌ → ✅
**Symptom:** Works fine on your machine but not on other machine with different system date

**The Problem:**
- Your machine: December 16, 2025 (Tuesday)
- Other machine: December 15, 2025 (Monday) or January 2026
- System prompt includes: "Today's date: 2025-12-16 (Tuesday)"
- When running on different machine, LLM gets wrong context and defaults

**Solution 1: Use Environment Variable (RECOMMENDED for testing)**
```powershell
# On the OTHER machine, set the date to match your reference machine
$env:SHIFT_REASONER_TODAY = "2025-12-16"

# Then run the test
python test_integrated_workflow.py --phone "0490024573" --transcript "Cancel my shift tomorrow"
```

**Solution 2: Use Parameter Override**
```python
# In your code
from backend.core.call_assistant.shift_date_reasoner import ShiftDateReasoner

reasoner = ShiftDateReasoner(model="llama2", override_today="2025-12-16")
```

### 3. **DIFFERENT LLAMA2 MODEL VERSION** ❌ → ✅
**Symptom:** Same code, different results on different machines

**Check what's installed:**
```bash
ollama list
```

**If llama2 is not installed:**
```bash
ollama pull llama2
```

**If llama2 is too old:**
```bash
ollama rm llama2
ollama pull llama2
```

### 4. **OLLAMA MODEL RUNNING OUT OF MEMORY** ❌ → ✅
**Symptom:** LLM returns blank responses or malformed JSON

**Check logs:**
```bash
# Look for "out of memory" errors
ollama serve
```

**Fix:**
- Reduce other running programs
- Use a smaller model temporarily: `gemma3:1b`
- Restart Ollama: `ollama serve`

### 5. **JSON PARSING ERRORS** ❌ → ✅
**Symptom:** LLM returns valid response but code can't parse it

**Enable detailed logging:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)

# This will show exact LLM response and parsing errors
```

---

## Diagnostic Script

**Run this on the problematic machine:**
```bash
python diagnose_llm_dates.py
```

This will check:
- ✓ System date and time
- ✓ Ollama server connectivity
- ✓ LLM model availability
- ✓ System prompt generation
- ✓ LLM response format
- ✓ Date parsing accuracy

---

## Testing with Override Dates

When deploying to a new machine, always test with the diagnostic script first:

```bash
# Step 1: Run diagnostics
python diagnose_llm_dates.py

# Step 2: If Ollama not reachable, start it
ollama serve

# Step 3: If llama2 not installed, pull it
ollama pull llama2

# Step 4: Test with override date matching your reference machine
$env:SHIFT_REASONER_TODAY = "2025-12-16"
python test_integrated_workflow.py --phone "0490024573" --transcript "Cancel my shift tomorrow"

# Step 5: Check detailed logs
# Look for warnings about "Falling back to default dates"
```

---

## Environment Variables

### SHIFT_REASONER_TODAY
Override the system date for testing.

```bash
# Format: YYYY-MM-DD
$env:SHIFT_REASONER_TODAY = "2025-12-16"

# Clear it when done
Remove-Item env:SHIFT_REASONER_TODAY
```

---

## Common Error Messages & Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| "No JSON found in LLM response" | LLM returned plain text instead of JSON | Check system prompt, restart Ollama |
| "Missing required fields" | LLM returned incomplete JSON | Verify llama2 model version |
| "Failed to reach Ollama" | Server not running or wrong address | Run `ollama serve` |
| "Falling back to default dates" | Any of above issues | Run `diagnose_llm_dates.py` |

---

## Confirmation Checklist

Before deploying to another machine:

- [ ] System date is set correctly
- [ ] Ollama is running: `ollama serve`
- [ ] llama2 model is pulled: `ollama list`
- [ ] Diagnostic script passes all checks
- [ ] Test with matching override date works
- [ ] Response shows specific date instead of next 7 days

---

## Integration with CI/CD

For automated deployments, set the environment variable before running tests:

```yaml
# Example GitHub Actions
env:
  SHIFT_REASONER_TODAY: "2025-12-16"
- name: Run integration tests
  run: python test_integrated_workflow.py --phone "0490024573" --transcript "Cancel my shift tomorrow"
```

---

## Still Having Issues?

Run diagnostic and share output:
```bash
python diagnose_llm_dates.py > diagnostic_report.txt
# Share diagnostic_report.txt with developer team
```

Key things to check in output:
1. Ollama server reachable ✓
2. llama2 model available ✓
3. System prompt contains today's date ✓
4. System prompt contains day of week ✓
5. LLM response is valid JSON ✓
6. Date format is DD-MM-YYYY ✓
