"""
Orchestrator for checking Ezaango shifts and notifying coordinators.

This module logs in with admin credentials, scrapes the shift page,
parses shift data, filters real shifts, and notifies coordinators.

Usage (async):
    from check_shifts_handler import check_shifts_and_notify
    result = await check_shifts_and_notify(service_name="hahs_vic3495", notify_method="log")
"""
import os
import logging
from typing import List, Dict, Optional

try:
    from .secrets import get_admin_credentials
    from .shift_scraper import parse_shifts_from_html, filter_real_shifts, Shift
    from .notifier import notify_coordinator
    from .login_playwright import LoginAutomation
    from .website_configs_playwright import get_config
    from .staff_lookup import lookup_staff_by_phone, phones_match
except ImportError:
    from secrets import get_admin_credentials
    from shift_scraper import parse_shifts_from_html, filter_real_shifts, Shift
    from notifier import notify_coordinator
    from login_playwright import LoginAutomation
    from website_configs_playwright import get_config
    from staff_lookup import lookup_staff_by_phone, phones_match

logger = logging.getLogger(__name__)


async def check_shifts_and_notify(service_name: str, notify_method: str = "log", caller_phone: Optional[str] = None) -> Dict:
    """
    Check Ezaango shifts and notify coordinators.
    
    Workflow:
    1. Login to Ezaango
    2. If caller_phone provided: Look up staff by phone to get full name
    3. Scrape shifts page
    4. Filter shifts (by phone and/or name)
    5. Notify coordinators

    Args:
        service_name: Ezaango service identifier (e.g., 'hahs_vic3495')
        notify_method: Notification method - 'log' or 'email'
        caller_phone: Phone number of caller to filter shifts (optional)

    Returns:
        Dict with success status, number of shifts found, and notification results
    """
    # Get credentials from secrets
    admin_creds = get_admin_credentials(service_name)
    if not admin_creds:
        return {"success": False, "error": "Admin credentials not available"}

    # Get website config for Ezaango
    try:
        config = get_config(service_name)
    except Exception as e:
        return {"success": False, "error": f"No website config for {service_name}: {e}"}

    # Lookup staff member by phone if provided
    staff_info = None
    if caller_phone:
        logger.info(f"Looking up staff by phone: {caller_phone}")

    # Login and scrape
    try:
        async with LoginAutomation(headless=os.getenv("HEADLESS", "true").lower() == "true") as automation:
            success = await automation.login_with_retry(
                config=config,
                service_name=f"{service_name}_admin",
                llm_credentials=admin_creds
            )
            if not success:
                return {"success": False, "error": "Login failed"}

            # If caller_phone provided, lookup staff member first
            if caller_phone:
                page = await automation.get_page()
                if page:
                    staff_info = await lookup_staff_by_phone(page, caller_phone)
                    if staff_info:
                        logger.info(f"Found staff member: {staff_info['full_name']}")
                    else:
                        logger.warning(f"Staff member not found for phone: {caller_phone}")
                        # Continue anyway - will filter by phone instead
                else:
                    logger.warning("Could not access page for staff lookup")

            # Navigate to shifts page and scrape
            # Assume shifts are on the main page or we can navigate after login
            html = await automation.scrape_page_content()
    except Exception as e:
        logger.error(f"Login/scraping error: {e}")
        return {"success": False, "error": f"Login failed: {e}"}

    # Parse and filter shifts
    candidates = parse_shifts_from_html(html)
    
    # Filter by phone (and optionally by staff name if we found one)
    real_shifts = filter_real_shifts(candidates, caller_phone=caller_phone, staff_name=staff_info.get("full_name") if staff_info else None)

    # Build shift payload
    shifts_payload: List[Dict] = []
    for s in real_shifts:
        shifts_payload.append({
            "id": s.id,
            "worker_name": s.worker_name,
            "worker_phone": s.worker_phone,
            "client_name": s.client_name,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "status": s.status,
            "coordinator_contact": s.coordinator_contact,
        })

    # Notify coordinators
    notified = []
    if not shifts_payload:
        logger.info("No active shifts found")
    else:
        # Group shifts by coordinator
        by_coord = {}
        for s in shifts_payload:
            contact = s.get("coordinator_contact") or "__no_contact__"
            by_coord.setdefault(contact, []).append(s)

        # Notify each coordinator
        for contact, shifts in by_coord.items():
            if contact == "__no_contact__":
                notify_coordinator(None, shifts, method="log")
                notified.append({"contact": None, "count": len(shifts)})
            else:
                ok = notify_coordinator(contact, shifts, method=notify_method)
                notified.append({"contact": contact, "count": len(shifts), "sent": ok})

    return {
        "success": True,
        "shifts_found": len(shifts_payload),
        "notified": notified,
        "staff_info": staff_info  # Include staff lookup result
    }
    print(result)
