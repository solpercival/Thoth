# Date Filtering Enhancement

## What Changed

The workflow now includes **server-side date filtering** using the reasoned dates from the LLM.

### Before
```
1. Login
2. Look up staff by phone
3. Reason dates from transcript (LLM)
4. Search shifts by name (get ALL shifts)
5. Filter locally (phone side)
```

### After ✅
```
1. Login
2. Look up staff by phone
3. Reason dates from transcript (LLM)
4. Search shifts by name with date range (FILTER ON SERVER)
5. Additional local filtering for safety
```

## Implementation Details

### Modified Function Signature

**staff_lookup.py::search_staff_shifts_by_name()**

```python
# Before
async def search_staff_shifts_by_name(page, staff_name: str) -> list

# After
async def search_staff_shifts_by_name(page, staff_name: str, start_date: str = None, end_date: str = None) -> list
```

### What It Does

1. **Accepts date parameters** from LLM in YYYY-MM-DD format
   - Example: `start_date="2025-12-16"`, `end_date="2025-12-16"`

2. **Converts date format** for Ezaango search field
   - YYYY-MM-DD → DD-MM-YYYY
   - Example: `2025-12-16` → `16-12-2025`

3. **Fills the search input field**
   ```python
   search_input = page.locator('input[type="search"].form-control-sm')
   await search_input.fill("15-12-2025 to 16-12-2025")
   ```

4. **Submits the filter**
   ```python
   await search_input.press("Enter")
   await page.wait_for_load_state("networkidle")
   ```

5. **Returns pre-filtered results**
   - Table now only contains shifts within the date range
   - Server-side filtering reduces data transfer
   - Faster response times

## Usage in Workflow

### test_integrated_workflow.py

**Before:**
```python
all_shifts = await search_staff_shifts_by_name(page, staff['full_name'])
```

**After:**
```python
all_shifts = await search_staff_shifts_by_name(
    page, 
    staff['full_name'],
    start_date=date_info['start_date'],      # From LLM
    end_date=date_info['end_date']            # From LLM
)
```

### Flow Diagram

```
LLM Outputs Dates
    ↓
test_integrated_workflow.py receives:
    {
        "start_date": "2025-12-16",
        "end_date": "2025-12-16",
        ...
    }
    ↓
Passes to search_staff_shifts_by_name():
    search_staff_shifts_by_name(
        page,
        "Alannah Courtnay",
        start_date="2025-12-16",
        end_date="2025-12-16"
    )
    ↓
staff_lookup.py:
    1. Navigate to /search?keyword=Alannah+Courtnay
    2. Find search input: input[type="search"].form-control-sm
    3. Fill with: "16-12-2025 to 16-12-2025"
    4. Press Enter
    5. Wait for results to filter
    6. Parse table (now contains only shifts on 16-12-2025)
    7. Return filtered shifts
    ↓
test_integrated_workflow.py:
    Optional local filtering as backup
    Return final results
```

## Benefits

✅ **Server-side filtering** - Reduces data transfer, faster response
✅ **Intelligent date handling** - LLM interprets natural language ("tomorrow", "next week", etc.)
✅ **Format conversion** - Automatically converts between YYYY-MM-DD and DD-MM-YYYY
✅ **Backward compatible** - Dates are optional parameters (default None)
✅ **Safety layer** - Local filtering still available as backup

## Example Output

```
[STEP 4] Reasoning dates from transcript...
[*] Asking LLM: "Hi I would like to cancel my shift tomorrow"
[+] LLM Analysis:
    Start Date: 2025-12-16
    End Date: 2025-12-16

[STEP 5] Searching for shifts with date range filter...
[*] Searching shifts for: Alannah Courtnay
[*] Filtering to date range: 2025-12-16 to 2025-12-16
[*] Date filtering enabled: 2025-12-16 to 2025-12-16
[*] Filling search field with date range: 16-12-2025 to 16-12-2025
[*] Search results filtered by date range
[+] Found 0 shifts (no shifts on Dec 16)
```

## Date Format Details

### Input Format (From LLM)
```python
date_info = {
    "start_date": "2025-12-16",    # YYYY-MM-DD
    "end_date": "2025-12-16"        # YYYY-MM-DD
}
```

### Search Field Format (For Ezaango)
```
16-12-2025 to 16-12-2025          # DD-MM-YYYY to DD-MM-YYYY
```

### Conversion Logic
```python
# Input: "2025-12-16"
start_parts = "2025-12-16".split("-")  # ["2025", "12", "16"]
formatted = f"{start_parts[2]}-{start_parts[1]}-{start_parts[0]}"  # "16-12-2025"
```

## Testing

### Test with Visible Browser

```bash
python test_integrated_workflow.py \
    --phone "0431256441" \
    --transcript "Hi I would like to cancel my shift tomorrow"
```

Watch the browser:
1. Login successfully
2. Navigate to /staff/4
3. Find staff
4. Navigate to /search
5. **NEW:** See search field being filled with date range
6. **NEW:** See table auto-filtering to date range

## Backward Compatibility

The function still works without dates:

```python
# Old way (still works)
shifts = await search_staff_shifts_by_name(page, "Alannah Courtnay")

# New way with dates
shifts = await search_staff_shifts_by_name(
    page, 
    "Alannah Courtnay",
    start_date="2025-12-16",
    end_date="2025-12-16"
)
```
