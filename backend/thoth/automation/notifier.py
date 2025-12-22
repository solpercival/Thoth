"""
Notifier utilities for automation.
Provides a simple `notify_coordinator` function which currently logs the message
and — if SMTP is configured in .env — sends an email.
"""
import logging
from typing import List, Optional
import smtplib
from email.message import EmailMessage

try:
    from .secrets import get_smtp_config
except ImportError:
    from secrets import get_smtp_config

logger = logging.getLogger(__name__)

# Load SMTP config from .env
_smtp_config = get_smtp_config()
SMTP_HOST = _smtp_config.get('host')
SMTP_PORT = _smtp_config.get('port')
SMTP_USER = _smtp_config.get('user')
SMTP_PASS = _smtp_config.get('password')
FROM_ADDRESS = _smtp_config.get('from_address', 'no-reply@example.com')


def _format_shifts_summary(shifts: List[dict]) -> str:
    lines = ["Shifts found:"]
    for s in shifts:
        lines.append(f"- ID: {s.get('id')}, Worker: {s.get('worker_name')}, Client: {s.get('client_name')}, Start: {s.get('start_time')}, Status: {s.get('status')}")
    return "\n".join(lines)


def notify_coordinator(coordinator_contact: Optional[str], shifts: List[dict], subject: Optional[str] = None, method: str = "log") -> bool:
    """
    Notify the coordinator about found shifts.
    - If method == "log": just log the message
    - If method == "email" and SMTP_* env vars are present: send an email

    coordinator_contact: email address preferred; if None, logs the message instead.
    shifts: list of dicts with shift details
    Returns True on success (or logged), False on failure to send.
    """
    subject = subject or "Shift check results"
    body = _format_shifts_summary(shifts)

    # If only logging is requested or no coordinator contact configured, log and return
    if method == "log" or not coordinator_contact:
        logger.info(f"Notify ({method}): {subject}\n{body}")
        return True

    # If email is requested, try to send via SMTP
    if method == "email":
        if not SMTP_HOST or not SMTP_USER or not SMTP_PASS or not SMTP_PORT:
            logger.warning("SMTP not fully configured; falling back to log")
            logger.info(f"{subject}\n{body}")
            return False

        try:
            msg = EmailMessage()
            msg["From"] = FROM_ADDRESS
            msg["To"] = coordinator_contact
            msg["Subject"] = subject
            msg.set_content(body)

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
                s.starttls()
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)

            logger.info(f"Email sent to {coordinator_contact}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {coordinator_contact}: {e}")
            return False

    logger.warning(f"Unknown notification method: {method}; falling back to log")
    logger.info(f"{subject}\n{body}")
    return True
