"""
Test script for ShiftDateReasoner with actual user transcript.
"""
import sys
sys.path.insert(0, '/Users/Yonsuncrat/Videos/Algorithms and Data Structures/thoth/backend/core/call_assistant')

from shift_date_reasoner import ShiftDateReasoner

def test_date_reasoning():
    """Test the date reasoner with sample user input."""
    
    # Initialize the reasoner
    reasoner = ShiftDateReasoner(model="gemma3:1b")
    
    # User transcript
    user_transcript = "Hi I would like to cancel my shift next Friday and check if I have any shifts this weekend."
    
    print("=" * 60)
    print("DATE REASONING TEST")
    print("=" * 60)
    print(f"User Transcript: {user_transcript}")
    print("-" * 60)
    
    # Get LLM to reason about dates
    result = reasoner.reason_dates(user_transcript)
    
    print(f"Is Shift Query: {result.get('is_shift_query')}")
    print(f"Date Range Type: {result.get('date_range_type')}")
    print(f"Start Date: {result.get('start_date')}")
    print(f"End Date: {result.get('end_date')}")
    print(f"Reasoning: {result.get('reasoning')}")
    print("-" * 60)
    
    # Format for search
    search_query = reasoner.format_search_query(result)
    print(f"Search Query Format: {search_query}")
    print("=" * 60)

if __name__ == "__main__":
    test_date_reasoning()
