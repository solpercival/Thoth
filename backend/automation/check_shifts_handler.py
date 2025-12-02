"""
Orchestrator for the "check shifts" intent.
This module does NOT perform cancellations. It logs in with admin credentials,
loads the page HTML via the Playwright automation, parses shifts, filters them,
and returns structured results (and optionally notifies the coordinator).

Usage (async):
    from check_shifts_handler import check_shifts_and_notify
    await check_shifts_and_notify(service_name="hahs_vic3495", notify_method="log")
"""
import os
import logging
from typing import List, Dict, Optional
import asyncio

from .credentials_client import get_admin_credentials
from .shift_scraper import parse_shifts_from_html, filter_real_shifts, Shift
from .notifier import notify_coordinator

try:
    from .login_playwright import LoginAutomation
    from .website_configs_playwright import get_config
except Exception:
    from login_playwright import LoginAutomation
    from website_configs_playwright import get_config

logger = logging.getLogger(__name__)


async def check_shifts_and_notify(service_name: str, notify_method: str = "log") -> Dict:
    """
    Main entrypoint to check shifts for a service and notify coordinators.

    Steps:
    1. Fetch admin credentials from credentials_api
    2. Use Playwright login automation to log in (re-using stored session if available)
    3. Scrape page HTML
    4. Parse and filter shifts
    5. Notify coordinator(s) via notifier

    Returns a dict with summary information.
    """
    admin_creds = get_admin_credentials(service_name)
    if not admin_creds:
        return {"success": False, "error": "Admin credentials not available"}

    # Get website config
    try:
        config = get_config(service_name)
    except Exception as e:
        return {"success": False, "error": f"No website config for {service_name}: {e}"}

    # Login via Playwright automation
    async with LoginAutomation(headless=os.getenv("HEADLESS", "true").lower() == "true") as automation:
        success = await automation.login_with_retry(config=config, service_name=f"{service_name}_admin", llm_credentials=admin_creds)
        if not success:
            return {"success": False, "error": "Login failed"}

        # Scrape HTML
        html = await automation.scrape_page_content()

    # Parse shifts
    candidates = parse_shifts_from_html(html)
    real_shifts = filter_real_shifts(candidates)

    # Prepare dicts for notification
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

    # Notify per-coordinator if contact present, otherwise log
    notified = []
    if not shifts_payload:
        logger.info("No active shifts found to report")
    else:
        # group by coordinator_contact
        by_coord = {}
        for s in shifts_payload:
            key = s.get("coordinator_contact") or "__no_contact__"
            by_coord.setdefault(key, []).append(s)

        for coord, shifts in by_coord.items():
            if coord == "__no_contact__":
                # Log these shifts
                notify_coordinator(None, shifts, method="log")
                notified.append({"contact": None, "count": len(shifts)})
            else:
                ok = notify_coordinator(coord, shifts, method=notify_method)
                notified.append({"contact": coord, "count": len(shifts), "sent": ok})

    return {"success": True, "shifts_found": len(shifts_payload), "notified": notified}


# Small CLI runner for debugging
if __name__ == "__main__":
    import sys
    svc = sys.argv[1] if len(sys.argv) > 1 else "hahs_vic3495"
    method = sys.argv[2] if len(sys.argv) > 2 else "log"

    result = asyncio.run(check_shifts_and_notify(svc, notify_method=method))
    print(result)
