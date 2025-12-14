# Staff Lookup Testing Guide

## Quick Start

### Option 1: Run Quick Test (Recommended)

```bash
cd backend/automation
python quick_test_staff.py "0490024573"
```

**What it does:**
1. Opens Ezaango login page (browser visible so you can watch)
2. Logs in with admin credentials from `.env`
3. Navigates to `/staff/4` (staff page)
4. Searches for the phone number
5. Extracts and prints the full name + all staff details

**Example Output:**
```
🔍 Looking up staff with phone: 0490024573
Opening browser... (headless=False for visibility)

📍 Logging in...
✓ Login successful
📍 Navigating to staff search...

======================================================================
✓ FOUND!
======================================================================
  Full Name:   Ms Adaelia Thomas
  Staff ID:    1728
  Mobile:      0490024573
  Email:       adaeliathomas@gmail.com
  Team:        VIC Team
  Status:      Active
  Address:     836 Highbury Rd, Glen Waverley VIC 3150, Australia
======================================================================
```

---

## Test Different Phone Formats

The lookup supports various Australian phone formats:

```bash
# All these should find the same person:
python quick_test_staff.py "0490024573"
python quick_test_staff.py "+61490024573"
python quick_test_staff.py "+61 490 024 573"
python quick_test_staff.py "0490 024 573"
```

---

## Option 2: Interactive Test Mode

For testing multiple phone numbers:

```bash
cd backend/automation
python test_staff_lookup.py
```

**Features:**
- Prompts for phone number
- Shows results
- Keeps browser open between searches
- Type 'quit' to exit

**Example Session:**
```
============================================================
STAFF LOOKUP TEST
============================================================

Supported phone formats:
  - +61412345678
  - +61 412 345 678
  - 0412345678
  - 0412 345 678

============================================================

Enter phone number to search (or 'quit' to exit): 0490024573

Searching for staff with phone: 0490024573

✓ SUCCESS! Found: Ms Adaelia Thomas
```

---

## Option 3: Batch Testing

Test multiple phone numbers at once:

```bash
python test_staff_lookup.py "0490024573" "+61412345678" "0412 345 678"
```

**Output:**
```
============================================================
BATCH TEST SUMMARY
============================================================
✓ 0490024573          → Ms Adaelia Thomas
✓ +61412345678        → John Smith
✗ 0412 345 678        → NOT FOUND
============================================================
```

---

## Prerequisites

Before running tests, make sure:

1. **Virtual environment activated:**
   ```bash
   cd thoth
   .\venv\Scripts\Activate.ps1
   ```

2. **Required packages installed:**
   ```bash
   pip install playwright beautifulsoup4 python-dotenv
   ```

3. **.env file configured** with:
   ```
   ADMIN_USERNAME_HAHS_VIC3495=your_admin_username
   ADMIN_PASSWORD_HAHS_VIC3495=your_admin_password
   TOTP_SECRET_HAHS_VIC3495=your_totp_secret
   ```

---

## Troubleshooting

### Login Fails

**Problem:** "Login failed" message

**Solutions:**
1. Check `.env` file has correct credentials
2. Check if Ezaango website is accessible
3. Verify TOTP secret is correct
4. Try login manually to verify credentials work

### Staff Not Found

**Problem:** "No staff found for phone: XXX"

**Solutions:**
1. Check if phone number is correct (no typos)
2. Verify staff member exists in Ezaango system
3. Check if phone is stored in a different format in Ezaango
4. Look at the console output to see what was searched

### HTML Parsing Issues

**Problem:** Staff lookup runs but returns empty/wrong data

**Solutions:**
1. The HTML structure might have changed
2. Staff search results show up differently
3. Table column order might be different

**Debug:**
- Screenshot the staff search results page
- Check what HTML structure Ezaango is using
- Update selectors in `staff_lookup.py` if needed

---

## What Gets Returned

When a staff member is found, the script returns a dictionary with:

```python
{
    "id": "1728",                                    # Staff ID
    "full_name": "Ms Adaelia Thomas",               # Full name
    "email": "adaeliathomas@gmail.com",             # Email address
    "team": "VIC Team",                             # Team name
    "mobile": "0490024573",                         # Mobile number
    "status": "Active",                             # Account status
    "address": "836 Highbury Rd, Glen Waverley..." # Full address
}
```

---

## Testing with Your Own Data

You likely have staff member phone numbers. Test with them:

```bash
# Test with known staff phone numbers
python quick_test_staff.py "0412345678"   # Replace with actual number
python quick_test_staff.py "0498765432"   # Replace with actual number
```

This will verify the lookup works with your actual Ezaango data.

---

## Next Steps

Once testing confirms staff lookup works:

1. **Integrate into shift checking:**
   ```python
   # In check_shifts_handler.py
   result = await check_shifts_and_notify(
       service_name="hahs_vic3495",
       caller_phone="0490024573"  # From 3CX webhook
   )
   print(f"Found: {result['staff_info']['full_name']}")
   ```

2. **Add to voice pipeline:**
   - Extract phone from 3CX webhook
   - Look up staff name
   - Use name to filter shifts
   - Convert results to speech

3. **Production deployment:**
   - Automate staff lookups on incoming calls
   - Cache results for performance
   - Log all lookups for audit trail

---

## Support

If tests fail, check:
- Console output for error messages
- Browser window for what the script is doing
- `.env` file for credential issues
- Ezaango website structure (might have changed)
