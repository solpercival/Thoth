"""
Credentials client for automation module.
Fetches admin credentials from the `credentials_api` service (or env override).
Returns credentials in the LLM-style dict expected by login modules.
"""
import os
import logging
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)

CREDENTIALS_API_URL = os.getenv("CREDENTIALS_API_URL", "http://localhost:5000")


def get_admin_credentials(service_name: str, role: str = "admin") -> Optional[Dict]:
    """
    Fetch admin credentials for a given service from the credentials API.

    Args:
        service_name: e.g. "hahs_vic3495" or "ezaango"
        role: logical role suffix; used to lookup a key like "{service_name}_admin" in the credentials API

    Returns:
        Credentials dict with keys expected by the login modules, or None on failure.
    """
    key = f"{service_name}_admin" if role == "admin" else service_name
    url = f"{CREDENTIALS_API_URL}/api/credentials/{key}"

    try:
        logger.info(f"Fetching admin credentials for {key} from {url}")
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        # Basic validation
        if "username" in data and "password" in data:
            return data
        logger.warning(f"Credentials API returned unexpected data for {key}: {data}")
        return None
    except Exception as e:
        logger.error(f"Failed to fetch credentials for {key}: {e}")
        return None
