# Application Design Document: Google Ads Assistant

**Version:** 1.0  
**Date:** 2026-04-24  
**Status:** Approved  
**Phase:** PoC (Hackday MVP)

---

## 1. Overview

The Google Ads Assistant is a CLI-invoked workflow that connects to the Google Ads API, retrieves and processes campaign performance data, and generates two AI-authored Markdown reports — one for Weight Loss (WL) campaigns and one for Non-WL campaigns. Each report follows a three-section structure: a data-driven Executive Summary, a per-campaign Breakdown, and an AI-generated PPP (Progress, Problems, Priorities) analysis.

The system is built on the **GenAI Launchpad workflow/node layer** only. No API server, task queue, or database is used in the PoC. The full event-driven stack (FastAPI + Celery + PostgreSQL) is reserved for Phase 2 when scheduled delivery is introduced.

---

## 2. Cognitive Architecture (from Design Diagram)

The system maps to five cognitive layers:

| Layer | PoC Implementation | Phase 2+ |
|---|---|---|
| **Trigger** | Manual CLI command | 7am daily cron scheduler |
| **Grounding** | Google Ads API → Campaign Classifier → Metrics Engine | Same + GA integration |
| **Memory** | Hardcoded targets config (spend target, CPA target) | + Report history (prev day) |
| **Reasoning** | LLM Interpreter + PPP Report Drafter (sequential) | + Reflection Loop (critic/refine) |
| **Decision** | N/A (output written directly) | Human Review Gate + approval flow |
| **Output** | Markdown files in `app/reports/` | Google Doc + email delivery |

---

## 3. System Architecture

### 3.1 High-Level Flow

```
CLI (main.py)
    │
    └─► GoogleAdsWorkflow.run(event)
            │
            ├─ [1] FetchCampaignDataNode
            │       └─ Auth → fetch campaigns + metrics (yesterday + WoW date)
            │               + all-time avg impressions per campaign
            │
            ├─ [2] ClassifyAndProcessNode
            │       └─ Segment WL / Non-WL
            │          Calculate: CPA, CVR, CTR, WoW deltas, segment aggregates
            │
            ├─ [3] GenerateWLReportNode  (AgentNode → Claude)
            │       └─ Exec Summary + Campaign Breakdown + PPP section (WL)
            │
            ├─ [4] GenerateNonWLReportNode  (AgentNode → Claude)
            │       └─ Exec Summary + Campaign Breakdown + PPP section (Non-WL)
            │
            └─ [5] WriteReportsNode
                    └─ Write app/reports/report_wl_YYYY-MM-DD.md
                       Write app/reports/report_nonwl_YYYY-MM-DD.md
                       Print paths to stdout
```

### 3.2 Workflow Definition

```python
# app/workflows/google_ads_workflow.py

class GoogleAdsWorkflow(Workflow):
    workflow_schema = WorkflowSchema(
        description="Daily Google Ads performance report generator",
        event_schema=GoogleAdsReportEvent,
        start=FetchCampaignDataNode,
        nodes=[
            NodeConfig(node=FetchCampaignDataNode,    connections=[ClassifyAndProcessNode]),
            NodeConfig(node=ClassifyAndProcessNode,    connections=[GenerateWLReportNode]),
            NodeConfig(node=GenerateWLReportNode,      connections=[GenerateNonWLReportNode]),
            NodeConfig(node=GenerateNonWLReportNode,   connections=[WriteReportsNode]),
            NodeConfig(node=WriteReportsNode,          connections=[]),
        ]
    )
```

### 3.3 Event Schema

```python
# app/schemas/google_ads_event_schema.py

class GoogleAdsReportEvent(BaseModel):
    customer_id: str        # Google Ads Customer ID (e.g. "123-456-7890")
    report_date: date       # Date to report on (default: yesterday)
    comparison_date: date   # WoW comparison date (default: report_date - 7 days)
```

---

## 4. Node Specifications

### Node 1 — FetchCampaignDataNode

**Responsibility:** Authenticate with Google Ads API and retrieve all required raw data.

**Inputs:** `task_context.event` (customer_id, report_date, comparison_date)

**Operations:**
1. Initialise `GoogleAdsService` with credentials from environment
2. Fetch all active campaigns for the account (name, id, daily budget)
3. Fetch campaign-level metrics for `report_date` (spend, conversions, clicks, impressions, impression share)
4. Fetch campaign-level metrics for `comparison_date` (same metrics)
5. Fetch all-time average impressions per campaign (date range: campaign start → yesterday)

**Outputs stored in TaskContext:**
```python
task_context.update_node(
    self.node_name,
    campaigns=[{id, name, daily_budget_usd, start_date}],
    metrics_yesterday={campaign_id: {cost, conversions, clicks, impressions, impression_share}},
    metrics_last_week={campaign_id: {cost, conversions, clicks, impressions, impression_share}},
    alltime_avg_impressions={campaign_id: float},
)
```

**Error handling:** Halts workflow with clear message on auth failure or API error.

---

### Node 2 — ClassifyAndProcessNode

**Responsibility:** Segment campaigns and compute all derived metrics and aggregates.

**Inputs:** `task_context.nodes["FetchCampaignDataNode"]`

**Operations:**
1. Classify each campaign:
   - **WL**: `"weight" in campaign.name.lower()`
   - **Non-WL**: all others
2. For each campaign, compute per-date derived metrics:
   - `CTR = clicks / impressions` (None if impressions = 0)
   - `CVR = conversions / clicks` (None if clicks = 0)
   - `CPA = cost / conversions` (None if conversions = 0)
3. Compute WoW deltas for each metric:
   - `delta_abs = yesterday_val - last_week_val`
   - `delta_pct = delta_abs / last_week_val * 100` (None if last_week_val = 0)
4. Build segment aggregates (totals and averages across all campaigns in group)
5. Attach performance context: daily budget vs yesterday spend (pacing %)

**Outputs stored in TaskContext:**
```python
task_context.update_node(
    self.node_name,
    wl_campaigns=[ProcessedCampaign],
    nonwl_campaigns=[ProcessedCampaign],
    wl_aggregates=SegmentAggregate,
    nonwl_aggregates=SegmentAggregate,
)
```

**Business rules:**
- Monetary values from API are in micros → divide by 1,000,000 for USD
- Zero-denominator derived metrics → store as `None`, render as `N/A`
- CPA target = $500 (injected as context into AI prompts)

---

### Node 3 — GenerateWLReportNode (AgentNode)

**Responsibility:** Use Claude to generate the full WL report as a Markdown string.

**Agent config:**
```python
def get_agent_config(self) -> AgentConfig:
    return AgentConfig(
        model_provider=ModelProvider.ANTHROPIC,
        model_name="claude-sonnet-4-6",
        output_type=self.OutputType,  # {report_markdown: str}
        system_prompt=REPORT_GENERATION_SYSTEM_PROMPT,
    )
```

**Inputs to agent:** Structured dict containing WL segment aggregates, per-campaign data, WoW deltas, CPA target, report date.

**Report structure generated:**
```
# Weight Loss Campaign Performance Report — YYYY-MM-DD

## Executive Summary
[Brief narrative: 2–4 sentences on overall performance, key trend, headline metric vs target]

### Key Metrics (vs same day last week)
[Aggregate metrics table with WoW delta]

## Campaign Breakdown
### [Campaign Name]
[Per-campaign metrics table: spend, conversions, CPA, CVR, CTR, impressions,
impression share, daily budget, all-time avg impressions]

## PPP Analysis
> AI-generated | For review only — no automated actions taken

### Progress
[What is working: metrics trending positively, campaigns hitting targets]

### Problems
[What needs attention: underperforming campaigns, high CPA, low impression share]

### Priorities
[Specific, actionable recommendations ranked by impact]
```

**Outputs stored in TaskContext:**
```python
task_context.update_node(self.node_name, report_markdown=str)
```

---

### Node 4 — GenerateNonWLReportNode (AgentNode)

**Responsibility:** Same as Node 3 but for the Non-WL segment. Identical agent config and report structure, different segment data.

**Inputs:** `task_context.nodes["ClassifyAndProcessNode"]` (nonwl_campaigns, nonwl_aggregates)

**Outputs stored in TaskContext:**
```python
task_context.update_node(self.node_name, report_markdown=str)
```

---

### Node 5 — WriteReportsNode

**Responsibility:** Write both reports to disk and confirm output.

**Operations:**
1. Create `app/reports/` directory if it does not exist
2. Write WL report → `app/reports/report_wl_YYYY-MM-DD.md`
3. Write Non-WL report → `app/reports/report_nonwl_YYYY-MM-DD.md`
4. Print file paths to stdout

**Inputs:**
- `task_context.nodes["GenerateWLReportNode"]["report_markdown"]`
- `task_context.nodes["GenerateNonWLReportNode"]["report_markdown"]`

---

## 5. Directory Structure

```
google-ads-assistant/
├── app/
│   ├── main.py                                  # CLI entry point
│   ├── .env                                     # Credentials (gitignored)
│   ├── reports/                                 # Generated report output
│   ├── schemas/
│   │   └── google_ads_event_schema.py           # GoogleAdsReportEvent
│   ├── services/
│   │   └── google_ads_service.py                # Google Ads API client wrapper
│   ├── workflows/
│   │   ├── google_ads_workflow.py               # Workflow definition
│   │   └── google_ads_workflow_nodes/
│   │       ├── fetch_campaign_data_node.py
│   │       ├── classify_and_process_node.py
│   │       ├── generate_wl_report_node.py
│   │       ├── generate_nonwl_report_node.py
│   │       └── write_reports_node.py
│   └── prompts/
│       └── report_generation.j2                 # System prompt template
├── docker/                                      # Existing (Phase 2 use)
├── ai_docs/                                     # Project documentation
└── pyproject.toml
```

---

## 6. External Integrations

### 6.1 Google Ads API

| Attribute | Detail |
|---|---|
| Library | `google-ads` (official Python client v24+) |
| Auth method | OAuth2 with refresh token + developer token |
| Query language | GAQL (Google Ads Query Language) |
| Key resources | `Campaign`, `CampaignBudget`, `metrics.*`, `segments.date` |
| Rate limits | Standard: 15,000 operations/day (well within PoC usage) |
| Metric unit | Monetary values in micros (÷ 1,000,000 = USD) |

**Required GAQL queries:**

```sql
-- 1. Campaign list with budget
SELECT campaign.id, campaign.name, campaign.start_date,
       campaign_budget.amount_micros
FROM campaign
WHERE campaign.status = 'ENABLED'

-- 2. Metrics for a specific date
SELECT campaign.id,
       metrics.cost_micros, metrics.conversions,
       metrics.clicks, metrics.impressions,
       metrics.search_impression_share
FROM campaign
WHERE segments.date = 'YYYY-MM-DD'

-- 3. All-time avg impressions (date range: start_date to yesterday)
SELECT campaign.id, metrics.impressions
FROM campaign
WHERE segments.date BETWEEN 'start_date' AND 'yesterday'
```

### 6.2 Anthropic Claude API

| Attribute | Detail |
|---|---|
| Access | Via `pydantic-ai` `AgentNode` (framework built-in) |
| Model | `claude-sonnet-4-6` |
| Usage | 2 calls per run (one per segment report) |
| Auth | `ANTHROPIC_API_KEY` environment variable |

---

## 7. Configuration & Secrets

All credentials loaded from `app/.env` (local dev):

```bash
# Google Ads
GOOGLE_ADS_DEVELOPER_TOKEN=...
GOOGLE_ADS_CLIENT_ID=...
GOOGLE_ADS_CLIENT_SECRET=...
GOOGLE_ADS_REFRESH_TOKEN=...
GOOGLE_ADS_CUSTOMER_ID=...         # KAP account ID (default)
GOOGLE_ADS_LOGIN_CUSTOMER_ID=...   # Manager account ID (if MCC)

# AI
ANTHROPIC_API_KEY=...

# Report config
CPA_TARGET_USD=500
```

**CLI overrides (optional):**
```bash
python app/main.py --customer-id 123-456-7890 --date 2026-04-23
```

---

## 8. Data Models

```python
class CampaignDayMetrics(BaseModel):
    cost_usd: float
    conversions: float
    clicks: int
    impressions: int
    impression_share: Optional[float]
    ctr: Optional[float]       # clicks / impressions
    cvr: Optional[float]       # conversions / clicks
    cpa_usd: Optional[float]   # cost / conversions

class WoWDeltas(BaseModel):
    cost_usd: Tuple[float, Optional[float]]               # (abs_delta, pct_delta)
    conversions: Tuple[float, Optional[float]]
    impressions: Tuple[float, Optional[float]]
    impression_share: Tuple[Optional[float], Optional[float]]
    ctr: Tuple[Optional[float], Optional[float]]
    cvr: Tuple[Optional[float], Optional[float]]
    cpa_usd: Tuple[Optional[float], Optional[float]]

class ProcessedCampaign(BaseModel):
    id: str
    name: str
    segment: Literal["WL", "NON_WL"]
    daily_budget_usd: float
    alltime_avg_impressions: float
    yesterday: CampaignDayMetrics
    last_week: CampaignDayMetrics
    wow_deltas: WoWDeltas

class SegmentAggregate(BaseModel):
    segment: Literal["WL", "NON_WL"]
    campaign_count: int
    total_cost_usd: float
    total_conversions: float
    total_clicks: int
    total_impressions: int
    blended_cpa_usd: Optional[float]
    avg_cvr: Optional[float]
    avg_ctr: Optional[float]
    avg_impression_share: Optional[float]
    wow_deltas: WoWDeltas
```

---

## 9. Security

| Concern | Mitigation |
|---|---|
| Credential exposure | All secrets in `.env`; `.env` in `.gitignore` |
| Unauthorised API access | OAuth2 scoped refresh token (read-only ads access) |
| Data retention | No campaign data persisted; reports are local output files only |
| AI output trust | Clearly labelled as AI-generated; no automated campaign actions |

---

## 10. Error Handling

| Scenario | Behaviour |
|---|---|
| Missing env var | Halt at startup with named variable in error message |
| Google Ads auth failure | Halt in FetchCampaignDataNode with API error detail |
| No active campaigns found | Halt with "No active campaigns found for account X" |
| Zero conversions | CPA and CVR stored as `None`, rendered as `N/A` |
| Zero denominator (WoW delta) | Delta % stored as `None`, rendered as `—` |
| Claude API failure | Halt in GenerateReportNode; partial reports not written |

---

## 11. Performance

| Metric | Expected (PoC) |
|---|---|
| Google Ads API calls | 3 per run (campaigns, yesterday metrics, last-week metrics) |
| Claude API calls | 2 per run (one per segment report) |
| Total runtime | < 60 seconds |
| Report size | ~2–5 KB per Markdown file |

---

## 12. Phase Roadmap

### Phase 1 — PoC (current)
- CLI invocation, workflow/node layer only
- Google Ads API data retrieval + WL/Non-WL segmentation
- Metric processing (CPA, CVR, CTR, WoW deltas, segment aggregates)
- AI-generated Markdown reports with PPP section
- Output to `app/reports/`

### Phase 2 — Delivery Automation
- 7am cron trigger
- Google Docs API integration (replace Markdown output)
- Automated email delivery to marketing manager
- Anomaly detection with defined thresholds
- Reflection Loop: critic LLM checks draft vs targets and refines
- Report history as memory input (previous day comparison)

### Phase 3 — Scale
- Multi-account support
- Full event-driven stack (FastAPI + Celery + DB) for audit trail and replay
- Marketing team distribution
- Google Analytics integration

---

## 13. Future-Proofing Notes

- **Reflection Loop:** Insert `ReflectAndRefineWLNode` / `ReflectAndRefineNonWLNode` between generate and write nodes — no existing nodes need modification
- **Multi-account:** Parameterise `customer_id` in event schema; loop workflow invocations in `main.py`
- **Delivery channel:** Replace `WriteReportsNode` with `PublishToGoogleDocNode` — report Markdown string is the interface contract between nodes
- **Scheduler:** In Phase 2, wrap `main.py` in a Celery beat task or system cron — workflow is self-contained and stateless
