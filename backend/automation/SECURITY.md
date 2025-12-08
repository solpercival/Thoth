# Security Configuration

## Secret Management

### ✅ Protected Files
- `.env` - **GITIGNORED**, contains all secrets (TOTP, credentials, SMTP)
- `.sessions/` - **GITIGNORED**, contains saved browser session cookies
- `.venv/` - **GITIGNORED**, Python virtual environment

### ⚠️ What NOT to commit
- `.env` - Your actual secrets
- `.sessions/*.json` - Session cookies with auth tokens
- Private credentials or API keys

### Setup Instructions

1. **Copy the template**:
   ```bash
   cp .env.example .env
   ```

2. **Fill in your actual secrets** in `.env`:
   ```
   ADMIN_USERNAME_HAHS_VIC3495=your_actual_username
   ADMIN_PASSWORD_HAHS_VIC3495=your_actual_password
   TOTP_SECRET_HAHS_VIC3495=your_totp_secret_from_authenticator
   ```

3. **Never commit `.env`** - it's in `.gitignore`

### Secret Access Pattern

All secrets are read from `.env` via the `secrets.py` module:

```python
from secrets import get_admin_credentials, get_admin_totp_code

# Get credentials
creds = get_admin_credentials("hahs_vic3495")
# Returns: {"username": "...", "password": "..."}

# Get TOTP code (auto-generated from secret)
code = get_admin_totp_code("hahs_vic3495")
# Returns: "927693"
```

### Environment Variables (Alternative)

You can also set secrets as environment variables instead of `.env`:

```bash
export ADMIN_USERNAME_HAHS_VIC3495="your_username"
export ADMIN_PASSWORD_HAHS_VIC3495="your_password"
export TOTP_SECRET_HAHS_VIC3495="your_secret"
```

Environment variables take priority over `.env` file.

### Deployment

For production/Docker:
- Set secrets as environment variables (most secure)
- Use `docker run -e ADMIN_USERNAME_HAHS_VIC3495=...`
- Or use Docker secrets/Kubernetes secrets
- Never put `.env` in Docker image

### TOTP Secret Safety

- The TOTP secret is **ONLY** used to generate codes locally
- It's never sent anywhere
- Anyone with the secret can generate valid 2FA codes
- Treat it like a password

---

## Verification Checklist

- [x] `.env` is in `.gitignore`
- [x] `.sessions/` is in `.gitignore`
- [x] No hardcoded secrets in source code
- [x] `.env.example` provided as template
- [x] `secrets.py` reads from `.env` only
- [x] No secret examples in docstrings

**Safe to push to GitHub** ✅
