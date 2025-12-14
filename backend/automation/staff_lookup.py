"""
Staff lookup by phone number.

Uses Ezaango's staff search page (/staff/4) to find employee details
by phone number. Returns the full name which can then be used to filter shifts.
"""
import logging
from typing import Optional, Dict
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def _remove_title(full_name: str) -> str:
    """
    Remove common titles/modifiers from full name.
    
    Examples:
    - "Ms Alannah Courtnay" → "Alannah Courtnay"
    - "Mr John Smith" → "John Smith"
    - "Dr Jane Doe" → "Jane Doe"
    - "Prof. Robert Johnson" → "Robert Johnson"
    
    Args:
        full_name: Full name with possible title prefix
    
    Returns:
        Name with title removed
    """
    titles = [
        "Ms.", "Ms", "Mr.", "Mr", "Dr.", "Dr", "Prof.", "Prof",
        "Sir", "Dame", "Mrs.", "Mrs", "Miss.", "Miss",
        "Rev.", "Rev", "Fr.", "Fr", "Reverend", "Father",
        "Mx.", "Mx"
    ]
    
    # Split and check first word
    parts = full_name.split()
    if parts and parts[0] in titles:
        return " ".join(parts[1:])
    
    return full_name


async def lookup_staff_by_phone(page, phone_number: str) -> Optional[Dict]:
    """
    Look up staff member by phone number on the Ezaango staff page.
    
    Steps:
    1. Navigate to /staff/4 page
    2. Fill the search box with phone number
    3. Wait for results table
    4. Extract first result: ID, Full Name, Email, Team, Mobile, Status
    
    Args:
        page: Playwright page object (already logged in)
        phone_number: Phone number to search for (e.g., "+61412345678" or "0412345678")
    
    Returns:
        Dict with staff details if found, None if not found
        {
            "id": "1728",
            "full_name": "Ms Adaelia Thomas",
            "email": "adaeliathomas@gmail.com",
            "team": "VIC Team",
            "mobile": "0490024573",
            "status": "Active",
            "address": "836 Highbury Rd, Glen Waverley VIC 3150, Australia"
        }
    """
    try:
        # Navigate to staff page
        logger.info(f"Navigating to staff page to lookup phone: {phone_number}")
        await page.goto("https://hahs-vic3495.ezaango.app/staff/4", wait_until="networkidle")
        logger.info(f"Page URL after navigation: {page.url}")
        
        # Check if we're still on a login page (indicates authentication failure)
        if "login" in page.url.lower():
            logger.error("Still on login page after navigation - authentication may have failed")
            logger.error(f"Current URL: {page.url}")
            return None
        
        # Wait for page to load and search box to appear
        logger.info("Waiting for search input...")
        await page.wait_for_selector("input[type='search'].form-control", timeout=15000)
        logger.info("Search input found")
        
        # Find and fill the search box
        search_input = await page.query_selector("input[type='search'].form-control")
        if not search_input:
            logger.error("Could not find search input on staff page")
            return None
        
        await search_input.fill(phone_number)
        logger.info(f"Filled search box with: {phone_number}")
        
        # Wait for results to filter (give it more time to update the table)
        logger.info("Waiting for search results to filter...")
        await page.wait_for_timeout(3000)  # DataTables filters async, give it time
        
        # Get table content
        table_html = await page.content()
        soup = BeautifulSoup(table_html, "html.parser")
        
        # Find the task-table and get first row
        table = soup.find("table", {"id": "task-table"})
        if not table:
            logger.warning(f"No staff found matching phone: {phone_number}")
            logger.debug("Task table not found in page - possible search yielded no results")
            return None
        
        # Get first tbody row
        tbody = table.find("tbody")
        if not tbody:
            logger.warning(f"Table has no body for phone: {phone_number}")
            return None
        
        rows = tbody.find_all("tr")
        if not rows:
            logger.warning(f"No rows found in staff table for phone: {phone_number}")
            return None
        
        first_row = rows[0]
        tds = first_row.find_all("td")
        
        # Extract data from columns
        # Expected order: [Email checkbox], ID, Full Name, Team, Email, Mobile No, Address, Status, Action
        if len(tds) < 8:
            logger.warning(f"Unexpected table structure, fewer columns than expected")
            return None
        
        # Column indices (accounting for checkbox column at index 0)
        full_name_raw = tds[2].get_text(strip=True)
        full_name_clean = _remove_title(full_name_raw)
        
        staff_info = {
            "id": tds[1].get_text(strip=True),
            "full_name": full_name_clean,  # Contains link, get text and remove title
            "team": tds[3].get_text(strip=True),
            "email": tds[4].get_text(strip=True),
            "mobile": tds[5].get_text(strip=True),
            "address": tds[6].get_text(strip=True),
            "status": tds[7].get_text(strip=True),
        }
        
        logger.info(f"Found staff: {staff_info['full_name']} (ID: {staff_info['id']})")
        return staff_info
        
    except Exception as e:
        logger.error(f"Error during staff lookup for {phone_number}: {e}")
        import traceback
        traceback.print_exc()
        return None


def normalize_phone(phone: str) -> str:
    """
    Normalize phone number for comparison.
    Removes: +, -, spaces, leading 0 (for Australian numbers)
    
    Examples:
    - "+61 412 345 678" → "61412345678"
    - "0412 345 678" → "61412345678" 
    - "+61412345678" → "61412345678"
    """
    # Remove +, -, spaces
    normalized = phone.replace("+", "").replace("-", "").replace(" ", "")
    
    # Convert leading 0 to 61 (Australian numbers)
    if normalized.startswith("0"):
        normalized = "61" + normalized[1:]
    
    return normalized


def phones_match(phone1: str, phone2: str) -> bool:
    """
    Check if two phone numbers match (handles various formats).
    
    Args:
        phone1: First phone number
        phone2: Second phone number
    
    Returns:
        True if phones match (normalized), False otherwise
    """
    norm1 = normalize_phone(phone1)
    norm2 = normalize_phone(phone2)
    return norm1 == norm2


async def search_staff_shifts_by_name(page, staff_name: str) -> list:
    """
    Search for all shifts by staff name on Ezaango search page.
    
    Navigates to: https://hahs-vic3495.ezaango.app/search?keyword=name+name
    Parses table rows to extract shift information.
    
    Handles:
    - Multiple shifts per day for same staff
    - Repeated clients (client may appear multiple times with different times)
    - Extracting date and time from client_info string
    
    Args:
        page: Playwright page object (already logged in)
        staff_name: Staff name to search for (e.g., "Alannah Courtnay")
    
    Returns:
        List of dicts with shift details:
        [
            {
                "type": "Shift",
                "staff_name": "Alannah Courtnay",
                "client_name": "Anthea Bassi",
                "date": "08-11-2025",
                "time": "12:00 PM",
                "client_info": "Anthea Bassi on 08-11-2025 at 12:00 PM",
                "shift_id": "196437",
                "shift_url": "https://hahs-vic3495.ezaango.app/roster/196437"
            },
            ...
        ]
    """
    try:
        # Format search URL with staff name (spaces become +)
        search_name = staff_name.replace(" ", "+")
        search_url = f"https://hahs-vic3495.ezaango.app/search?keyword={search_name}"
        
        logger.info(f"Searching for shifts by staff name: {staff_name}")
        logger.info(f"Navigating to: {search_url}")
        
        await page.goto(search_url, wait_until="networkidle")
        logger.info(f"Page URL: {page.url}")
        
        # Wait for results table to load
        await page.wait_for_selector("table tbody tr", timeout=10000)
        logger.info("Results table found")
        
        # Get page content and parse with BeautifulSoup
        table_html = await page.content()
        soup = BeautifulSoup(table_html, "html.parser")
        
        # Find all table rows with role="row"
        rows = soup.find_all("tr", {"role": "row"})
        if not rows:
            logger.info(f"No shifts found for staff: {staff_name}")
            return []
        
        shifts = []
        for row in rows:
            try:
                tds = row.find_all("td")
                if len(tds) < 3:
                    continue
                
                # Extract columns: Type | Staff Name | Client Info
                shift_type = tds[0].get_text(strip=True)
                found_staff_name = tds[1].get_text(strip=True)
                client_info_raw = tds[2].get_text(strip=True)
                
                # Extract shift_id from data-href attribute
                # Example: data-href="https://hahs-vic3495.ezaango.app/roster/196437"
                shift_link = row.get("data-href", "")
                shift_id = shift_link.split("/")[-1] if shift_link else None
                
                # Parse client_info: "Client Name on DD-MM-YYYY at HH:MM AM/PM"
                # Example: "Anthea Bassi on 08-11-2025 at 12:00 PM"
                client_name = None
                date = None
                time = None
                
                if " on " in client_info_raw and " at " in client_info_raw:
                    # Split by " on " to get client name and rest
                    parts = client_info_raw.split(" on ")
                    client_name = parts[0].strip()
                    
                    # Split rest by " at " to get date and time
                    remainder = parts[1] if len(parts) > 1 else ""
                    if " at " in remainder:
                        date_time_split = remainder.split(" at ")
                        date = date_time_split[0].strip()
                        time = date_time_split[1].strip() if len(date_time_split) > 1 else None
                
                shift_data = {
                    "type": shift_type,
                    "staff_name": found_staff_name,
                    "client_name": client_name,
                    "date": date,
                    "time": time,
                    "client_info": client_info_raw,
                    "shift_id": shift_id,
                    "shift_url": shift_link
                }
                
                shifts.append(shift_data)
                logger.debug(f"Parsed shift: {client_name} on {date} at {time} (ID: {shift_id})")
                
            except Exception as e:
                logger.warning(f"Error parsing row: {e}")
                continue
        
        logger.info(f"Found {len(shifts)} shifts for {staff_name}")
        return shifts
        
    except Exception as e:
        logger.error(f"Error searching for shifts by name {staff_name}: {e}")
        import traceback
        traceback.print_exc()
        return []
