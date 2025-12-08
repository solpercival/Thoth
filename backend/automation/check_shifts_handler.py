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
from typing import List, Dict

try:
    from .secrets import get_admin_credentials
    from .shift_scraper import parse_shifts_from_html, filter_real_shifts, Shift
    from .notifier import notify_coordinator
    from .login_playwright import LoginAutomation
    from .website_configs_playwright import get_config
except ImportError:
    from secrets import get_admin_credentials
    from shift_scraper import parse_shifts_from_html, filter_real_shifts, Shift
    from notifier import notify_coordinator
    from login_playwright import LoginAutomation
    from website_configs_playwright import get_config

logger = logging.getLogger(__name__)


async def check_shifts_and_notify(service_name: str, notify_method: str = "log") -> Dict:
    """
    Check Ezaango shifts and notify coordinators.

    Args:
        service_name: Ezaango service identifier (e.g., 'hahs_vic3495')
        notify_method: Notification method - 'log' or 'email'

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

            html = await automation.scrape_page_content()
    except Exception as e:
        logger.error(f"Login/scraping error: {e}")
        return {"success": False, "error": f"Login failed: {e}"}

    # Parse and filter shifts
    candidates = parse_shifts_from_html(html)
    real_shifts = filter_real_shifts(candidates)

    # Build shift payload
    shifts_payload: List[Dict] = []
    for s in real_shifts:
        shifts_payload.append({
            "id": s.id,
            "worker_name": s.worker_name,
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

    return {"success": True, "shifts_found": len(shifts_payload), "notified": notified}
    print(result)
