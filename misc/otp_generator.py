"""
OTP Code Generator
Generates TOTP (Time-based One-Time Password) codes for authentication.
"""

import hmac
import hashlib
import struct
import time
import sys


def generate_totp(secret: str, interval: int = 30) -> str:
    """
    Generate a TOTP code from a base32-encoded secret.

    Args:
        secret: Base32-encoded secret key (spaces and case are ignored)
        interval: Time step in seconds (default 30)

    Returns:
        6-digit OTP code as string
    """
    # Clean the secret: remove spaces, convert to uppercase
    secret = secret.replace(" ", "").upper()

    # Add padding if necessary for base32 decoding
    padding = 8 - (len(secret) % 8)
    if padding != 8:
        secret += "=" * padding

    # Decode base32 secret
    import base64
    try:
        key = base64.b32decode(secret)
    except Exception as e:
        raise ValueError(f"Invalid base32 secret: {e}")

    # Get current time counter
    counter = int(time.time()) // interval

    # Convert counter to 8-byte big-endian
    counter_bytes = struct.pack(">Q", counter)

    # Generate HMAC-SHA1
    hmac_hash = hmac.new(key, counter_bytes, hashlib.sha1).digest()

    # Dynamic truncation
    offset = hmac_hash[-1] & 0x0F
    truncated = struct.unpack(">I", hmac_hash[offset:offset + 4])[0]
    truncated &= 0x7FFFFFFF

    # Get 6-digit code
    code = truncated % 1000000

    return f"{code:06d}"


def get_time_remaining(interval: int = 30) -> int:
    """Get seconds remaining until the current OTP expires."""
    return interval - (int(time.time()) % interval)


def main():
    if len(sys.argv) < 2:
        print("Usage: python otp_generator.py <base32_secret>")
        print("\nExample:")
        print("  python otp_generator.py JBSWY3DPEHPK3PXP")
        print("\nYou can find your secret in your authenticator app setup,")
        print("or from the service's 2FA configuration page.")
        sys.exit(1)

    secret = sys.argv[1]

    try:
        code = generate_totp(secret)
        remaining = get_time_remaining()
        print(f"OTP: {code}")
        print(f"Valid for: {remaining} seconds")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
