#!/usr/bin/env python3
"""
Continuous TOTP Code Generator

Generates TOTP codes every second so you can observe them during browser automation.
This helps verify if the TOTP generation is working correctly.

Usage:
    python test_totp_generator.py
"""
import time
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from secrets import get_admin_totp_code


def main():
    """Continuously generate and display TOTP codes"""
    print("\n" + "="*60)
    print("CONTINUOUS TOTP CODE GENERATOR")
    print("="*60)
    print("Generating TOTP codes every second...")
    print("Watch these codes while the browser is doing 2FA login")
    print("Press Ctrl+C to stop\n")
    
    try:
        counter = 0
        while True:
            code = get_admin_totp_code("hahs_vic3495")
            timestamp = time.strftime("%H:%M:%S")
            counter += 1
            
            # Display with timestamp and counter
            print(f"[{timestamp}] #{counter:3d} TOTP Code: {code}")
            
            # Pause 1 second before next code
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n[*] Stopped by user")
        print("="*60 + "\n")


if __name__ == "__main__":
    main()
