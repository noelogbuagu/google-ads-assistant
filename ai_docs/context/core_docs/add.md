# Architecture Design Document: Google Ads Intelligence Assistant

**Version:** 1.0  
**Date:** 2026-05-29  
**Status:** Approved for build  
**Brand:** SOP (UK) — v1

---

## 1. System Overview

The Google Ads Intelligence Assistant is a scheduled workflow that runs inside the existing **GenAI Launchpad** infrastructure (FastAPI + Celery + Redis + PostgreSQL). Each weekday at 7:30 AM UTC, a Celery beat task fires a four-node linear workflow that:

1. Queries Snowflake for Google Ads performance data
2. Computes deltas and detects anomalies
3. Generates an AI narrative via Anthropic Claude
4. Delivers the report to a Microsoft Teams channel via webhook

The workflow is **fire-and-forget** — no event is persisted to the application database. The workflow runs entirely within the Celery worker process.

---

## 2. Component Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Compose Stack                  │
│                                                          │
│  ┌─────────────┐    ┌──────────────────────────────┐    │
│  │ Celery Beat │───▶│     Celery Worker            │    │
│  │  (scheduler)│    │  process_google_ads_report() │    │
│  └─────────────┘    │                              │    │
│                     │  GoogleAdsReportWorkflow      │    │
│                     │  ┌────────────────────────┐  │    │
│                     │  │ SnowflakeQueryNode     │  │    │
│                     │  │ ProcessingNode         │  │    │
│                     │  │ NarrativeNode (Claude) │  │    │
│                     │  │ TeamsDeliveryNode      │  │    │
│                     │  └────────────────────────┘  │    │
│                     └──────────────────────────────┘    │
│                              │           │               │
│                     ┌────────┘           └──────────┐   │
│                     ▼                               ▼   │
│             ┌──────────────┐             ┌─────────────┐│
│             │   Snowflake  │             │  Teams      ││
│             │  (external)  │             │  Webhook    ││
│             └──────────────┘             │  (external) ││
│                                          └─────────────┘│
└─────────────────────────────────────────────────────────┘
```

**No FastAPI involvement.** The scheduled task bypasses the HTTP API entirely — it instantiates `GoogleAdsReportWorkflow` directly within the Celery worker.

---

## 3. Workflow Graph

```python
class GoogleAdsReportWorkflow(Workflow):
    workflow_schema = WorkflowSchema(
        description="Daily Google Ads performance report for SOP",
        event_schema=GoogleAdsReportEventSchema,
        start=SnowflakeQueryNode,
        nodes=[
            NodeConfig(node=SnowflakeQueryNode, connections=[ProcessingNode]),
            NodeConfig(node=ProcessingNode,      connections=[NarrativeNode]),
            NodeConfig(node=NarrativeNode,       connections=[TeamsDeliveryNode]),
            NodeConfig(node=TeamsDeliveryNode,   connections=[]),
        ]
    )
```

Linear chain. No router. `TeamsDeliveryNode` is terminal and doubles as the error alert node.

---

## 4. Event Schema

```python
# app/schemas/google_ads_schema.py
from datetime import date
from typing import Optional
from pydantic import BaseModel

class GoogleAdsReportEventSchema(BaseModel):
    brand: str = "sop"
    override_date: Optional[date] = None  # for manual / catch-up runs
```

Passed as the initial event. `override_date` bypasses the D-1/D-2 logic and uses the specified date as the reporting date.

---

## 5. File Structure

```
app/
├── schemas/
│   └── google_ads_schema.py          # Event schema
├── workflows/
│   ├── workflow_registry.py          # Add GOOGLE_ADS_REPORT_WORKFLOW
│   ├── google_ads_report_workflow.py # Workflow class
│   └── google_ads_report_nodes/
│       ├── __init__.py
│       ├── snowflake_query_node.py
│       ├── processing_node.py
│       ├── narrative_node.py
│       └── teams_delivery_node.py
├── services/
│   └── snowflake_client.py           # Snowflake connection factory
└── worker/
    ├── config.py                     # Add beat_schedule
    └── tasks.py                      # Add process_google_ads_report task
```

---

## 6. Node Specifications

### 6.1 SnowflakeQueryNode

**File:** `app/workflows/google_ads_report_nodes/snowflake_query_node.py`  
**Base class:** `Node`  
**Purpose:** Connect to Snowflake, run completeness check, fetch reporting data.

**Inputs (from event):**
- `task_context.event.brand` — brand filter (default: `"sop"`)
- `task_context.event.override_date` — optional manual date override

**Algorithm:**
```
1. Resolve reporting_date:
   - If override_date set → use it, skip completeness check
   - Else → run completeness check query
     - IF COUNT(*) >= 400 for D-1 → reporting_date = D-1
     - ELSE → reporting_date = D-2, set data_lag_flag = True

2. Compute window:
   - trailing_start = reporting_date - 7 days
   - trailing_end = reporting_date - 1 day

3. Execute main query (see Section 9 for SQL)

4. Store results in TaskContext
```

**Outputs (`task_context.update_node("SnowflakeQueryNode", ...)`):**
```python
{
    "reporting_date": date,          # date being reported on
    "data_lag_flag": bool,           # True if D-2 fallback used
    "reporting_day_rows": list[dict],  # rows for reporting_date
    "trailing_rows": list[dict],       # rows for trailing 7-day window
}
```

**Error handling:**
```python
except Exception as e:
    task_context.metadata["error"] = f"Snowflake query failed: {str(e)}"
    task_context.stop_workflow()
    return task_context
```

---

### 6.2 ProcessingNode

**File:** `app/workflows/google_ads_report_nodes/processing_node.py`  
**Base class:** `Node`  
**Purpose:** Aggregate raw rows, compute deltas, flag anomalies, build report data structures.

**Inputs:**
- `task_context.nodes["SnowflakeQueryNode"]`

**Algorithm:**
```
1. Aggregate reporting_day_rows by CAMPAIGN → reporting_day dict
2. Aggregate trailing_rows by CAMPAIGN → trailing_avg dict (mean per metric)
3. Compute account-level rollup (sum across campaigns)
4. For each campaign:
   a. Compute delta_pct per metric
   b. Assign direction indicator (▲ ▼ →) per metric semantics
   c. Evaluate anomaly rules (see PRD FR-2.4)
   d. Compute derived metrics (CPA, ROAS, funnel rates)
5. Filter: only campaigns with trailing 7d COST >= £10
6. Sort: reporting_day COST DESC; zero-spend campaigns at bottom
7. Assemble anomaly list with severity (Critical / Warning)
```

**Metric semantics for direction indicators:**

| Metric | ▲ means | ▼ means |
|---|---|---|
| Spend, Impressions, Clicks, Conversions, Sessions, Revenue | Increased (good) | Decreased (bad) |
| CPA, CPC, CPM | Increased (bad) | Decreased (good) |
| CTR, ROAS, funnel rates | Increased (good) | Decreased (bad) |

**Anomaly thresholds (configurable via env):**

| Metric | Threshold |
|---|---|
| CPA delta | > ±30% vs trailing avg |
| Cost delta | > ±50% vs trailing avg |
| Impressions delta | > ±40% vs trailing avg |
| New Orders delta | > ±40% vs trailing avg |
| Spend > 0 but Orders = 0 | Always flag |
| Zero spend after active trailing window | Always flag |

**Outputs (`task_context.update_node("ProcessingNode", ...)`):**
```python
{
    "reporting_date": date,
    "data_lag_flag": bool,
    "account_snapshot": {
        "spend": float, "spend_avg": float, "spend_delta_pct": float,
        "new_orders": int, "new_orders_avg": float, "new_orders_delta_pct": float,
        "cpa": float, "cpa_avg": float, "cpa_delta_pct": float,
        "roas": float, "roas_avg": float, "roas_delta_pct": float,
        "impressions": int, "impressions_avg": float, "impressions_delta_pct": float,
        "clicks": int, "clicks_avg": float, "clicks_delta_pct": float,
        "ctr": float, "ctr_avg": float,
        "cpc": float, "cpc_avg": float, "cpc_delta_pct": float,
        "gross_revenue": float, "new_gross_revenue": float,
    },
    "campaign_rows": [
        {
            "campaign": str,
            "channel": str,
            "spend": float, "spend_avg": float, "spend_delta_pct": float,
            "spend_indicator": str,  # ▲ ▼ →
            "new_orders": int, "new_orders_avg": float, "new_orders_delta_pct": float,
            "cpa": float | None, "cpa_avg": float | None, "cpa_delta_pct": float | None,
            "roas": float | None, "roas_avg": float | None,
            "impressions": int, "impressions_delta_pct": float,
            "anomaly_severity": str | None,  # "critical" | "warning" | None
            "anomaly_reasons": list[str],
            "has_spend_yesterday": bool,
        },
        ...
    ],
    "anomalies": [
        {
            "campaign": str,
            "severity": str,      # "critical" | "warning"
            "metric": str,
            "value": float,
            "avg": float,
            "delta_pct": float,
            "description": str,   # human-readable e.g. "CPA up 45% vs 7d avg"
        },
        ...
    ],
    "funnel_snapshot": {
        "sessions": int, "started_assessment": int,
        "submitted_assessment": int, "basket_page": int, "purchased": int,
        "session_to_assessment_rate": float,
        "assessment_completion_rate": float,
        "assessment_to_basket_rate": float,
        "basket_to_purchase_rate": float,
    }
}
```

**Error handling:** Same pattern — set `metadata["error"]`, call `stop_workflow()`.

---

### 6.3 NarrativeNode

**File:** `app/workflows/google_ads_report_nodes/narrative_node.py`  
**Base class:** `AgentNode`  
**Purpose:** Generate the AI-authored sections of the report using Anthropic Claude.

**Model:** `claude-sonnet-4-6` (fast, high quality, cost-efficient for this use case)  
**Provider:** `ModelProvider.ANTHROPIC`

**Output type:**
```python
class NarrativeOutput(BaseModel):
    headline: str           # 2-3 sentences, account-level story
    what_stands_out: str    # 3-5 paragraphs, anomaly narrative
    recommendations: str    # 3-5 bullet points, actionable
```

**System prompt (instructions):**
```
You are an expert Google Ads analyst for SOP, a UK healthcare brand offering 
weight loss injections, ED treatment, hair loss, birth control, and online 
pharmacy services.

Your job is to write the analytical sections of a daily performance report 
for the SOP marketing team. You will be given structured campaign data and 
must write:
1. A headline (2-3 sentences): state total spend, CPA direction, and the 
   single most important story in the account today.
2. What Stands Out (3-5 paragraphs): specific anomalies, named campaigns, 
   exact numbers. No generic phrases like "performance was mixed."
3. Recommendations (3-5 bullets): specific, actionable, campaign-named. 
   Never recommend actions that require Google Ads API access — observations 
   and manual actions only.

Rules:
- Always reference specific campaign names and exact figures.
- If data shows an anomaly, explain it in context (is it expected? seasonal?).
- Do not make claims about medical efficacy of any advertised product.
- Flag uncertainty where data is ambiguous.
- Currency is GBP (£). Use £X,XXX format for spend, £XX for CPA.
```

**User prompt (constructed in `process()`):**
Passes the full structured data from ProcessingNode as a formatted prompt including:
- Account snapshot table
- Campaign breakdown with all metrics and deltas
- Anomaly list with severity and descriptions
- Funnel snapshot
- Reporting date and data lag flag

**Outputs (`task_context.update_node("NarrativeNode", ...)`):**
```python
{
    "headline": str,
    "what_stands_out": str,
    "recommendations": str,
}
```

**Error handling:** Same pattern.

---

### 6.4 TeamsDeliveryNode

**File:** `app/workflows/google_ads_report_nodes/teams_delivery_node.py`  
**Base class:** `Node`  
**Purpose:** Assemble the full markdown report and POST to Teams. Also serves as the error alert node.

**Inputs:**
- `task_context.metadata.get("error")` — if set, send failure alert instead of report
- `task_context.nodes["ProcessingNode"]` — for templated tables
- `task_context.nodes["NarrativeNode"]` — for AI narrative sections

**Algorithm:**
```
1. Check task_context.metadata.get("error")
   - If error: send failure alert message → return

2. Assemble markdown report (7 sections, see PRD FR-3.2)
3. Check length:
   - If <= 24,000 chars: single POST
   - If > 24,000 chars: split into 2 messages
4. POST to TEAMS_SOP_WEBHOOK_URL via httpx
5. On non-200 or exception:
   - await asyncio.sleep(30)
   - Retry once
   - If still fails: log error, continue (do not raise)
```

**Retry logic:**
```python
for attempt in range(2):
    try:
        response = await client.post(webhook_url, json=payload)
        if response.status_code == 200:
            delivery_status = "success"
            break
    except Exception as e:
        last_error = str(e)
    if attempt == 0:
        await asyncio.sleep(30)
else:
    logging.error(f"Teams delivery failed after retry: {last_error}")
    delivery_status = "failed"
```

**Failure alert format:**
```
⚠️ SOP Google Ads daily report failed to generate.
Time: {timestamp} UTC
Error: {error_summary}
Action: Check pipeline logs or run manual report.
```

**Outputs:**
```python
{
    "delivery_status": "success" | "failed",
    "delivery_error": str | None,
}
```

---

## 7. Snowflake Integration

### 7.1 Authentication — RSA Key-Pair

Snowflake key-pair authentication replaces username/password. Steps to set up:

**Generate key pair (run once):**
```bash
# Generate unencrypted private key
openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt

# Extract public key
openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub

# Register public key on Snowflake user
# ALTER USER <username> SET RSA_PUBLIC_KEY='<contents of rsa_key.pub without headers>';

# Base64-encode private key for env var storage
base64 -i rsa_key.p8 | tr -d '\n'  # → paste into SNOWFLAKE_PRIVATE_KEY_B64
```

**Connection factory (`app/services/snowflake_client.py`):**
```python
import os
import base64
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
import snowflake.connector

def get_snowflake_connection():
    private_key_b64 = os.environ["SNOWFLAKE_PRIVATE_KEY_B64"]
    pem_data = base64.b64decode(private_key_b64)
    
    passphrase = os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE")
    private_key = load_pem_private_key(
        pem_data,
        password=passphrase.encode() if passphrase else None,
    )
    
    pkb = private_key.private_bytes(
        encoding=Encoding.DER,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryption(),
    )
    
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key=pkb,
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ.get("SNOWFLAKE_SCHEMA", "MARKETING"),
        role=os.environ.get("SNOWFLAKE_ROLE"),
    )
```

**Async usage in node (run sync connector in thread pool):**
```python
import asyncio

async def _query_snowflake(self, sql: str, params: dict) -> list[dict]:
    def _run():
        conn = get_snowflake_connection()
        try:
            cur = conn.cursor(snowflake.connector.DictCursor)
            cur.execute(sql, params)
            return cur.fetchall()
        finally:
            conn.close()
    
    return await asyncio.to_thread(_run)
```

### 7.2 Environment Variables

Add to `docker/.env` (and `.env.example`):

```bash
# Snowflake
SNOWFLAKE_ACCOUNT=          # e.g. xy12345.eu-west-1
SNOWFLAKE_USER=             # service account username
SNOWFLAKE_PRIVATE_KEY_B64=  # base64-encoded PEM private key
SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=  # optional, if key is encrypted
SNOWFLAKE_WAREHOUSE=        # e.g. COMPUTE_WH
SNOWFLAKE_DATABASE=         # e.g. DWH
SNOWFLAKE_SCHEMA=           # e.g. MARKETING
SNOWFLAKE_ROLE=             # optional

# Teams
TEAMS_SOP_WEBHOOK_URL=      # incoming webhook URL for SOP channel

# Report config (optional overrides)
REPORT_BRAND=sop
REPORT_COMPLETENESS_THRESHOLD=400
REPORT_MIN_SPEND_GBP=10.0
```

---

## 8. Celery Beat Scheduling

**Modify `app/worker/config.py`:**

```python
from celery.schedules import crontab

def get_celery_config():
    redis_url = get_redis_url()
    return {
        "broker_url": redis_url,
        "result_backend": redis_url,
        "task_serializer": "json",
        "accept_content": ["json"],
        "result_serializer": "json",
        "enable_utc": True,
        "broker_connection_retry_on_startup": True,
        "beat_schedule": {
            "google-ads-report-sop": {
                "task": "process_google_ads_report",
                "schedule": crontab(hour=7, minute=30, day_of_week="1-5"),
                "args": [{"brand": "sop", "override_date": None}],
            }
        },
    }
```

**Add task to `app/worker/tasks.py`:**

```python
@celery_app.task(name="process_google_ads_report")
def process_google_ads_report(event: dict):
    """Fire-and-forget scheduled task. No DB persistence."""
    from workflows.workflow_registry import WorkflowRegistry
    workflow = WorkflowRegistry.GOOGLE_ADS_REPORT_WORKFLOW.value()
    workflow.run(event)
```

**Note:** Celery beat requires a separate beat process. In Docker Compose, this means adding a `celery_beat` service alongside the existing `celery_worker`. The beat process uses the same image — just override the command:
```yaml
celery_beat:
  command: celery -A worker.config.celery_app beat --loglevel=info
```

---

## 9. Key SQL Queries

### Completeness Check
```sql
SELECT COUNT(*) AS row_count
FROM DWH.MARKETING.ACQUISITION_MASTER
WHERE DATE = DATEADD(day, -1, CURRENT_DATE())
  AND BRAND = %(brand)s
  AND SOURCE = 'Google'
```

### Main Report Query
```sql
SELECT
    DATE,
    CAMPAIGN,
    CHANNEL,
    SUM(COST)                     AS COST,
    SUM(IMPRESSIONS)              AS IMPRESSIONS,
    SUM(CLICKS)                   AS CLICKS,
    AVG(CTR)                      AS CTR,
    AVG(CPC)                      AS CPC,
    SUM(NEW_ORDERS)               AS NEW_ORDERS,
    SUM(ORDERS)                   AS ORDERS,
    SUM(GROSS_REVENUE)            AS GROSS_REVENUE,
    SUM(NEW_GROSS_REVENUE)        AS NEW_GROSS_REVENUE,
    SUM(GROSS_PROFIT)             AS GROSS_PROFIT,
    SUM(NEW_GROSS_PROFIT)         AS NEW_GROSS_PROFIT,
    SUM(SESSIONS)                 AS SESSIONS,
    SUM(NEW_SESSIONS)             AS NEW_SESSIONS,
    SUM(STARTED_ASSESSMENT)       AS STARTED_ASSESSMENT,
    SUM(NEW_STARTED_ASSESSMENT)   AS NEW_STARTED_ASSESSMENT,
    SUM(SUBMITTED_ASSESSMENT)     AS SUBMITTED_ASSESSMENT,
    SUM(NEW_SUBMITTED_ASSESSMENT) AS NEW_SUBMITTED_ASSESSMENT,
    SUM(BASKET_PAGE)              AS BASKET_PAGE,
    SUM(NEW_BASKET_PAGE)          AS NEW_BASKET_PAGE,
    SUM(PURCHASED)                AS PURCHASED,
    SUM(NEW_PURCHASED)            AS NEW_PURCHASED
FROM DWH.MARKETING.ACQUISITION_MASTER
WHERE BRAND = %(brand)s
  AND SOURCE = 'Google'
  AND ATTRIBUTION = 'Last Click Attribution'
  AND IS_CAMPAIGN = 1
  AND DATE BETWEEN %(trailing_start)s AND %(reporting_date)s
GROUP BY DATE, CAMPAIGN, CHANNEL
ORDER BY DATE, COST DESC
```

---

## 10. TaskContext Flow (End-to-End)

```
Initial event:
  { "brand": "sop", "override_date": null }

After SnowflakeQueryNode:
  nodes["SnowflakeQueryNode"] = {
      "reporting_date": date(2026, 5, 27),
      "data_lag_flag": False,
      "reporting_day_rows": [...],   # raw dicts from Snowflake
      "trailing_rows": [...],
  }

After ProcessingNode:
  nodes["ProcessingNode"] = {
      "reporting_date": date(2026, 5, 27),
      "data_lag_flag": False,
      "account_snapshot": { ... },
      "campaign_rows": [ ... ],
      "anomalies": [ ... ],
      "funnel_snapshot": { ... },
  }

After NarrativeNode:
  nodes["NarrativeNode"] = {
      "headline": "...",
      "what_stands_out": "...",
      "recommendations": "...",
  }

After TeamsDeliveryNode:
  nodes["TeamsDeliveryNode"] = {
      "delivery_status": "success",
      "delivery_error": null,
  }
```

---

## 11. Error Flow

```
Any node failure:
  task_context.metadata["error"] = "Human-readable error description"
  task_context.stop_workflow()  →  next node: TeamsDeliveryNode skips
  
  Wait — stop_workflow() stops AFTER current node, but TeamsDeliveryNode
  is the last node. The error alert must therefore be sent from within
  whichever node fails, OR the TeamsDeliveryNode must always run.
```

**Solution — TeamsDeliveryNode always runs:**

The `should_stop` flag prevents remaining nodes from running. To ensure Teams always fires, the workflow uses a **two-phase approach**:

- Nodes 1–3 set `metadata["error"]` but do NOT call `stop_workflow()`
- `TeamsDeliveryNode` checks `metadata.get("error")` at the start
  - If error → send failure alert → `stop_workflow()`
  - If no error → assemble and send report

This guarantees Teams always receives either a report or an error alert.

---

## 12. Report Assembly (TeamsDeliveryNode)

The node assembles the markdown from two sources:

**Templated sections** (built by the node from ProcessingNode data):
- Report header
- Account Snapshot table
- Campaign Breakdown table
- Funnel Overview table

**AI-generated sections** (from NarrativeNode):
- Headline
- What Stands Out
- Recommendations

**Final format:**
```markdown
📊 **SOP Google Ads — Daily Report | {weekday} {date}**
*Data: Snowflake ACQUISITION_MASTER | Attribution: Last Click | {lag note if applicable}*

---

**{headline}**

---

### Account Snapshot
| Metric | Yesterday | 7d Avg | Δ |
...

### Campaign Breakdown
| Campaign | Spend | Δ | Conv | Δ | CPA | Δ | ROAS | Δ |
...

### Funnel Overview (New Customers)
| Stage | Volume | Rate |
...

---

### What Stands Out
{what_stands_out}

---

### Recommendations
{recommendations}
```

---

## 13. New Dependencies

Add to `pyproject.toml`:
```toml
[tool.poetry.dependencies]
snowflake-connector-python = ">=3.0.0"
cryptography = ">=41.0.0"  # likely already present; verify
```

---

## 14. Registry Update

```python
# app/workflows/workflow_registry.py
from enum import Enum
from workflows.example_streaming_workflow import ExampleStreamingWorkflow
from workflows.google_ads_report_workflow import GoogleAdsReportWorkflow

class WorkflowRegistry(Enum):
    EXAMPLE_STREAMING_WORKFLOW = ExampleStreamingWorkflow
    GOOGLE_ADS_REPORT_WORKFLOW = GoogleAdsReportWorkflow
```

---

## 15. Security Considerations

| Concern | Mitigation |
|---|---|
| Snowflake credentials | RSA key-pair; private key base64-encoded in env var, never in code |
| Teams webhook URL | Env var only; treat as secret (anyone with the URL can post to the channel) |
| Healthcare data in report | Report contains marketing metrics only — no PII, no patient data |
| AI narrative | Prompt explicitly prevents medical efficacy claims |
| Snowflake access scope | Service account should have SELECT-only access on `DWH.MARKETING.*` |

---

## 16. Observability

| Signal | Mechanism |
|---|---|
| Workflow start/end | Celery task logs (existing) |
| Node execution | `workflow.node_context()` logs start/finish per node (existing) |
| Snowflake query timing | Log query duration in `SnowflakeQueryNode` |
| Data lag events | `data_lag_flag = True` logged + visible in Teams report header |
| Delivery failure | Logged at ERROR level; Teams failure alert sent |
| Langfuse tracing | Optional — pass `enable_tracing=True` to workflow constructor |

---

## 17. Scale Path (KAP / SOD)

To add a new brand:
1. Add a new beat schedule entry in `worker/config.py`:
   ```python
   "google-ads-report-kap": {
       "task": "process_google_ads_report",
       "schedule": crontab(hour=7, minute=30, day_of_week="1-5"),
       "args": [{"brand": "kap", "override_date": None}],
   }
   ```
2. Add `TEAMS_KAP_WEBHOOK_URL` to `.env`
3. Update `TeamsDeliveryNode` to select webhook URL by brand
4. No code changes to any node logic required

---

## 18. Manual Trigger

For testing, catch-up runs, or the hackathon demo:

```bash
# Via Celery CLI (inside worker container)
celery -A worker.config.celery_app call process_google_ads_report \
  --args='[{"brand": "sop", "override_date": "2026-05-27"}]'

# Or directly in Python (for demo)
from workflows.google_ads_report_workflow import GoogleAdsReportWorkflow
workflow = GoogleAdsReportWorkflow()
result = workflow.run({"brand": "sop", "override_date": None})
```
