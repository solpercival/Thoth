"""
Unified secrets management for all sensitive data.
Reads from .env file (gitignored, never committed).

Priority order:
1. Environment variables (highest security)
2. .env file in workspace root
3. Fallback defaults (testing only)
"""

import os
import logging
from pathlib import Path
from typing import Optional
import pyotp

logger = logging.getLogger(__name__)


class Secrets:
    """
    Central secrets manager.
    
    Reads from .env file (gitignored, never committed to version control).
    See .env.example for configuration format.
    """
    
    _instance = None
    _env_file: Optional[Path] = None
    _cache: dict = {}
    
    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize secrets manager.
        
        Args:
            env_file: Path to .env file (defaults to workspace root/.env)
        """
        if env_file:
            self._env_file = Path(env_file)
        else:
            # Find workspace root (3 levels up from this file)
            self._env_file = Path(__file__).parent.parent.parent / ".env"
        
        self._cache = {}
        self._load_env_file()
    
    def _load_env_file(self):
        """Load variables from .env file if it exists."""
        if self._env_file and self._env_file.exists():
            try:
                with open(self._env_file, 'r') as f:
                    for line in f:
                        line = line.strip()
                        # Skip comments and empty lines
                        if not line or line.startswith('#'):
                            continue
                        # Parse KEY=VALUE
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            # Remove quotes if present
                            if value.startswith('"') and value.endswith('"'):
                                value = value[1:-1]
                            elif value.startswith("'") and value.endswith("'"):
                                value = value[1:-1]
                            self._cache[key] = value
                logger.debug(f"Loaded secrets from {self._env_file}")
            except Exception as e:
                logger.warning(f"Failed to load .env file: {e}")
    
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get secret value.
        
        Priority:
        1. Environment variable
        2. .env cache
        3. Default value
        
        Args:
            key: Secret key (e.g., 'ADMIN_USERNAME_HAHS_VIC3495')
            default: Default value if not found
            
        Returns:
            Secret value or default
        """
        # Try environment variable first
        if key in os.environ:
            return os.environ[key]
        
        # Try .env cache
        if key in self._cache:
            return self._cache[key]
        
        # Return default
        if default is not None:
            logger.debug(f"Secret {key} not found, using default")
        return default
    
    def set(self, key: str, value: str):
        """
        Store secret in memory cache (not persisted to .env).
        
        Args:
            key: Secret key
            value: Secret value
        """
        self._cache[key] = value
        logger.debug(f"Cached secret {key}")


# Global instance
_secrets_instance = None


def _get_secrets_instance() -> Secrets:
    """Get or create global secrets instance."""
    global _secrets_instance
    if _secrets_instance is None:
        _secrets_instance = Secrets()
    return _secrets_instance


# ============================================================================
# Public API Functions
# ============================================================================

def get_admin_credentials(service_name: str) -> dict:
    """
    Get admin credentials for a service from .env.
    
    Args:
        service_name: Service identifier (e.g., 'hahs_vic3495')
        
    Returns:
        Dict with 'username' and 'password' keys, or empty dict if not found
        
    Example:
        creds = get_admin_credentials('hahs_vic3495')
        # Returns: {
        #     'username': 'helpdesk@helpathandsupport.com.au',
        #     'password': 'secret123'
        # }
    """
    secrets = _get_secrets_instance()
    service_upper = service_name.upper()
    
    username = secrets.get(f"ADMIN_USERNAME_{service_upper}")
    password = secrets.get(f"ADMIN_PASSWORD_{service_upper}")
    
    if not username or not password:
        logger.warning(f"Admin credentials not found for {service_name}")
        return {}
    
    return {
        'username': username,
        'password': password
    }


def get_admin_totp_secret(service_name: str) -> Optional[str]:
    """
    Get TOTP secret for a service.
    
    Args:
        service_name: Service identifier (e.g., 'hahs_vic3495')
        
    Returns:
        Base32-encoded TOTP secret or None if not found
        
    Example:
        secret = get_admin_totp_secret('hahs_vic3495')
        # Returns: 'JBSWY3DPEBLW64TMMQ======'
    """
    secrets = _get_secrets_instance()
    service_upper = service_name.upper()
    secret = secrets.get(f"TOTP_SECRET_{service_upper}")
    
    if not secret:
        logger.warning(f"TOTP secret not found for {service_name}")
        return None
    
    return secret


def get_admin_totp_code(service_name: str) -> Optional[str]:
    """
    Generate current 6-digit TOTP code for a service.
    
    Args:
        service_name: Service identifier (e.g., 'hahs_vic3495')
        
    Returns:
        Current 6-digit TOTP code or None if secret not found
        
    Example:
        code = get_admin_totp_code('hahs_vic3495')
        # Returns: '927693'
    """
    secret = get_admin_totp_secret(service_name)
    if not secret:
        return None
    
    try:
        totp = pyotp.TOTP(secret)
        code = totp.now()
        logger.debug(f"Generated TOTP code for {service_name}: {code}")
        return code
    except Exception as e:
        logger.error(f"Failed to generate TOTP code for {service_name}: {e}")
        return None


def get_smtp_config() -> dict:
    """
    Get SMTP configuration from .env.
    
    Returns:
        Dict with SMTP settings, or empty dict if not configured
        
    Example:
        config = get_smtp_config()
        # Returns: {
        #     'host': 'smtp.gmail.com',
        #     'port': 587,
        #     'user': 'email@gmail.com',
        #     'password': 'app_password',
        #     'from_address': 'noreply@example.com'
        # }
    """
    secrets = _get_secrets_instance()
    
    host = secrets.get('SMTP_HOST')
    port = secrets.get('SMTP_PORT')
    user = secrets.get('SMTP_USER')
    password = secrets.get('SMTP_PASS')
    from_address = secrets.get('NOTIFIER_FROM', 'no-reply@example.com')
    
    if not all([host, port, user, password]):
        logger.debug("SMTP not fully configured")
        return {}
    
    return {
        'host': host,
        'port': int(port) if port else 587,
        'user': user,
        'password': password,
        'from_address': from_address
    }


def verify_secrets_configured(service_name: str) -> bool:
    """
    Verify that all required secrets are configured for a service.
    
    Args:
        service_name: Service identifier (e.g., 'hahs_vic3495')
        
    Returns:
        True if credentials and TOTP secret are configured
    """
    creds = get_admin_credentials(service_name)
    totp = get_admin_totp_secret(service_name)
    
    if not creds or not totp:
        logger.warning(f"Secrets not fully configured for {service_name}")
        return False
    
    return True


def generate_totp_secret() -> str:
    """
    Generate a new random TOTP secret.
    
    Returns:
        Base32-encoded secret suitable for QR code scanning
        
    Example:
        secret = generate_totp_secret()
        print(f"Add this to your authenticator app: {secret}")
    """
    secret = pyotp.random_base32()
    logger.info(f"Generated new TOTP secret (first 4 chars): {secret[:4]}...***")
    return secret


def get_provisioning_uri(service_name: str, secret: str) -> str:
    """
    Get QR code provisioning URI for authenticator app setup.
    
    Args:
        service_name: Service identifier
        secret: TOTP secret
        
    Returns:
        otpauth:// URI for QR code
    """
    totp = pyotp.TOTP(secret)
    account_name = f"Shift Admin ({service_name})"
    return totp.provisioning_uri(account_name, issuer_name="Thoth")
