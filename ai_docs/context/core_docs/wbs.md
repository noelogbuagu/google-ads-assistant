# Work Breakdown Structure: Google Ads Assistant

**Version:** 1.0  
**Date:** 2026-04-24  
**Status:** Approved  
**Phase:** PoC (Hackday — ~2.5hrs)  
**Build order:** Layer-by-layer

---

## Timeline Overview

| Layer | Description | Estimate | Cumulative |
|---|---|---|---|
| L1 | Project Setup | 15 min | 0:15 |
| L2 | Data Models & Schemas | 15 min | 0:30 |
| L3 | Google Ads Service | 30 min | 1:00 |
| L4 | Workflow Nodes | 50 min | 1:50 |
| L5 | Workflow Definition & Registry | 10 min | 2:00 |
| L6 | Prompt Engineering | 10 min | 2:10 |
| L7 | CLI Entry Point | 10 min | 2:20 |
| L8 | End-to-End Verification | 20 min | 2:40 |

> **Risk:** Google Ads API credential setup is the highest-risk item. If it exceeds 30 minutes, simplify by deferring all-time avg impressions query (use a fixed lookback window instead).

---

## Layer 1 — Project Setup
**Target: 15 min**

### T1.1 — Create directory structure
```
app/
├── schemas/
├── services/
├── workflows/
│   └── google_ads_workflow_nodes/
├── prompts/
└── reports/
```
**Done when:** All directories exist.

### T1.2 — Install dependencies
Add to `pyproject.toml` / install via pip:
```
google-ads>=24.0.0
python-dotenv>=1.0.0
```
`pydantic-ai` and `anthropic` are already in the framework.  
**Done when:** `pip install` completes without errors.

### T1.3 — Configure credentials
Create `app/.env` (from `.env.example`):
```bash
GOOGLE_ADS_DEVELOPER_TOKEN=
GOOGLE_ADS_CLIENT_ID=
GOOGLE_ADS_CLIENT_SECRET=
GOOGLE_ADS_REFRESH_TOKEN=
GOOGLE_ADS_CUSTOMER_ID=
GOOGLE_ADS_LOGIN_CUSTOMER_ID=
ANTHROPIC_API_KEY=
CPA_TARGET_USD=500
```
Ensure `app/.env` is in `.gitignore`.  
**Done when:** `.env` file populated, gitignored.

---

## Layer 2 — Data Models & Schemas
**Target: 15 min**

### T2.1 — Event schema
**File:** `app/schemas/google_ads_event_schema.py`

```python
class GoogleAdsReportEvent(BaseModel):
    customer_id: str
    report_date: date        # defaults to yesterday
    comparison_date: date    # defaults to report_date - 7 days
```
**Done when:** Schema importable with no errors.

### T2.2 — Internal data models
**File:** `app/schemas/google_ads_models.py`

Models to define:
- `CampaignDayMetrics` — cost, conversions, clicks, impressions, impression_share, ctr, cvr, cpa (all Optional floats where derived)
- `WoWDeltas` — per-metric tuple of (abs_delta, pct_delta)
- `ProcessedCampaign` — id, name, segment, daily_budget_usd, alltime_avg_impressions, yesterday, last_week, wow_deltas
- `SegmentAggregate` — segment totals + averages + wow_deltas

**Done when:** All models importable, pydantic validation passes on sample data.

---

## Layer 3 — Google Ads Service
**Target: 30 min** ⚠️ Critical path

### T3.1 — Service class skeleton
**File:** `app/services/google_ads_service.py`

```python
class GoogleAdsService:
    def __init__(self, customer_id: str): ...
    def fetch_campaigns(self) -> list[dict]: ...
    def fetch_metrics_for_date(self, date: str) -> dict[str, dict]: ...
    def fetch_alltime_avg_impressions(self, campaigns: list[dict]) -> dict[str, float]: ...
```

Initialise `GoogleAdsClient` from `google.ads.googleads.client` using env vars.  
**Done when:** Client initialises without errors.

### T3.2 — `fetch_campaigns()` GAQL query
```sql
SELECT campaign.id, campaign.name, campaign.start_date,
       campaign_budget.amount_micros
FROM campaign
WHERE campaign.status = 'ENABLED'
```
Returns list of `{id, name, start_date, daily_budget_usd}`.  
**Done when:** Returns non-empty list for KAP account.

### T3.3 — `fetch_metrics_for_date()` GAQL query
```sql
SELECT campaign.id,
       metrics.cost_micros, metrics.conversions,
       metrics.clicks, metrics.impressions,
       metrics.search_impression_share
FROM campaign
WHERE segments.date = '{date}'
```
Returns `{campaign_id: {cost_usd, conversions, clicks, impressions, impression_share}}`.  
**Done when:** Returns data for yesterday and last-week date.

### T3.4 — `fetch_alltime_avg_impressions()` GAQL query
```sql
SELECT campaign.id, metrics.impressions
FROM campaign
WHERE segments.date BETWEEN '{start_date}' AND '{yesterday}'
```
Aggregate per campaign, divide by number of days to get average.  
**Fallback if time-constrained:** Use a fixed 30-day lookback instead of all-time.  
**Done when:** Returns `{campaign_id: float}` for all campaigns.

---

## Layer 4 — Workflow Nodes
**Target: 50 min**

All nodes in: `app/workflows/google_ads_workflow_nodes/`

### T4.1 — FetchCampaignDataNode (15 min)
**File:** `fetch_campaign_data_node.py`

```python
class FetchCampaignDataNode(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        service = GoogleAdsService(task_context.event.customer_id)
        campaigns = service.fetch_campaigns()
        metrics_yesterday = service.fetch_metrics_for_date(str(task_context.event.report_date))
        metrics_last_week = service.fetch_metrics_for_date(str(task_context.event.comparison_date))
        alltime_avg = service.fetch_alltime_avg_impressions(campaigns)
        task_context.update_node(self.node_name,
            campaigns=campaigns,
            metrics_yesterday=metrics_yesterday,
            metrics_last_week=metrics_last_week,
            alltime_avg_impressions=alltime_avg,
        )
        return task_context
```
**Done when:** Node stores raw API data in task_context without errors.

### T4.2 — ClassifyAndProcessNode (15 min)
**File:** `classify_and_process_node.py`

Logic:
1. Classify: `"weight" in campaign["name"].lower()` → WL else Non-WL
2. Compute per-campaign CampaignDayMetrics for yesterday + last_week
3. Compute WoWDeltas per campaign (handle None denominators)
4. Build SegmentAggregate for WL and Non-WL

**Done when:** task_context contains `wl_campaigns`, `nonwl_campaigns`, `wl_aggregates`, `nonwl_aggregates` with correct types.

### T4.3 — GenerateWLReportNode (10 min)
**File:** `generate_wl_report_node.py`

```python
class GenerateWLReportNode(AgentNode):
    class OutputType(BaseModel):
        report_markdown: str

    def get_agent_config(self) -> AgentConfig:
        return AgentConfig(
            model_provider=ModelProvider.ANTHROPIC,
            model_name="claude-sonnet-4-6",
            output_type=self.OutputType,
            system_prompt=load_prompt("report_generation"),
        )

    async def process(self, task_context: TaskContext) -> TaskContext:
        data = task_context.nodes["ClassifyAndProcessNode"]
        result = await self.agent.run(
            user_prompt=format_wl_prompt(data, task_context.event)
        )
        task_context.update_node(self.node_name, report_markdown=result.output.report_markdown)
        return task_context
```
**Done when:** Node returns a non-empty markdown string.

### T4.4 — GenerateNonWLReportNode (5 min)
**File:** `generate_nonwl_report_node.py`

Identical structure to GenerateWLReportNode — uses `nonwl_campaigns` and `nonwl_aggregates`.  
**Done when:** Node returns a non-empty markdown string for Non-WL data.

### T4.5 — WriteReportsNode (5 min)
**File:** `write_reports_node.py`

```python
class WriteReportsNode(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        reports_dir = Path("app/reports")
        reports_dir.mkdir(exist_ok=True)
        date_str = str(task_context.event.report_date)

        wl_path = reports_dir / f"report_wl_{date_str}.md"
        nonwl_path = reports_dir / f"report_nonwl_{date_str}.md"

        wl_path.write_text(task_context.nodes["GenerateWLReportNode"]["report_markdown"])
        nonwl_path.write_text(task_context.nodes["GenerateNonWLReportNode"]["report_markdown"])

        print(f"Reports written:\n  {wl_path}\n  {nonwl_path}")
        task_context.update_node(self.node_name, wl_path=str(wl_path), nonwl_path=str(nonwl_path))
        return task_context
```
**Done when:** Two `.md` files exist in `app/reports/`.

---

## Layer 5 — Workflow Definition & Registry
**Target: 10 min**

### T5.1 — GoogleAdsWorkflow
**File:** `app/workflows/google_ads_workflow.py`

```python
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
**Done when:** `GoogleAdsWorkflow()` instantiates without validation errors.

### T5.2 — Register in WorkflowRegistry
**File:** `app/worker/workflow_registry.py` (existing)

Add:
```python
class WorkflowRegistry(Enum):
    ...
    GOOGLE_ADS_REPORT = GoogleAdsWorkflow
```
**Done when:** `WorkflowRegistry.GOOGLE_ADS_REPORT.value` returns the workflow class.

---

## Layer 6 — Prompt Engineering
**Target: 10 min**

### T6.1 — System prompt template
**File:** `app/prompts/report_generation.j2`

The prompt must instruct Claude to:
- Generate a complete Markdown report for the given segment
- Include: Executive Summary (narrative + metrics table), Campaign Breakdown (per-campaign tables), PPP Analysis (Progress / Problems / Priorities)
- Reference the $500 CPA target when evaluating performance
- Use directional indicators (↑/↓) for WoW changes
- Label the PPP section as AI-generated suggestions
- Never suggest automated actions — recommendations only

**Done when:** Prompt loads via `PromptService` without errors and produces structured output when tested.

---

## Layer 7 — CLI Entry Point
**Target: 10 min**

### T7.1 — main.py
**File:** `app/main.py`

```python
def main():
    parser = argparse.ArgumentParser(description="Google Ads Daily Report Generator")
    parser.add_argument("--customer-id", default=os.getenv("GOOGLE_ADS_CUSTOMER_ID"))
    parser.add_argument("--date", default=None, help="Report date YYYY-MM-DD (default: yesterday)")
    args = parser.parse_args()

    report_date = date.fromisoformat(args.date) if args.date else date.today() - timedelta(days=1)
    comparison_date = report_date - timedelta(days=7)

    event = GoogleAdsReportEvent(
        customer_id=args.customer_id,
        report_date=report_date,
        comparison_date=comparison_date,
    )

    print(f"Generating reports for {report_date} vs {comparison_date}...")
    workflow = GoogleAdsWorkflow()
    workflow.run(event)

if __name__ == "__main__":
    main()
```
**Done when:** `python app/main.py --help` runs without errors.

---

## Layer 8 — End-to-End Verification
**Target: 20 min**

### T8.1 — Configure real credentials
- Obtain Google Ads developer token from Google Ads API Center
- Create OAuth2 credentials (client ID + secret) in Google Cloud Console
- Generate refresh token using OAuth2 flow
- Populate `app/.env` with all values

### T8.2 — Run the tool
```bash
python app/main.py
```
Expected stdout:
```
Generating reports for 2026-04-23 vs 2026-04-16...
Fetching campaign data...
Processing metrics...
Generating WL report...
Generating Non-WL report...
Reports written:
  app/reports/report_wl_2026-04-23.md
  app/reports/report_nonwl_2026-04-23.md
```

### T8.3 — Verify report content
Acceptance checklist:
- [ ] Two `.md` files exist in `app/reports/`
- [ ] WL report contains only campaigns with "weight" in name
- [ ] Non-WL report contains the remaining campaigns
- [ ] Each report has Executive Summary, Campaign Breakdown, PPP Analysis sections
- [ ] Metrics match Google Ads UI for the same date range
- [ ] WoW deltas reference the correct comparison date (7 days prior)
- [ ] PPP section contains specific, actionable recommendations
- [ ] No credentials appear in output files

---

## Dependencies & Sequencing

```
L1 (Setup)
  └─► L2 (Models)
        └─► L3 (Service)  ← CRITICAL PATH
              └─► L4 (Nodes)
                    └─► L5 (Workflow + Registry)
                          ├─► L6 (Prompts)
                          └─► L7 (CLI)
                                └─► L8 (E2E Test)
```

L6 (Prompts) can be written in parallel with L5 if time allows.

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Google Ads API OAuth2 setup > 30 min | Medium | High | Prepare credentials before starting build; use `google-ads-python` quickstart |
| GAQL query syntax errors | Medium | Medium | Test queries in Google Ads Query Builder first |
| All-time avg impressions query timeout | Low | Low | Fall back to 30-day lookback window |
| pydantic-ai AgentNode integration issue | Low | Medium | Fall back to direct `anthropic` SDK call |
| Claude output not valid Markdown | Low | Low | Add output validation in WriteReportsNode; retry once |
| Scope creep | Medium | High | Strictly enforce layer sequence; log deferred items |

---

## Definition of Done (PoC)

The PoC is complete when:
1. `python app/main.py` runs to completion with no unhandled exceptions
2. Two Markdown files are written to `app/reports/`
3. Report content is accurate (metrics verified against Google Ads UI)
4. Both reports contain all three required sections (Summary, Breakdown, PPP)
5. No credentials are exposed in code or output

---

## Deferred to Phase 2

- Unit tests for metric calculation logic
- Integration tests with mocked API responses
- CI/CD pipeline
- Scheduled execution (cron)
- Email delivery
- Google Docs output
- Reflection Loop (critic/refine)
- Multi-account support
