#!/usr/bin/env python3
"""
DIAGNOSTIC TOOL - Debug LLM date reasoning issues

This script helps identify why the LLM is returning default dates on another machine.

Run this on the machine where date reasoning is failing to get detailed diagnostics:
    python diagnose_llm_dates.py

It will check:
    1. System date and time
    2. Ollama server connectivity
    3. LLM model availability
    4. System prompt generation
    5. LLM response format
    6. Date parsing accuracy
"""
import sys
import os
from datetime import datetime, timedelta
import json

# Add parent directories to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from backend.core.call_assistant.llm_client import OllamaClient
    from backend.core.call_assistant.shift_date_reasoner import ShiftDateReasoner
except ImportError:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core', 'call_assistant'))
    from llm_client import OllamaClient
    from shift_date_reasoner import ShiftDateReasoner


def diagnose():
    print("=" * 80)
    print("LLM DATE REASONING DIAGNOSTIC TOOL")
    print("=" * 80)
    
    # 1. Check system date/time
    print("\n[1] SYSTEM DATE & TIME CHECK")
    print("-" * 80)
    now = datetime.now()
    print(f"Current date: {now.strftime('%Y-%m-%d')}")
    print(f"Current time: {now.strftime('%H:%M:%S')}")
    print(f"Day of week: {now.strftime('%A')}")
    print(f"Timezone: {now.astimezone().tzname()}")
    
    # 2. Check Ollama connectivity
    print("\n[2] OLLAMA SERVER CONNECTIVITY")
    print("-" * 80)
    try:
        import ollama
        client = ollama.Client(host="http://localhost:11434")
        models = client.list()
        print("[OK] Ollama server is reachable at http://localhost:11434")
        print(f"[OK] Available models: {len(models.get('models', []))} found")
        
        model_names = [m.get('name', 'unknown') for m in models.get('models', [])]
        print(f"     Models: {', '.join(model_names[:5])}")
        
        if not any('llama2:latest' in m for m in model_names):
            print("     [WARN] llama2:latest model not found!")
        else:
            print("     [OK] llama2:latest model found")
            
    except Exception as e:
        print(f"[FAIL] Could not reach Ollama: {e}")
        print("       Make sure Ollama is running: ollama serve")
        return
    
    # 3. Test basic LLM response
    print("\n[3] BASIC LLM RESPONSE TEST")
    print("-" * 80)
    try:
        basic_client = OllamaClient(model="llama2:latest", system_prompt="You are a helpful assistant.")
        response = basic_client.ask_llm("What is 2+2?")
        print(f"[OK] LLM responded successfully")
        print(f"     Response: {response[:100]}...")
    except Exception as e:
        print(f"[FAIL] Could not get LLM response: {e}")
        return
    
    # 4. Test system prompt generation
    print("\n[4] SYSTEM PROMPT GENERATION")
    print("-" * 80)
    try:
        reasoner = ShiftDateReasoner(model="qwen2.5:7b")
        print(f"[OK] ShiftDateReasoner initialized with llama2:latest")
        print(f"     Today: {reasoner.today.strftime('%Y-%m-%d')}")
        print(f"     Day of week: {reasoner.today.strftime('%A')}")
        print(f"     This Sunday: {reasoner.this_sunday.strftime('%Y-%m-%d')}")
        
        # Get the system prompt
        history = reasoner.llm_client.get_history()
        if history and history[0]['role'] == 'system':
            system_prompt = history[0]['content']
            print(f"\n[OK] System prompt (first 200 chars):")
            print(f"     {system_prompt[:200]}...")
            
            # Check if date context is in prompt
            if reasoner.today.strftime('%Y-%m-%d') in system_prompt:
                print(f"     [OK] Contains today's date: {reasoner.today.strftime('%Y-%m-%d')}")
            else:
                print(f"     [FAIL] MISSING today's date in prompt!")
                
            if reasoner.today.strftime('%A') in system_prompt:
                print(f"     [OK] Contains day of week: {reasoner.today.strftime('%A')}")
            else:
                print(f"     [FAIL] MISSING day of week in prompt!")
    except Exception as e:
        print(f"[FAIL] Could not initialize reasoner: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 5. Test date reasoning with various inputs
    print("\n[5] DATE REASONING TEST")
    print("-" * 80)
    
    test_queries = [
        "Cancel my shift tomorrow",
        "I want to cancel my shift this week",
        "Show me shifts for next week",
        "When is my shift?",
    ]
    
    for query in test_queries:
        print(f"\nQuery: '{query}'")
        try:
            result = reasoner.reason_dates(query)
            
            is_shift = result.get('is_shift_query')
            date_type = result.get('date_range_type')
            start = result.get('start_date')
            end = result.get('end_date')
            reasoning = result.get('reasoning', '')
            
            print(f"     is_shift_query: {is_shift}")
            print(f"     date_range_type: {date_type}")
            print(f"     dates: {start} → {end}")
            print(f"     reasoning: {reasoning[:80]}...")
            
            # Check if dates are in expected format
            if start and '-' in start:
                parts = start.split('-')
                if len(parts) == 3:
                    if len(parts[0]) == 2:  # DD-MM-YYYY
                        print(f"     [OK] Date format correct: DD-MM-YYYY")
                    elif len(parts[0]) == 4:  # YYYY-MM-DD
                        print(f"     [WARN] Date format is YYYY-MM-DD (should be DD-MM-YYYY)")
                    else:
                        print(f"     [FAIL] Date format unknown")
            
        except Exception as e:
            print(f"     [FAIL] {e}")
            import traceback
            traceback.print_exc()
    
    # 6. Check if defaults are being returned
    print("\n[6] DEFAULT DATES CHECK")
    print("-" * 80)
    default_result = reasoner._default_dates()
    print(f"Default date range:")
    print(f"     Start: {default_result['start_date']}")
    print(f"     End: {default_result['end_date']}")
    print(f"     Type: {default_result['date_range_type']}")
    
    print("\n" + "=" * 80)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 80)
    print("\nNEXT STEPS:")
    print("- If Ollama is not reachable, start it: ollama serve")
    print("- If llama2:latest is not available, pull it: ollama pull llama2:latest")
    print("- If date format is YYYY-MM-DD, the conversion is not working")
    print("- If defaults are being returned, check the LLM response format")
    print("- Share this output when reporting issues on another machine")


if __name__ == "__main__":
    diagnose()
