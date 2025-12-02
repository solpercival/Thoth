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
            # [ID, Worker, Client, Start, End, Status, Coordinator]
            id_ = cols[0] if len(cols) > 0 else None
            worker = cols[1] if len(cols) > 1 else None
            client = cols[2] if len(cols) > 2 else None
            start = cols[3] if len(cols) > 3 else None
            end = cols[4] if len(cols) > 4 else None
            status = cols[5] if len(cols) > 5 else None
            coord = cols[6] if len(cols) > 6 else None
            shifts.append(Shift(id=id_, worker_name=worker, client_name=client, start_time=start, end_time=end, status=status, coordinator_contact=coord))

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
            # try to find status keywords
            status = None
            for t in text:
                if t.lower() in ("active", "confirmed", "cancelled", "cancelled", "pending"):
                    status = t
                    break
            coord = None
            # try to find an email or phone-like token
            for t in text:
                if "@" in t or (t.replace("+", "").replace(" ", "").isdigit() and len(t) >= 7):
                    coord = t
                    break
            shifts.append(Shift(id=id_, worker_name=worker, client_name=client, start_time=None, end_time=None, status=status, coordinator_contact=coord))

    # Heuristic 3: List items
    if not shifts:
        lis = soup.select("ul.shifts li, ol.shifts li, li.shift")
        for li in lis:
            text = li.get_text("|", strip=True).split("|")
            shifts.append(Shift(id=None, worker_name=(text[0] if text else None), client_name=(text[1] if len(text) > 1 else None), start_time=None, end_time=None, status=None, coordinator_contact=None))

    logger.info(f"Parsed {len(shifts)} shift candidates from HTML")
    return shifts


def filter_real_shifts(shifts: List[Shift]) -> List[Shift]:
    """
    Heuristic filter to only keep shifts that appear real/active.
    For now: keep shifts that have a worker name and do not contain 'cancel' in status.
    """
    real = []
    for s in shifts:
        if s.worker_name and (not s.status or "cancel" not in (s.status or "").lower()):
            real.append(s)
    logger.info(f"Filtered {len(real)} real shifts from {len(shifts)} candidates")
    return real
