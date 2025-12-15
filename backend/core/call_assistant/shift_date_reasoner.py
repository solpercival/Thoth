"""
LLM-BASED DATE REASONING MODULE

In the workflow:
    test_integrated_workflow.py (calls test_date_reasoner.py)
        ↓
        login_playwright.py (returns authenticated page)
        ↓
        staff_lookup.py (finds staff by phone)
        ↓
        shift_date_reasoner.py ← YOU ARE HERE
            - Takes user transcript: "Cancel my shift tomorrow"
            - Sends to Ollama (local LLM) with system prompt
            - LLM interprets dates and returns JSON
            - Returns structured date range for filtering
        ↓
        staff_lookup.py (searches for shifts by name)
        ↓
        test_integrated_workflow.py (filters shifts by dates)

Key Class:
    ShiftDateReasoner
        Constructor: __init__(model="gemma3:1b")
        Main method: reason_dates(user_query)
            
Main Function:
    reason_dates(user_query: str)
        Input: "Hi I would like to cancel my shift tomorrow"
        Output: {
            "is_shift_query": True,
            "date_range_type": "tomorrow",
            "start_date": "2025-12-16",
            "end_date": "2025-12-16",
            "reasoning": "Cancellation of shift tomorrow."
        }

How It Works:
    1. Receives user transcript from test_integrated_workflow.py
    2. Builds prompt with:
       - System prompt (instructions for LLM)
       - User query
       - Current date context
    3. Sends to Ollama HTTP endpoint: POST http://127.0.0.1:11434/api/chat
    4. Ollama (gemma3:1b model) responds with JSON
    5. Parses JSON response
    6. Returns structured date range

Dependencies:
    - llm_client.py: OllamaClient (HTTP requests to Ollama)
    - Ollama server: Must be running (ollama serve)
    - gemma3:1b model: Must be pulled (ollama pull gemma3:1b)

Used By:
    - test_integrated_workflow.py: Calls reason_dates() to interpret user transcript
    - Manual testing: test_date_reasoner.py
"""
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional
from backend.core.call_assistant.llm_client import OllamaClient

logger = logging.getLogger(__name__)


class ShiftDateReasoner:
    """
    Uses LLM to determine relevant dates for shift queries.
    """
    
    SYSTEM_PROMPT_TEMPLATE = """You are a shift scheduling assistant. Your job is to interpret shift queries and determine what dates the user is interested in.

TASK: Given a user's query about their shifts, output ONLY a JSON object (no other text) with these fields:
{{
    "is_shift_query": true/false,
    "date_range_type": "today" | "tomorrow" | "week" | "month" | "specific",
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "reasoning": "brief explanation"
}}

DATE INTERPRETATION RULES:
- "When is my shift?" or "What shifts do I have?" → today + next 7 days
- "Tomorrow" → tomorrow only
- "Next week" → 7 days from today
- "This week" → until end of week (Sunday)
- "Next month" → entire next calendar month
- Specific date mentioned → that date only
- Default (no date mentioned) → today + next 7 days

IMPORTANT: Always use today's date as reference. Output ONLY the JSON object, no explanation.

Today's date: {today}
"""

    def __init__(self, model: str = "gemma3:1b"):
        """Initialize the LLM client for date reasoning."""
        today = datetime.now().strftime("%Y-%m-%d")
        system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(today=today)
        self.llm_client = OllamaClient(model=model, system_prompt=system_prompt)
        self.model = model
    
    def reason_dates(self, user_query: str) -> dict:
        """
        Use LLM to determine relevant dates for a shift query.
        
        Args:
            user_query: User's question about shifts
                Example: "When is my shift tomorrow?"
                Example: "What shifts do I have next week?"
        
        Returns:
            Dict with:
            {
                "is_shift_query": bool,
                "date_range_type": str,
                "start_date": "YYYY-MM-DD",
                "end_date": "YYYY-MM-DD",
                "reasoning": str
            }
        """
        try:
            logger.info(f"Reasoning dates for query: {user_query}")
            
            response = self.llm_client.ask_llm(user_query)
            logger.debug(f"LLM response: {response}")
            
            # Try to extract JSON from response (in case there's extra text)
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx == -1 or end_idx == 0:
                logger.error(f"No JSON found in response: {response}")
                return self._default_dates()
            
            json_str = response[start_idx:end_idx]
            date_info = json.loads(json_str)
            
            # Validate response has required fields
            required_fields = ["is_shift_query", "date_range_type", "start_date", "end_date"]
            if not all(field in date_info for field in required_fields):
                logger.warning(f"Missing fields in response: {date_info}")
                return self._default_dates()
            
            logger.info(f"Determined dates: {date_info['start_date']} to {date_info['end_date']}")
            return date_info
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return self._default_dates()
        except Exception as e:
            logger.error(f"Error reasoning dates: {e}")
            return self._default_dates()
    
    def _default_dates(self) -> dict:
        """Return default date range (today + 7 days)."""
        today = datetime.now()
        end = today + timedelta(days=7)
        
        return {
            "is_shift_query": True,
            "date_range_type": "week",
            "start_date": today.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "reasoning": "Default: next 7 days"
        }
    
    def format_search_query(self, date_info: dict) -> str:
        """
        Format date info into a search query for the API.
        
        Args:
            date_info: Output from reason_dates()
        
        Returns:
            Formatted query string for filtering shifts
        """
        start = date_info.get("start_date")
        end = date_info.get("end_date")
        return f"from={start}&to={end}"


def create_date_reasoner(model: str = "gemma3:1b") -> ShiftDateReasoner:
    """Factory function to create a ShiftDateReasoner instance."""
    return ShiftDateReasoner(model=model)
