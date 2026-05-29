# Architecture Design Scratchpad

## Session
- Started: 2026-05-29
- Stage: ALL DECISIONS CAPTURED — generating ADD now

## All Architecture Decisions

### Auth: Snowflake key-pair (RSA)
- No username/password — private/public key authentication
- Private key stored as env var (base64-encoded PEM) or file path
- Public key registered on Snowflake user account
- snowflake-connector-python uses cryptography lib to load key

### Persistence: Fire-and-forget
- No DB writes for scheduled reports
- Celery task calls workflow.run() directly
- No events table involvement

### Teams failure: Retry once after 30s, then log + continue
- httpx POST → non-200 or exception → asyncio.sleep(30) → retry → log if still fails
- Task marked success regardless (delivery is best-effort)

### Trigger: Celery beat
- beat_schedule in worker/config.py
- crontab(hour=7, minute=30, day_of_week='1-5')
- New Celery task: process_google_ads_report

### Snowflake env vars
SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PRIVATE_KEY_B64,
SNOWFLAKE_PRIVATE_KEY_PASSPHRASE (optional), SNOWFLAKE_WAREHOUSE,
SNOWFLAKE_DATABASE, SNOWFLAKE_SCHEMA, SNOWFLAKE_ROLE (optional)
TEAMS_SOP_WEBHOOK_URL

### New dependencies
- snowflake-connector-python
- cryptography (for key loading — likely already present via other deps)
