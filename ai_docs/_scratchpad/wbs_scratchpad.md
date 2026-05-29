# WBS Scratchpad

## Session
- Started: 2026-05-29
- Stage: Generating WBS directly — full context from charter/PRD/ADD
- HACKATHON DEADLINE: 4 PM TODAY

## Demo Target (P0)
- Snowflake query (real data) + AI narrative → console output
- Teams delivery is stretch goal

## Production (P1)
- Celery beat schedule, Teams webhook, docker-compose beat service

## File Structure (from ADD)
- app/schemas/google_ads_schema.py
- app/services/snowflake_client.py
- app/workflows/google_ads_report_workflow.py
- app/workflows/google_ads_report_nodes/{4 nodes}
- app/worker/tasks.py (add task)
- app/worker/config.py (add beat schedule)
- docker/.env (add vars)

## Complexity ratings
Low = <1hr, Medium = 1-2hr, High = 2-4hr
