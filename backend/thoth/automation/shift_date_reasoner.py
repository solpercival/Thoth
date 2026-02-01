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
            "start_date": "17-12-2025",
            "end_date": "17-12-2025",
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
import os
from datetime import datetime, timedelta
from ollama_client.llm_client import OllamaClient

logger = logging.getLogger(__name__)

#<CNCL>
#<SHOW>

# Test mode configuration - matches pattern in call_assistant files
TEST_MODE = False
TEST_DATE = "2026-01-29"  # YYYY-MM-DD format, only used if TEST_MODE=True


class ShiftDateReasoner:
    """
    Uses LLM to determine relevant dates for shift queries.
    """
    
    SYSTEM_PROMPT_TEMPLATE = """You are a shift scheduling assistant. Your job is to interpret shift queries and determine what dates the user is interested in.

TASK: Given a user's query about their shifts, output ONLY a JSON object (no other text) with these fields:
{{
    "is_shift_query": true/false,
    "date_range_type": "today" | "tomorrow" | "week" | "month" | "specific",
    "start_date": "DD-MM-YYYY",
    "end_date": "DD-MM-YYYY",
    "reasoning": "<CNCL>" if cancellation, "<SHOW>" if viewing shifts, followed by brief explanation
}}

DATE INTERPRETATION RULES:
- "When is my shift?" or "What shifts do I have?" → today + next 7 days
- "Tomorrow" → get the date today and add one day
- "Next week" → 7 days from today
- "This week" → from TODAY until {this_sunday}
- "Next month" → entire next calendar month
- Specific date mentioned → that date only
- Default (no date mentioned) → today + next 7 days

IMPORTANT: Always use today's date as reference. Output ONLY the JSON object, no explanation. 
This Sunday is: {this_sunday}

Today's date: {today} ({day_of_week})
"""

    def __init__(self, model: str = "llama2:latest"):
        """
        Initialize the LLM client for date reasoning.

        Args:
            model: LLM model to use (default: llama2:latest)

        Note:
            If TEST_MODE is True (set at module level), uses TEST_DATE as "today".
            Otherwise uses the actual current date from datetime.now().
        """
        # Use TEST_DATE if TEST_MODE is enabled, otherwise use actual current date
        if TEST_MODE:
            try:
                self.today = datetime.strptime(TEST_DATE, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
                logger.info(f"[TEST MODE] Using test date: {self.today.strftime('%Y-%m-%d')}")
            except ValueError:
                logger.warning(f"Invalid TEST_DATE format: {TEST_DATE}. Expected YYYY-MM-DD. Falling back to actual date.")
                self.today = datetime.now()
        else:
            self.today = datetime.now()
        
        today_str = self.today.strftime("%Y-%m-%d")
        day_of_week = self.today.strftime("%A")  # e.g., "Tuesday"
        
        logger.info(f"ShiftDateReasoner initialized - Today: {today_str} ({day_of_week})")
        
        # Calculate this Sunday (end of current week)
        # Monday=0, Sunday=6 in weekday()
        days_until_sunday = (6 - self.today.weekday()) % 7
        if days_until_sunday == 0 and self.today.weekday() == 6:
            # Today is Sunday
            sunday_date = self.today
        else:
            # Calculate next Sunday
            sunday_date = self.today + timedelta(days=days_until_sunday if days_until_sunday != 0 else 7)
        
        self.this_sunday = sunday_date
        sunday_str = sunday_date.strftime("%Y-%m-%d")
        sunday_dd_mm_yyyy = sunday_date.strftime("%d-%m-%Y")
        
        logger.debug(f"This Sunday: {sunday_dd_mm_yyyy}")
        
        system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(
            today=today_str, 
            day_of_week=day_of_week,
            this_sunday=sunday_dd_mm_yyyy
        )
        self.llm_client = OllamaClient(model=model, system_prompt=system_prompt)
        self.model = model
    
    def _calculate_simple_dates(self, user_query: str):
        """
        Fast path: Calculate dates for simple keywords without using LLM.
        Returns None if query is too complex and needs LLM.
        """
        query_lower = user_query.lower().strip()

        # Check for simple date keywords
        if query_lower in ['tomorrow', 'tmr', 'tmrw']:
            tomorrow = self.today + timedelta(days=1)
            return {
                "is_shift_query": True,
                "date_range_type": "tomorrow",
                "start_date": tomorrow.strftime("%d-%m-%Y"),
                "end_date": tomorrow.strftime("%d-%m-%Y"),
                "reasoning": "<SHOW> Query about tomorrow's shift (calculated in Python)"
            }

        if query_lower in ['today', 'tonight']:
            return {
                "is_shift_query": True,
                "date_range_type": "today",
                "start_date": self.today.strftime("%d-%m-%Y"),
                "end_date": self.today.strftime("%d-%m-%Y"),
                "reasoning": "<SHOW> Query about today's shift (calculated in Python)"
            }

        if query_lower in ['yesterday']:
            yesterday = self.today - timedelta(days=1)
            return {
                "is_shift_query": True,
                "date_range_type": "yesterday",
                "start_date": yesterday.strftime("%d-%m-%Y"),
                "end_date": yesterday.strftime("%d-%m-%Y"),
                "reasoning": "<SHOW> Query about yesterday's shift (calculated in Python)"
            }

        # Check for day of week (e.g., "monday", "tuesday")
        weekdays = {
            'monday': 0, 'mon': 0,
            'tuesday': 1, 'tue': 1, 'tues': 1,
            'wednesday': 2, 'wed': 2,
            'thursday': 3, 'thu': 3, 'thur': 3, 'thurs': 3,
            'friday': 4, 'fri': 4,
            'saturday': 5, 'sat': 5,
            'sunday': 6, 'sun': 6
        }

        for day_name, target_weekday in weekdays.items():
            if query_lower == day_name or query_lower == f"next {day_name}":
                current_weekday = self.today.weekday()
                days_ahead = target_weekday - current_weekday
                if days_ahead <= 0:  # Target day already happened this week
                    days_ahead += 7
                target_date = self.today + timedelta(days=days_ahead)

                return {
                    "is_shift_query": True,
                    "date_range_type": "specific",
                    "start_date": target_date.strftime("%d-%m-%Y"),
                    "end_date": target_date.strftime("%d-%m-%Y"),
                    "reasoning": f"<SHOW> Query about {day_name.capitalize()} shift (calculated in Python)"
                }

        # Check for "next week"
        if 'next week' in query_lower:
            # Next week Monday
            days_until_next_monday = (7 - self.today.weekday()) % 7 + 7
            if days_until_next_monday == 7:
                days_until_next_monday = 14
            next_monday = self.today + timedelta(days=days_until_next_monday)
            next_sunday = next_monday + timedelta(days=6)

            return {
                "is_shift_query": True,
                "date_range_type": "week",
                "start_date": next_monday.strftime("%d-%m-%Y"),
                "end_date": next_sunday.strftime("%d-%m-%Y"),
                "reasoning": "<SHOW> Query about next week's shifts (calculated in Python)"
            }

        # Check for "this week"
        if 'this week' in query_lower or query_lower == 'week':
            return {
                "is_shift_query": True,
                "date_range_type": "week",
                "start_date": self.today.strftime("%d-%m-%Y"),
                "end_date": self.this_sunday.strftime("%d-%m-%Y"),
                "reasoning": "<SHOW> Query about this week's shifts (calculated in Python)"
            }

        # No simple match - need LLM
        return None

    def reason_dates(self, user_query: str, retry_on_defaults: bool = True) -> dict:
        """
        Determine relevant dates for a shift query.

        Uses fast Python calculation for simple keywords (tomorrow, monday, etc.).
        Falls back to LLM for complex queries.

        Args:
            user_query: User's question about shifts
                Example: "When is my shift tomorrow?"
                Example: "What shifts do I have next week?"
            retry_on_defaults: If True, retry the query if defaults are returned (for intermittent LLM issues)

        Returns:
            Dict with:
            {
                "is_shift_query": bool,
                "date_range_type": str,
                "start_date": "DD-MM-YYYY",
                "end_date": "DD-MM-YYYY",
                "reasoning": str
            }
        """
        # Try fast path first - calculate simple dates without LLM
        simple_result = self._calculate_simple_dates(user_query)
        if simple_result:
            logger.info(f"Date calculated directly (Python): {simple_result['start_date']} to {simple_result['end_date']}")
            return simple_result

        # Complex query - use LLM
        logger.info(f"Complex query detected, using LLM for date reasoning...")
        max_retries = 2 if retry_on_defaults else 1
        attempt = 0

        while attempt < max_retries:
            attempt += 1
            try:
                logger.info(f"Reasoning dates for query: {user_query} (attempt {attempt}/{max_retries})")
                logger.debug(f"LLM context - Today: {self.today.strftime('%Y-%m-%d')}, This Sunday: {self.this_sunday.strftime('%Y-%m-%d')}")
                
                # Verify system prompt is in the conversation
                history = self.llm_client.get_history()
                if not history or history[0].get('role') != 'system':
                    logger.warning("System prompt missing from LLM history! Re-initializing...")
                    # Reinitialize to restore system prompt
                    system_prompt = self.SYSTEM_PROMPT_TEMPLATE.format(
                        today=self.today.strftime("%Y-%m-%d"),
                        day_of_week=self.today.strftime("%A"),
                        this_sunday=self.this_sunday.strftime("%d-%m-%Y")
                    )
                    self.llm_client.set_system_prompt(system_prompt)
                
                response = self.llm_client.ask_llm(user_query)
                logger.debug(f"LLM response (attempt {attempt}): {response[:500]}...")
            
                # Try to extract JSON from response (in case there's extra text)
                start_idx = response.find('{')
                end_idx = response.rfind('}') + 1
                
                if start_idx == -1 or end_idx == 0:
                    logger.error(f"No JSON found in LLM response (attempt {attempt}). Response was: {response}")
                    if attempt < max_retries:
                        logger.warning(f"Retrying... (attempt {attempt + 1})")
                        self.llm_client.clear_history(keep_system_prompt=True)
                        continue
                    logger.warning("Falling back to default dates (next 7 days)")
                    return self._default_dates()
                
                json_str = response[start_idx:end_idx]
                try:
                    date_info = json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from LLM (attempt {attempt}): {json_str[:200]}")
                    logger.error(f"JSON error: {e}")
                    if attempt < max_retries:
                        logger.warning(f"Retrying... (attempt {attempt + 1})")
                        self.llm_client.clear_history(keep_system_prompt=True)
                        continue
                    logger.warning("Falling back to default dates (next 7 days)")
                    return self._default_dates()
                
                # Validate response has required fields
                required_fields = ["is_shift_query", "date_range_type", "start_date", "end_date"]
                if not all(field in date_info for field in required_fields):
                    missing = [f for f in required_fields if f not in date_info]
                    logger.warning(f"Missing required fields in response (attempt {attempt}): {missing}. Got: {date_info}")
                    if attempt < max_retries:
                        logger.warning(f"Retrying... (attempt {attempt + 1})")
                        self.llm_client.clear_history(keep_system_prompt=True)
                        continue
                    logger.warning("Falling back to default dates (next 7 days)")
                    return self._default_dates()
                
                # Normalize dates to DD-MM-YYYY format regardless of LLM output format
                start_date = date_info.get('start_date', '')
                end_date = date_info.get('end_date', '')
                
                # If LLM returned YYYY-MM-DD, convert to DD-MM-YYYY
                if start_date and '-' in start_date:
                    parts = start_date.split('-')
                    if len(parts) == 3 and len(parts[0]) == 4:  # YYYY-MM-DD format
                        date_info['start_date'] = f"{parts[2]}-{parts[1]}-{parts[0]}"
                
                if end_date and '-' in end_date:
                    parts = end_date.split('-')
                    if len(parts) == 3 and len(parts[0]) == 4:  # YYYY-MM-DD format
                        date_info['end_date'] = f"{parts[2]}-{parts[1]}-{parts[0]}"
                
                # Fix "this week" end date if LLM returned wrong date
                if date_info.get('date_range_type') == 'this week' or date_info.get('date_range_type') == 'week':
                    # If LLM returned a date that doesn't match Sunday, correct it
                    sunday_str = self.this_sunday.strftime("%d-%m-%Y")
                    if date_info['end_date'] != sunday_str:
                        logger.info(f"Correcting 'this week' end date from {date_info['end_date']} to {sunday_str}")
                        date_info['end_date'] = sunday_str
                
                logger.info(f"Determined dates (attempt {attempt}): {date_info['start_date']} to {date_info['end_date']}")
                
                # Clear conversation history for next reasoning to avoid contamination
                self.llm_client.clear_history(keep_system_prompt=True)
                
                return date_info
            
            except Exception as e:
                logger.error(f"Error reasoning dates (attempt {attempt}): {e}")
                logger.exception("Full traceback:")
                if attempt < max_retries:
                    logger.warning(f"Retrying... (attempt {attempt + 1})")
                    self.llm_client.clear_history(keep_system_prompt=True)
                    continue
                logger.warning("Falling back to default dates (next 7 days)")
                return self._default_dates()
    
    def _default_dates(self) -> dict:
        """Return default date range (today + 7 days)."""
        today = datetime.now()
        end = today + timedelta(days=7)
        
        return {
            "is_shift_query": True,
            "date_range_type": "week",
            "start_date": today.strftime("%d-%m-%Y"),
            "end_date": end.strftime("%d-%m-%Y"),
            "reasoning": "Default: next 7 days"
        }
    
    def clear_history(self) -> None:
        """Clear the LLM conversation history while keeping the system prompt."""
        self.llm_client.clear_history(keep_system_prompt=True)
        logger.info("Cleared LLM conversation history")
    
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


def create_date_reasoner(model: str = "qwen3:8b") -> ShiftDateReasoner:
    """Factory function to create a ShiftDateReasoner instance."""
    return ShiftDateReasoner(model=model)
