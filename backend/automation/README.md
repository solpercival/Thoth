# Automated Website Login System - LLM Core Integration

This module provides automated website login functionality as part of the Thoth LLM core pipeline. It receives credentials reasoned out by the LLM from transcribed calls, performs the login, and returns scraped content for further LLM processing.

## Architecture

```
┌─────────────────────────────────┐
│ Voice Call Transcription        │
│ (Audio → Text)                  │
└────────────────┬────────────────┘
                 │
┌────────────────▼────────────────┐
│ LLM Core Reasoning              │
│ (Choose appropriate actions)    │
└────────────────┬────────────────┘
                 │ llm_reasoning_output
                 │ {
                 │   "service_name": "...",
                 │   "credentials": {...},
                 │   "action": "login_and_scrape"
                 │ }
                 │
┌────────────────▼────────────────┐
│ Login Automation (This Module)  │
│ Playwright-based login          │
| Playwright saves cookies and    |
| the signed in state so that 2FA |
| is not needed                   |
└────────────────┬────────────────┘
                 │ scraped_content
                 │
┌────────────────▼────────────────┐
│ Web Scraper                     │
│ (Extract relevant data)         │
└────────────────┬────────────────┘
                 │
┌────────────────▼────────────────┐
│ LLM Phrase Processing           │
│ (Format for TTS)                │
└────────────────┬────────────────┘
                 │
┌────────────────▼────────────────┐
│ Text-to-Speech                  │
│ (Return audio to call)          │
└─────────────────────────────────┘
```

## Features

✅ **LLM Integration** - Receives LLM-reasoned credentials directly
✅ **Automated Website Login** - Selenium-based form filling and submission
✅ **Content Scraping** - Extracts page content after login for LLM processing
✅ **Retry Logic** - Automatic retry on failure with configurable attempts
✅ **Website Configuration** - Easy configuration for different websites
✅ **Logging & Debugging** - Comprehensive logging and screenshot capture
✅ **Docker Support** - Easy deployment with Docker Compose
✅ **Error Handling** - Graceful error handling with detailed error messages

## Components

### 1. Login Automation (`automation/login.py`)
Core automation library with:
- **LoginAutomation**: Main orchestrator receiving LLM credentials
- **WebsiteAutoLogin**: Selenium WebDriver wrapper
- **Credentials**: Dataclass with `from_llm_output()` method for LLM integration

### 2. Website Configurations (`automation/website_configs.py`)
Pre-configured for custom sites.

### 3. Integration Example (`automation/example_usage.py`)
- `login_from_llm_reasoning()`: Direct LLM credential integration
- `llm_integration_pipeline()`: Full pipeline entry point
- Shows how LLM reasoning output flows through the system

### 4. Updated Dockerfiles
- `Dockerfile.automation`: Standalone automation container
- Integrated with LLM core pipeline

## Installation

### Prerequisites
- Python 3.8+
- Docker & Docker Compose (for containerized setup)
- Chrome/Chromium browser (for local testing)
- ChromeDriver (for local testing)

### Local Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install selenium
```

### Docker Setup

```bash
# Build and run with Docker Compose
docker-compose -f docker-compose.automation.yml up --build
```

## Configuration

### Environment Variables

```bash
# Login Automation
HEADLESS=true          # Run browser headless (true/false)
PYTHONUNBUFFERED=1     # Real-time logging
```

### Website Configuration Example

```python
from automation.login import WebsiteConfig, LoginStrategy

config = WebsiteConfig(
    url="https://example.com/login",
    strategy=LoginStrategy.STANDARD,
    username_selector="input[name='username']",
    password_selector="input[name='password']",
    submit_selector="button[type='submit']",
    expected_url_after_login="https://example.com/dashboard",
    wait_timeout=10,
)
```

To find correct CSS selectors:
1. Open website in browser
2. Right-click on login form elements
3. Select "Inspect" to view HTML
4. Copy the CSS selector or use `name`, `id`, or `class` attributes

## Usage Examples

### Example 1: LLM Core Integration

```python
from automation.example_usage import llm_integration_pipeline

# LLM reasoning output (from core LLM processing)
llm_reasoning = {
    "service_name": "github",
    "credentials": {
        "username": "my_username",
        "password": "my_token",
        "email": "user@example.com",
        "extra_fields": {}
    },
    "action": "login_and_scrape"
}

# Execute login and scraping
result = llm_integration_pipeline(
    transcribed_call="Login to github and check my repositories",
    llm_reasoning_output=llm_reasoning
)

if result['success']:
    # Pass scraped content to web scraper component
    page_content = result['scraped_content']
    # ... further processing by web scraper
```

### Example 2: Direct LLM Credentials Usage

```python
from automation.login import LoginAutomation, Credentials
from automation.website_configs import get_config

# LLM-reasoned credentials
llm_creds = {
    "username": "user",
    "password": "pass",
    "email": "user@example.com",
    "extra_fields": {}
}

config = get_config("github")

with LoginAutomation(headless=True) as automation:
    success = automation.login_with_retry(
        config=config,
        llm_credentials=llm_creds,
    )
    
    if success:
        content = automation.scrape_page_content()
        print(f"Scraped {len(content)} characters")
```

### Example 3: With Extra Fields (2FA, Security Questions)

```python
llm_reasoning = {
    "service_name": "secure_service",
    "credentials": {
        "username": "user",
        "password": "pass",
        "extra_fields": {
            "security_answer": "my_security_answer",
            "2fa_code": "123456"
        }
    }
}

# The LLM should extract these extra fields from the transcribed call
result = llm_integration_pipeline(
    transcribed_call="Login and answer the security question about my pet",
    llm_reasoning_output=llm_reasoning
)
```

## Docker Compose Usage

### Start Services

```bash
# Build and start containers
docker-compose -f docker-compose.automation.yml up --build

# Run in background
docker-compose -f docker-compose.automation.yml up -d
```

### Stop Services

```bash
docker-compose -f docker-compose.automation.yml down
```

### View Logs

```bash
# All services
docker-compose -f docker-compose.automation.yml logs -f

# Specific service
docker-compose -f docker-compose.automation.yml logs -f login-automation
```

## Debugging

### Take Screenshots

```python
automation.take_screenshot("debug.png")
```

### View Page Source

```python
source = automation.auto_login.get_page_source()
print(source)
```

### Enable Debug Logging

```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

### Common Issues

| Issue | Solution |
|-------|----------|
| "Element not found" | Check CSS selectors match website HTML structure |
| Login fails | Verify LLM extracted correct credentials from transcription |
| Timeout errors | Increase `wait_timeout` in WebsiteConfig |
| "Chrome not found" | Install Chrome/Chromium or use headless=False for system browser |
| 2FA fails | Ensure LLM extracts 2FA code and includes in extra_fields |

## LLM Core Integration Points

### Input to Login Automation

The LLM core passes a dictionary with this structure:

```python
{
    "service_name": str,           # Name of service to login to
    "credentials": {
        "username": str,           # Extracted username
        "password": str,           # Extracted password
        "email": str,              # Optional email
        "extra_fields": {          # Optional 2FA codes, security answers, etc
            "field_name": str
        }
    },
    "action": "login_and_scrape"  # Action type
}
```

### Output from Login Automation

Returns to LLM core:

```python
{
    "success": bool,                    # Login successful?
    "scraped_content": str,             # Page HTML/content
    "message": str,                     # Success message
    "error": str                        # Error message if failed
}
```

## Integration with Other Components

### Connection with Web Scraper
After successful login, `scraped_content` is passed to the web scraper component for data extraction.

### Connection with LLM Phrase Processing
Web scraper output is passed to LLM for formatting as natural language for TTS.

### Connection with Text-to-Speech
Formatted text is converted to audio and returned to the call.

## Security Considerations

⚠️ **Important Security Notes:**

1. **Never Log Credentials**: System logs credentials only for debugging, use secure logging in production
2. **Secure Credential Handling**: LLM should only pass credentials internally, not via external APIs
3. **HTTPS for External Sites**: Ensure target websites use HTTPS
4. **Browser Isolation**: Use Docker/containers to isolate browser instances
5. **Temporary Data**: Clean up screenshots and temporary files after use

## Performance Tips

- Use headless mode for faster execution
- Adjust `wait_timeout` based on network speed
- Cache website configurations for frequently accessed sites
- Parallelize multiple logins if needed (separate containers)

## Troubleshooting

### Logs Location
- Local: Check console output
- Docker: `docker-compose logs -f login-automation`

### Common Selectors
```python
# By CSS class
"input.username"

# By ID
"input#password"

# By attribute
"input[data-testid='login-username']"

# XPath
"//input[@name='username']"
```

## Contributing

To add support for a new website:

1. Add configuration to `website_configs.py`
2. Update `WEBSITE_CONFIGS` dictionary
3. Test with example LLM reasoning output
4. Document custom selectors

## License

[Add your license here]

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review logs for error messages
3. Test selectors manually in browser DevTools
4. Verify LLM is extracting credentials correctly
