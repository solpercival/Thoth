"""
Simple HTML shift scraper utilities.
This file contains generic, best-effort parsing helpers that convert
login page HTML into a list of structured `Shift` objects.

Because website structure varies, these helpers try a few heuristics
(table rows, divs with class 'shift', list items) and return a list of
candidates. You should customize selectors for the real Ezaango pages
once you inspect them.
"""
from dataclasses import dataclass
from typing import List, Optional
import logging

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class Shift:
    id: Optional[str]
    worker_name: Optional[str]
    worker_phone: Optional[str]  # Caller's phone number for matching
    client_name: Optional[str]
    start_time: Optional[str]
    end_time: Optional[str]
    status: Optional[str]
    coordinator_contact: Optional[str]


def parse_shifts_from_html(html: str) -> List[Shift]:
    """
    Parse HTML and return a list of Shift dataclasses.
    This is intentionally generic — update selectors after inspecting the real pages.
    """
    soup = BeautifulSoup(html, "html.parser")
    shifts: List[Shift] = []

    # Heuristic 1: Table rows
    table_rows = soup.select("table tr")
    if len(table_rows) > 1:
        for tr in table_rows[1:]:
            cols = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
            if not cols:
                continue
            # Basic mapping: try to guess columns
            # [ID, Worker, Phone, Client, Start, End, Status, Coordinator]
            id_ = cols[0] if len(cols) > 0 else None
            worker = cols[1] if len(cols) > 1 else None
            phone = cols[2] if len(cols) > 2 else None
            client = cols[3] if len(cols) > 3 else None
            start = cols[4] if len(cols) > 4 else None
            end = cols[5] if len(cols) > 5 else None
            status = cols[6] if len(cols) > 6 else None
            coord = cols[7] if len(cols) > 7 else None
            shifts.append(Shift(id=id_, worker_name=worker, worker_phone=phone, client_name=client, start_time=start, end_time=end, status=status, coordinator_contact=coord))

    # Heuristic 2: Divs with class 'shift'
    if not shifts:
        divs = soup.select(".shift, .shift-row, .shift-item")
        for d in divs:
            text = d.get_text("|", strip=True).split("|")
            # try to map some fields
            id_attr = d.get("data-shift-id")
            id_ = str(id_attr) if id_attr else (text[0] if len(text) > 0 else None)
            worker = text[1] if len(text) > 1 else None
            client = text[2] if len(text) > 2 else None
            status = None
            phone = None
            coord = None
            # try to find status keywords and phone/email
            for t in text:
                if t.lower() in ("active", "confirmed", "cancelled", "pending"):
                    status = t
                # try to extract phone (7+ digits, possibly with +, -, spaces)
                if phone is None and t.replace("+", "").replace("-", "").replace(" ", "").isdigit() and len(t.replace("+", "").replace("-", "").replace(" ", "")) >= 7:
                    phone = t
                # try to extract email or second phone (for coordinator)
                if "@" in t:
                    coord = t
                elif coord is None and phone is not None and t.replace("+", "").replace("-", "").replace(" ", "").isdigit() and len(t.replace("+", "").replace("-", "").replace(" ", "")) >= 7:
                    coord = t
            shifts.append(Shift(id=id_, worker_name=worker, worker_phone=phone, client_name=client, start_time=None, end_time=None, status=status, coordinator_contact=coord))

    # Heuristic 3: List items
    if not shifts:
        lis = soup.select("ul.shifts li, ol.shifts li, li.shift")
        for li in lis:
            text = li.get_text("|", strip=True).split("|")
            worker = text[0] if text else None
            phone = None
            client = text[1] if len(text) > 1 else None
            # Try to find phone in remaining text
            for t in text[2:]:
                if phone is None and t.replace("+", "").replace("-", "").replace(" ", "").isdigit() and len(t.replace("+", "").replace("-", "").replace(" ", "")) >= 7:
                    phone = t
                    break
            shifts.append(Shift(id=None, worker_name=worker, worker_phone=phone, client_name=client, start_time=None, end_time=None, status=None, coordinator_contact=None))

    logger.info(f"Parsed {len(shifts)} shift candidates from HTML")
    return shifts


def filter_real_shifts(shifts: List[Shift], caller_phone: Optional[str] = None, staff_name: Optional[str] = None) -> List[Shift]:
    """
    Heuristic filter to only keep shifts that appear real/active.
    Optionally filter by caller phone number and/or staff name.
    
    Args:
        shifts: List of shift candidates from HTML
        caller_phone: Phone number to filter by (optional)
        staff_name: Staff member's full name to filter by (optional)
    
    Returns:
        Filtered list of real/active shifts
    """
    real = []
    for s in shifts:
        # Check if shift is real (has worker name and not cancelled)
        if not (s.worker_name and (not s.status or "cancel" not in (s.status or "").lower())):
            continue
        
        matched = False
        
        # If staff_name provided, prioritize matching by name first
        if staff_name:
            # Case-insensitive name matching (handles titles like "Ms", "Mr", etc)
            if staff_name.lower() in s.worker_name.lower() or s.worker_name.lower() in staff_name.lower():
                matched = True
                logger.info(f"Shift {s.id} matched to staff by name: {staff_name}")
        
        # If phone provided, also check phone match
        if caller_phone and not matched:
            # Normalize phone numbers for comparison (remove spaces, dashes, +)
            normalized_caller = caller_phone.replace("+", "").replace("-", "").replace(" ", "")
            normalized_shift = (s.worker_phone or "").replace("+", "").replace("-", "").replace(" ", "")
            
            # Match if worker phone matches caller or worker name contains caller phone
            if normalized_shift and (normalized_caller in normalized_shift or normalized_shift in normalized_caller):
                matched = True
                logger.info(f"Shift {s.id} matched to caller by phone {caller_phone}")
            else:
                logger.debug(f"Shift {s.id} skipped: phone mismatch (shift={s.worker_phone}, caller={caller_phone})")
        
        # If neither staff_name nor caller_phone provided, include all real shifts
        if not staff_name and not caller_phone:
            matched = True
        
        if matched:
            real.append(s)
    
    filter_msg = "Filtered"
    if staff_name:
        filter_msg += f" by staff name '{staff_name}'"
    if caller_phone:
        filter_msg += f" by phone '{caller_phone}'"
    
    logger.info(f"{filter_msg}: {len(real)} real shifts from {len(shifts)} candidates")
    return real
