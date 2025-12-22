"""
Test the email formatter with cancellation reason
"""
try:
    from .email_formatter import format_ezaango_shift_data
except ImportError:
    from email_formatter import format_ezaango_shift_data

# Test data
test_data = {
    "reasoning": "Requested cancellation of shift.",
    "staff": {
        "name": "Adaelia Thomas",
        "id": "1728",
        "email": "adaeliathomas@gmail.com"
    },
    "shifts": [
        {
            "client": "Zak James",
            "time": "02:00 PM",
            "date": "18-12-2025"
        }
    ]
}

# Test without cancellation reason
print("="*70)
print("WITHOUT CANCELLATION REASON:")
print("="*70)
email_without_reason = format_ezaango_shift_data(test_data)
print(email_without_reason)

# Test with cancellation reason
print("\n" + "="*70)
print("WITH CANCELLATION REASON:")
print("="*70)
email_with_reason = format_ezaango_shift_data(
    test_data,
    cancellation_reason="She is sick."
)
print(email_with_reason)
