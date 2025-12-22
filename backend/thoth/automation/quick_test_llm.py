#!/usr/bin/env python3
"""
QUICK TEST HELPER - Verify LLM date reasoning works correctly

This script lets you quickly test if date reasoning is working on another machine
while controlling the system date via environment variable.

Usage:
    python quick_test_llm.py "Cancel my shift tomorrow"
    python quick_test_llm.py --override "2025-12-16" "Cancel my shift tomorrow"
    python quick_test_llm.py --override "2025-12-16" --model "llama2" "What shifts do I have this week?"
"""
import sys
import os
import argparse
from datetime import datetime
from pathlib import Path

# Add parent directories to path
backend_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_root))

try:
    from thoth.core.call_assistant.shift_date_reasoner import ShiftDateReasoner
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core', 'call_assistant'))
    from shift_date_reasoner import ShiftDateReasoner


def format_result(result):
    """Pretty print the result."""
    print("\n" + "="*80)
    print("LLM DATE REASONING RESULT")
    print("="*80)
    
    for key, value in result.items():
        if key == 'reasoning' and len(value) > 100:
            print(f"{key:20}: {value[:100]}...")
        else:
            print(f"{key:20}: {value}")
    
    print("="*80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Quick test LLM date reasoning on another machine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python quick_test_llm.py "Cancel my shift tomorrow"
    python quick_test_llm.py --override "2025-12-16" "Cancel my shift tomorrow"
    python quick_test_llm.py --override "2025-12-16" "What shifts do I have this week?"
    python quick_test_llm.py --model "gemma3:1b" "Show me all my shifts"
        """
    )
    
    parser.add_argument(
        "query",
        nargs="?",
        default="Cancel my shift tomorrow",
        help="User query to test (default: 'Cancel my shift tomorrow')"
    )
    
    parser.add_argument(
        "--override",
        type=str,
        help="Override system date (format: YYYY-MM-DD, e.g., 2025-12-16)"
    )
    
    parser.add_argument(
        "--model",
        type=str,
        default="llama2",
        help="LLM model to use (default: llama2)"
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*80)
    print("QUICK LLM TEST")
    print("="*80)
    
    # Show current date
    if args.override:
        print(f"System date:  {datetime.now().strftime('%Y-%m-%d')}")
        print(f"Override:     {args.override}")
    else:
        print(f"System date:  {datetime.now().strftime('%Y-%m-%d')}")
    
    print(f"Model:        {args.model}")
    print(f"Query:        '{args.query}'")
    print("="*80 + "\n")
    
    try:
        # Create reasoner with override if provided
        print("Initializing ShiftDateReasoner...")
        reasoner = ShiftDateReasoner(
            model=args.model,
            override_today=args.override
        )
        print("[OK] Initialized successfully\n")
        
        # Reason the dates
        print(f"Sending query to LLM...\n")
        result = reasoner.reason_dates(args.query)
        
        # Format and print result
        format_result(result)
        
        # Check if result is reasonable
        print("VALIDATION:")
        if result.get('start_date') and result.get('end_date'):
            # Parse dates
            try:
                parts_start = result['start_date'].split('-')
                parts_end = result['end_date'].split('-')
                
                if len(parts_start) == 3 and len(parts_end) == 3:
                    if len(parts_start[0]) == 2:  # DD-MM-YYYY
                        print(f"[OK] Date format is correct (DD-MM-YYYY)")
                    else:
                        print(f"[WARN] Unexpected date format: {result['start_date']}")
                
                if result['start_date'] == result['end_date']:
                    print(f"[OK] Single day query")
                else:
                    print(f"[OK] Date range query ({result['start_date']} -> {result['end_date']})")
                    
            except Exception as e:
                print(f"[WARN] Could not validate dates: {e}")
        
        if result.get('is_shift_query'):
            print(f"[OK] Recognized as shift query")
        else:
            print(f"[WARN] Not recognized as shift query")
        
        if '<CNCL>' in result.get('reasoning', ''):
            print(f"[OK] Detected cancellation intent")
        elif '<SHOW>' in result.get('reasoning', ''):
            print(f"[OK] Detected show shifts intent")
        
        # Check if defaults were used
        if result.get('date_range_type') == 'week' and 'Default' in result.get('reasoning', ''):
            print(f"[WARN] WARNING: Using DEFAULT dates (7 days)")
            print(f"       This usually means the LLM had an issue")
            print(f"       Check Ollama server and system prompt context")
        
    except Exception as e:
        print(f"[FAIL] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
