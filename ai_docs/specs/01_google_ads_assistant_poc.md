# Engineering Specification: Google Ads Assistant PoC

## Context

### Current State

- `app/main.py` — FastAPI app (existing, do not modify)
- `app/workflows/workflow_registry.py` — contains `WorkflowRegistry` enum with `EXAMPLE_STREAMING_WORKFLOW`
- `app/core/nodes/base.py` — `Node` base class with `save_output()`, `get_output()`, `update_node()`
- `app/core/nodes/agent.py` — `AgentNode` base class with `AgentConfig`, `ModelProvider`
- `app/core/workflow.py` — `Workflow` base class with `run()` / `run_async()`
- `app/core/task.py` — `TaskContext` with `update_node(**kwargs)` and `stop_workflow()`
- `app/core/schema.py` — `WorkflowSchema`, `NodeConfig`
- `app/services/prompt_loader.py` — `PromptManager.get_prompt(template, **kwargs)`
- `app/prompts/template.j2` — example Jinja2 template with frontmatter
- `app/.env.example` — existing env template; `ANTHROPIC_API_KEY` already present

No Google Ads workflow, service, schemas, or CLI entry point exist yet.

### Desired Outcome

Running `python app/run_report.py` from the project root authenticates with the Google Ads API, retrieves yesterday's campaign data for KAP's account, processes it into WL and Non-WL segments, generates two AI-narrated Markdown reports via Claude, and writes them to `app/reports/`.

### Success Criteria

- `python app/run_report.py` completes without unhandled exceptions
- `app/reports/report_wl_YYYY-MM-DD.md` and `app/reports/report_nonwl_YYYY-MM-DD.md` are written
- WL report contains only campaigns whose name contains "weight" (case-insensitive)
- Non-WL report contains all other campaigns
- Each report has three sections: Executive Summary, Campaign Breakdown, PPP Analysis
- Metrics (spend, conversions, CPA, CTR, CVR, impression share) match Google Ads UI for the same date
- WoW comparison references exactly 7 days prior to the report date
- PPP section contains specific, actionable AI-generated recommendations
- No credentials appear in any output file or stdout

---

## Implementation Specification

### Data Models & Types

**File: `app/schemas/google_ads_event_schema.py`**

```python
from datetime import date, timedelta
from pydantic import BaseModel, Field, model_validator

class GoogleAdsReportEvent(BaseModel):
    customer_id: str = Field(..., description="Google Ads Customer ID (digits only, no dashes)")
    report_date: date = Field(default_factory=lambda: date.today() - timedelta(days=1))
    comparison_date: date = Field(default=None)

    @model_validator(mode="after")
    def set_comparison_date(self):
        if self.comparison_date is None:
            self.comparison_date = self.report_date - timedelta(days=7)
        return self
```

**File: `app/schemas/google_ads_models.py`**

```python
from typing import Optional, Tuple, Literal
from pydantic import BaseModel

class CampaignDayMetrics(BaseModel):
    cost_usd: float
    conversions: float
    clicks: int
    impressions: int
    impression_share: Optional[float]  # None if unavailable (<10% threshold from API)
    ctr: Optional[float]               # clicks / impressions; None if impressions == 0
    cvr: Optional[float]               # conversions / clicks; None if clicks == 0
    cpa_usd: Optional[float]           # cost / conversions; None if conversions == 0

# Delta tuple: (absolute_delta, pct_delta)
# pct_delta is None when last_week value is 0
Delta = Tuple[Optional[float], Optional[float]]

class WoWDeltas(BaseModel):
    cost_usd: Delta
    conversions: Delta
    clicks: Delta
    impressions: Delta
    impression_share: Delta
    ctr: Delta
    cvr: Delta
    cpa_usd: Delta

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
    blended_cpa_usd: Optional[float]   # total_cost / total_conversions
    avg_cvr: Optional[float]
    avg_ctr: Optional[float]
    avg_impression_share: Optional[float]
    wow_deltas: WoWDeltas              # computed on aggregate values
```

---

### Interfaces & Contracts

**File: `app/services/google_ads_service.py`**

```python
class GoogleAdsService:
    def __init__(self, customer_id: str):
        """
        Initialises the Google Ads API client using credentials from environment.

        Args:
            customer_id: Google Ads Customer ID (digits only, e.g. "1234567890")

        Raises:
            EnvironmentError: If any required env var is missing.
            google.ads.googleads.errors.GoogleAdsException: On auth failure.
        """

    def fetch_campaigns(self) -> list[dict]:
        """
        Fetches all ENABLED campaigns for the account.

        Returns:
            List of dicts: [{id, name, daily_budget_usd, start_date}]
            - daily_budget_usd: campaign_budget.amount_micros / 1_000_000
            - start_date: str in "YYYY-MM-DD" format
        """

    def fetch_metrics_for_date(self, target_date: str) -> dict[str, dict]:
        """
        Fetches campaign-level metrics for a specific date.

        Args:
            target_date: Date string "YYYY-MM-DD"

        Returns:
            Dict keyed by campaign_id (str):
            {cost_micros, conversions, clicks, impressions, search_impression_share}
            All values are raw API values (cost in micros).
            Returns empty dict for campaign if no impressions that day.
        """

    def fetch_alltime_avg_impressions(
        self, campaigns: list[dict]
    ) -> dict[str, float]:
        """
        Fetches average daily impressions per campaign from start_date to yesterday.

        Args:
            campaigns: List from fetch_campaigns() (needs id and start_date)

        Returns:
            Dict keyed by campaign_id: average daily impressions (float)
            Falls back to 0.0 if campaign has no historical data.

        Note:
            Uses a single GAQL query with date range per campaign, aggregated in Python.
            Fallback: if all-time query fails, use last 30 days.
        """
```

---

### Plan - High-Level Tasks

- [x] **L1** Create directory structure and install dependencies
- [ ] **L2** Implement data models (`google_ads_event_schema.py`, `google_ads_models.py`)
- [ ] **L3** Implement `GoogleAdsService` with 3 GAQL queries
- [ ] **L4.1** Implement `FetchCampaignDataNode`
- [ ] **L4.2** Implement `ClassifyAndProcessNode`
- [ ] **L4.3** Implement `GenerateWLReportNode`
- [ ] **L4.4** Implement `GenerateNonWLReportNode`
- [ ] **L4.5** Implement `WriteReportsNode`
- [ ] **L5** Define `GoogleAdsWorkflow` and register in `WorkflowRegistry`
- [ ] **L6** Write `app/prompts/report_generation.j2` system prompt
- [ ] **L7** Implement `app/run_report.py` CLI entry point
- [ ] **L8** End-to-end verification with real credentials

---

### Implementation Order — Step-by-Step

#### Step 1: Dependencies

Add to `pyproject.toml` dependencies (or install directly):
```
google-ads>=24.0.0
```
`anthropic`, `pydantic-ai`, and `python-dotenv` are already available.

Add to `app/.env` (copy from `.env.example`, then add):
```bash
# Google Ads
GOOGLE_ADS_DEVELOPER_TOKEN=
GOOGLE_ADS_CLIENT_ID=
GOOGLE_ADS_CLIENT_SECRET=
GOOGLE_ADS_REFRESH_TOKEN=
GOOGLE_ADS_CUSTOMER_ID=      # KAP account (digits only)
GOOGLE_ADS_LOGIN_CUSTOMER_ID= # Manager/MCC account if applicable

# Report config
CPA_TARGET_USD=500
```

#### Step 2: Create `app/schemas/google_ads_event_schema.py`

Implement `GoogleAdsReportEvent` exactly as defined above.

#### Step 3: Create `app/schemas/google_ads_models.py`

Implement all four models: `CampaignDayMetrics`, `WoWDeltas`, `ProcessedCampaign`, `SegmentAggregate`.

#### Step 4: Create `app/services/google_ads_service.py`

```python
import os
from google.ads.googleads.client import GoogleAdsClient

class GoogleAdsService:
    def __init__(self, customer_id: str):
        self.customer_id = customer_id.replace("-", "")  # normalise
        credentials = {
            "developer_token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
            "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
            "refresh_token": os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
            "use_proto_plus": True,
        }
        login_id = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID")
        if login_id:
            credentials["login_customer_id"] = login_id.replace("-", "")
        self.client = GoogleAdsClient.load_from_dict(credentials)
        self.ga_service = self.client.get_service("GoogleAdsService")
```

**`fetch_campaigns()` GAQL:**
```sql
SELECT campaign.id, campaign.name, campaign.start_date,
       campaign_budget.amount_micros
FROM campaign
WHERE campaign.status = 'ENABLED'
ORDER BY campaign.name
```
Convert `campaign_budget.amount_micros / 1_000_000` to `daily_budget_usd`.

**`fetch_metrics_for_date(target_date)` GAQL:**
```sql
SELECT campaign.id,
       metrics.cost_micros,
       metrics.conversions,
       metrics.clicks,
       metrics.impressions,
       metrics.search_impression_share
FROM campaign
WHERE segments.date = '{target_date}'
  AND campaign.status = 'ENABLED'
```
Note: `search_impression_share` returns a float 0–1 or a sentinel value for `<10%` — treat as `None` if the API returns the sentinel string value.

**`fetch_alltime_avg_impressions(campaigns)` GAQL:**
```sql
SELECT campaign.id, metrics.impressions
FROM campaign
WHERE campaign.id IN ({comma_separated_ids})
  AND segments.date BETWEEN '{earliest_start_date}' AND '{yesterday}'
```
Aggregate in Python: sum impressions per campaign, divide by number of days in range.

#### Step 5: Create `app/workflows/google_ads_workflow_nodes/`

Create `__init__.py` (empty) in the directory.

**5a. `fetch_campaign_data_node.py`**

```python
from core.nodes.base import Node
from core.task import TaskContext
from services.google_ads_service import GoogleAdsService

class FetchCampaignDataNode(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        event = task_context.event
        service = GoogleAdsService(event.customer_id)

        campaigns = service.fetch_campaigns()
        metrics_yesterday = service.fetch_metrics_for_date(str(event.report_date))
        metrics_last_week = service.fetch_metrics_for_date(str(event.comparison_date))
        alltime_avg = service.fetch_alltime_avg_impressions(campaigns)

        task_context.update_node(
            self.node_name,
            campaigns=campaigns,
            metrics_yesterday=metrics_yesterday,
            metrics_last_week=metrics_last_week,
            alltime_avg_impressions=alltime_avg,
        )
        return task_context
```

**5b. `classify_and_process_node.py`**

```python
from core.nodes.base import Node
from core.task import TaskContext
from schemas.google_ads_models import (
    CampaignDayMetrics, WoWDeltas, ProcessedCampaign, SegmentAggregate
)

class ClassifyAndProcessNode(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        data = task_context.nodes["FetchCampaignDataNode"]
        campaigns = data["campaigns"]
        m_yday = data["metrics_yesterday"]
        m_lweek = data["metrics_last_week"]
        alltime_avg = data["alltime_avg_impressions"]

        wl, nonwl = [], []
        for c in campaigns:
            segment = "WL" if "weight" in c["name"].lower() else "NON_WL"
            yesterday = _build_metrics(m_yday.get(c["id"], {}))
            last_week = _build_metrics(m_lweek.get(c["id"], {}))
            deltas = _compute_deltas(yesterday, last_week)
            pc = ProcessedCampaign(
                id=c["id"], name=c["name"], segment=segment,
                daily_budget_usd=c["daily_budget_usd"],
                alltime_avg_impressions=alltime_avg.get(c["id"], 0.0),
                yesterday=yesterday, last_week=last_week, wow_deltas=deltas,
            )
            (wl if segment == "WL" else nonwl).append(pc)

        task_context.update_node(
            self.node_name,
            wl_campaigns=[c.model_dump() for c in wl],
            nonwl_campaigns=[c.model_dump() for c in nonwl],
            wl_aggregates=_build_aggregate("WL", wl).model_dump(),
            nonwl_aggregates=_build_aggregate("NON_WL", nonwl).model_dump(),
        )
        return task_context
```

Helper functions (private, in same file):
- `_build_metrics(raw: dict) -> CampaignDayMetrics` — converts micros to USD, computes CTR/CVR/CPA, handles None
- `_compute_deltas(yday: CampaignDayMetrics, lweek: CampaignDayMetrics) -> WoWDeltas` — computes (abs, pct) for each metric
- `_build_aggregate(segment, campaigns: list[ProcessedCampaign]) -> SegmentAggregate` — sums totals, computes blended metrics

**Key logic for `_compute_deltas`:**
```python
def _delta(a: Optional[float], b: Optional[float]) -> Delta:
    if a is None or b is None:
        return (None, None)
    abs_d = a - b
    pct_d = (abs_d / b * 100) if b != 0 else None
    return (round(abs_d, 4), round(pct_d, 2) if pct_d is not None else None)
```

**5c. `generate_wl_report_node.py`**

```python
import os
import json
from core.nodes.agent import AgentNode, AgentConfig, ModelProvider
from core.task import TaskContext
from pydantic import BaseModel
from services.prompt_loader import PromptManager

class GenerateWLReportNode(AgentNode):
    class OutputType(BaseModel):
        report_markdown: str

    def get_agent_config(self) -> AgentConfig:
        return AgentConfig(
            model_provider=ModelProvider.ANTHROPIC,
            model_name="claude-sonnet-4-6",
            output_type=self.OutputType,
            instructions=PromptManager.get_prompt(
                "report_generation",
                cpa_target=os.getenv("CPA_TARGET_USD", "500"),
            ),
        )

    async def process(self, task_context: TaskContext) -> TaskContext:
        data = task_context.nodes["ClassifyAndProcessNode"]
        user_prompt = _format_report_prompt(
            segment="Weight Loss (WL)",
            campaigns=data["wl_campaigns"],
            aggregates=data["wl_aggregates"],
            report_date=str(task_context.event.report_date),
            comparison_date=str(task_context.event.comparison_date),
        )
        result = await self.agent.run(user_prompt)
        task_context.update_node(
            self.node_name,
            report_markdown=result.output.report_markdown,
        )
        return task_context
```

`_format_report_prompt(segment, campaigns, aggregates, report_date, comparison_date) -> str`:
Returns a structured JSON/text block with all campaign data formatted for Claude to consume.

**5d. `generate_nonwl_report_node.py`**

Identical structure to `GenerateWLReportNode`. Uses `nonwl_campaigns` and `nonwl_aggregates`. Segment label: `"Non-Weight Loss (Non-WL)"`.

```python
class GenerateNonWLReportNode(AgentNode):
    class OutputType(BaseModel):
        report_markdown: str

    def get_agent_config(self) -> AgentConfig:
        # identical to WL version
        ...

    async def process(self, task_context: TaskContext) -> TaskContext:
        data = task_context.nodes["ClassifyAndProcessNode"]
        user_prompt = _format_report_prompt(
            segment="Non-Weight Loss (Non-WL)",
            campaigns=data["nonwl_campaigns"],
            aggregates=data["nonwl_aggregates"],
            ...
        )
        result = await self.agent.run(user_prompt)
        task_context.update_node(self.node_name, report_markdown=result.output.report_markdown)
        return task_context
```

**5e. `write_reports_node.py`**

```python
from pathlib import Path
from core.nodes.base import Node
from core.task import TaskContext

class WriteReportsNode(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        reports_dir = Path(__file__).parent.parent.parent / "reports"
        reports_dir.mkdir(exist_ok=True)
        date_str = str(task_context.event.report_date)

        wl_path = reports_dir / f"report_wl_{date_str}.md"
        nonwl_path = reports_dir / f"report_nonwl_{date_str}.md"

        wl_md = task_context.nodes["GenerateWLReportNode"]["report_markdown"]
        nonwl_md = task_context.nodes["GenerateNonWLReportNode"]["report_markdown"]

        wl_path.write_text(wl_md, encoding="utf-8")
        nonwl_path.write_text(nonwl_md, encoding="utf-8")

        print(f"\nReports written:")
        print(f"  {wl_path}")
        print(f"  {nonwl_path}")

        task_context.update_node(
            self.node_name,
            wl_path=str(wl_path),
            nonwl_path=str(nonwl_path),
        )
        return task_context
```

#### Step 6: Create `app/workflows/google_ads_workflow.py`

```python
from core.schema import WorkflowSchema, NodeConfig
from core.workflow import Workflow
from schemas.google_ads_event_schema import GoogleAdsReportEvent
from workflows.google_ads_workflow_nodes.fetch_campaign_data_node import FetchCampaignDataNode
from workflows.google_ads_workflow_nodes.classify_and_process_node import ClassifyAndProcessNode
from workflows.google_ads_workflow_nodes.generate_wl_report_node import GenerateWLReportNode
from workflows.google_ads_workflow_nodes.generate_nonwl_report_node import GenerateNonWLReportNode
from workflows.google_ads_workflow_nodes.write_reports_node import WriteReportsNode

class GoogleAdsWorkflow(Workflow):
    workflow_schema = WorkflowSchema(
        description="Daily Google Ads performance report generator — WL and Non-WL segments",
        event_schema=GoogleAdsReportEvent,
        start=FetchCampaignDataNode,
        nodes=[
            NodeConfig(node=FetchCampaignDataNode,    connections=[ClassifyAndProcessNode],   description="Fetches raw campaign data from Google Ads API"),
            NodeConfig(node=ClassifyAndProcessNode,    connections=[GenerateWLReportNode],     description="Segments campaigns and computes all metrics"),
            NodeConfig(node=GenerateWLReportNode,      connections=[GenerateNonWLReportNode],  description="Generates WL report via Claude"),
            NodeConfig(node=GenerateNonWLReportNode,   connections=[WriteReportsNode],         description="Generates Non-WL report via Claude"),
            NodeConfig(node=WriteReportsNode,          connections=[],                         description="Writes both reports to app/reports/"),
        ],
    )
```

#### Step 7: Register in WorkflowRegistry

**Update `app/workflows/workflow_registry.py`:**

```python
from enum import Enum
from workflows.example_streaming_workflow import ExampleStreamingWorkflow
from workflows.google_ads_workflow import GoogleAdsWorkflow

class WorkflowRegistry(Enum):
    EXAMPLE_STREAMING_WORKFLOW = ExampleStreamingWorkflow
    GOOGLE_ADS_REPORT = GoogleAdsWorkflow
```

#### Step 8: Create `app/prompts/report_generation.j2`

```jinja2
---
description: System prompt for Google Ads daily performance report generation
author: Google Ads Assistant
---

You are an expert Google Ads performance analyst generating a daily campaign performance report.

Your task is to analyse the campaign data provided and generate a complete Markdown report with exactly three sections:

## Report Structure

### 1. Executive Summary
Write a concise 2–4 sentence narrative covering:
- Overall segment performance for the day
- The most significant trend or signal
- How performance compares to the ${{ cpa_target }} CPA target

Then output a **Key Metrics** table showing aggregate metrics with WoW deltas using ↑/↓ indicators.

### 2. Campaign Breakdown
For each campaign, output a metrics table with: Spend, Conversions, CPA, CVR, CTR, Impressions, Impression Share, Daily Budget, All-Time Avg Impressions.
Use `N/A` for any metric that cannot be calculated (zero denominator).
Use `—` for any WoW delta that cannot be calculated (zero baseline).

### 3. PPP Analysis
Label this section clearly as AI-generated suggestions. Structure it as:

**Progress** — What is performing well. Reference specific campaigns and metrics.
**Problems** — What needs attention. Flag campaigns with CPA above ${{ cpa_target }}, significant impression drops, or declining CTR.
**Priorities** — Ranked list of specific, actionable recommendations. Reference campaign names. Never suggest automated actions — recommendations only.

## Formatting Rules
- Use Markdown headers (##, ###)
- Monetary values: prefix with $ and round to 2 decimal places
- Percentages: round to 2 decimal places with % suffix
- WoW deltas: show as ↑+X% or ↓-X% (green framing for positive signals, flag negative signals)
- CPA above ${{ cpa_target }} is underperforming — flag it
- Lower CPA = better; higher conversions = better; higher impression share = better
```

#### Step 9: Create `app/run_report.py`

```python
import argparse
import os
import sys
from datetime import date, timedelta

from dotenv import load_dotenv

load_dotenv(dotenv_path="app/.env")

from schemas.google_ads_event_schema import GoogleAdsReportEvent
from workflows.google_ads_workflow import GoogleAdsWorkflow


def main():
    parser = argparse.ArgumentParser(description="Google Ads Daily Report Generator")
    parser.add_argument(
        "--customer-id",
        default=os.getenv("GOOGLE_ADS_CUSTOMER_ID"),
        help="Google Ads Customer ID (overrides env var)",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Report date YYYY-MM-DD (default: yesterday)",
    )
    args = parser.parse_args()

    if not args.customer_id:
        print("Error: GOOGLE_ADS_CUSTOMER_ID not set. Use --customer-id or set env var.")
        sys.exit(1)

    report_date = (
        date.fromisoformat(args.date) if args.date else date.today() - timedelta(days=1)
    )

    event = GoogleAdsReportEvent(
        customer_id=args.customer_id,
        report_date=report_date,
    )

    print(f"Google Ads Assistant — Report for {report_date}")
    print(f"Account: {args.customer_id}")
    print(f"Comparison date: {event.comparison_date}")
    print("─" * 50)

    workflow = GoogleAdsWorkflow()
    workflow.run(event)


if __name__ == "__main__":
    # Run from project root: python app/run_report.py
    sys.path.insert(0, "app")
    main()
```

---

### Key Algorithms & Logic

**Metric derivation (in `_build_metrics`):**
```
cost_usd = raw.get("cost_micros", 0) / 1_000_000
conversions = float(raw.get("conversions", 0))
clicks = int(raw.get("clicks", 0))
impressions = int(raw.get("impressions", 0))
impression_share = raw.get("search_impression_share")  # None if sentinel or missing

ctr = clicks / impressions if impressions > 0 else None
cvr = conversions / clicks if clicks > 0 else None
cpa_usd = cost_usd / conversions if conversions > 0 else None
```

**Segment aggregate (in `_build_aggregate`):**
```
total_cost = sum(c.yesterday.cost_usd for c in campaigns)
total_conversions = sum(c.yesterday.conversions for c in campaigns)
total_clicks = sum(c.yesterday.clicks for c in campaigns)
total_impressions = sum(c.yesterday.impressions for c in campaigns)

blended_cpa = total_cost / total_conversions if total_conversions > 0 else None
avg_cvr = total_conversions / total_clicks if total_clicks > 0 else None
avg_ctr = total_clicks / total_impressions if total_impressions > 0 else None
avg_impression_share = mean of non-None impression_share values, or None

wow_deltas = _compute_deltas(
    aggregate_yesterday_metrics,
    aggregate_last_week_metrics   # re-compute from last_week fields
)
```

**User prompt formatting (in `_format_report_prompt`):**

Produce a structured text block Claude can read without ambiguity:
```
SEGMENT: {segment}
REPORT DATE: {report_date}
COMPARISON DATE: {comparison_date}

=== SEGMENT AGGREGATES ===
Yesterday: total_spend=$X, conversions=N, blended_CPA=$X, avg_CTR=X%, avg_CVR=X%, total_impressions=N, avg_impression_share=X%
Last week: [same fields]
WoW: [deltas]

=== CAMPAIGNS ===
[For each campaign:]
Campaign: {name}
  Budget/day: $X | All-time avg impressions: N
  Yesterday: spend=$X, conv=N, CPA=$X/N/A, CVR=X%/N/A, CTR=X%/N/A, impressions=N, imp_share=X%/N/A
  Last week: [same]
  WoW: [deltas]
```

---

### Error Handling

| Scenario | Behaviour |
|---|---|
| Missing required env var | `sys.exit(1)` with named variable in error message (checked in `run_report.py` before workflow start) |
| `GOOGLE_ADS_CUSTOMER_ID` not set | Error printed, exit code 1 |
| Google Ads API auth failure | `GoogleAdsException` propagates with API error detail; workflow halts |
| No campaigns returned | Print warning "No active campaigns found" and exit cleanly |
| Campaign has zero impressions on a date | `fetch_metrics_for_date` returns empty dict for that campaign; `_build_metrics({})` returns all-zero/None metrics |
| `search_impression_share` sentinel value (`"< 10%"`) | Treat as `None` in `_build_metrics` |
| Zero-denominator in metric calc | All derived metrics (CPA, CVR, CTR) return `None` |
| Zero-denominator in WoW delta % | `pct_delta = None`, rendered as `—` in report |
| Claude API failure | Exception propagates from `AgentNode.process()`; workflow halts with error |
| `app/reports/` directory doesn't exist | `Path.mkdir(exist_ok=True)` creates it |

---

## Testing Requirements

### Critical Test Cases (E2E — PoC)

```
Scenario: Full pipeline run with real credentials
  Given: app/.env contains valid Google Ads and Anthropic credentials
  When:  python app/run_report.py
  Then:
    - Exit code 0
    - app/reports/report_wl_{yesterday}.md exists and is non-empty
    - app/reports/report_nonwl_{yesterday}.md exists and is non-empty
    - WL report contains section headers: "Executive Summary", "Campaign Breakdown", "PPP Analysis"
    - Non-WL report contains same section headers
    - No campaign names containing "weight" appear in the Non-WL report
    - No campaign names NOT containing "weight" appear in the WL report
```

### Edge Cases to Consider

- **Campaign with zero spend on report date** — should appear in breakdown with $0.00 and N/A for CPA/CVR
- **Campaign with zero spend on comparison date** — WoW deltas for spend show absolute delta only, pct delta = `—`
- **All campaigns in one segment** — the other segment report is generated with 0 campaigns; PPP notes no campaigns active
- **`impression_share` below 10% threshold** — API returns sentinel; store as `None`, render as `N/A`
- **`--date` flag with a date that has no data** — all metrics are 0/None; report still generates with `N/A` throughout

---

## Dependencies & Constraints

### External Dependencies

```
google-ads>=24.0.0          # Official Google Ads Python client
python-dotenv>=1.0.0        # Already present in framework
pydantic-ai                 # Already present in framework
anthropic                   # Already present in framework
python-frontmatter          # Already present (used by PromptManager)
jinja2                      # Already present (used by PromptManager)
```

### Required Google Ads API Credentials

| Credential | Where to obtain |
|---|---|
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Google Ads → Tools → API Center |
| `GOOGLE_ADS_CLIENT_ID` | Google Cloud Console → OAuth 2.0 Client |
| `GOOGLE_ADS_CLIENT_SECRET` | Google Cloud Console → OAuth 2.0 Client |
| `GOOGLE_ADS_REFRESH_TOKEN` | Run OAuth2 flow (google-auth-oauthlib or oauth2l) |
| `GOOGLE_ADS_CUSTOMER_ID` | Google Ads → Account ID (top-right, remove dashes) |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | Manager account ID (only if using MCC) |

### Constraints & Assumptions

- Run from project root: `python app/run_report.py` (not from `app/`)
- `sys.path.insert(0, "app")` in `run_report.py` enables absolute imports
- `GOOGLE_ADS_CUSTOMER_ID` digits only — dashes stripped automatically in `GoogleAdsService.__init__`
- `search_impression_share` requires the account to be on Search campaigns; may not apply to all campaign types
- `workflow.run(event)` is synchronous — appropriate for CLI invocation
- `AgentConfig.instructions` is the system prompt — set once at agent init; campaign data goes in the user prompt passed to `agent.run()`
- `PromptManager` resolves templates relative to `app/prompts/` — ensure `run_report.py` is executed with `app/` on the path
- The `LANGFUSE_*` env vars are optional — `AgentNode` instruments by default but gracefully skips if keys missing

---

## Open Questions

All resolved. No open questions remain for PoC implementation.

---

## Assumptions Documented

1. `workflow.run(event)` accepts a Pydantic model instance directly (confirmed from framework source)
2. `agent.run(user_prompt)` returns a `RunResult` — output accessed via `result.output.report_markdown`
3. `google-ads` client accepts a plain dict via `GoogleAdsClient.load_from_dict()`
4. `search_impression_share` is the correct GAQL field name for impression share on Search campaigns
5. All 13 KAP campaigns are `ENABLED` status — removed/paused campaigns are excluded by the `WHERE campaign.status = 'ENABLED'` filter
6. Jinja2 template variable syntax `{{ cpa_target }}` works in `.j2` files loaded by `PromptManager`
7. `CPA_TARGET_USD` defaults to `"500"` if not set in `.env`
