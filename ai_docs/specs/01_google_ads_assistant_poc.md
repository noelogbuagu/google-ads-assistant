# Engineering Specification: Google Ads Assistant PoC

**Updated:** 2026-04-24 — Data source changed from Google Ads API to CSV files

## Context

### Current State

- `app/main.py` — FastAPI app (existing, do not modify)
- `app/workflows/workflow_registry.py` — `WorkflowRegistry` enum with `EXAMPLE_STREAMING_WORKFLOW`
- `app/core/nodes/base.py` — `Node` base class; use `task_context.update_node(self.node_name, **kwargs)`
- `app/core/nodes/agent.py` — `AgentNode` with `AgentConfig(instructions=..., output_type=...)`
- `app/core/workflow.py` — `Workflow` base class with `run()` (synchronous)
- `app/core/task.py` — `TaskContext` with `update_node(**kwargs)`
- `app/services/prompt_loader.py` — `PromptManager.get_prompt(template, **kwargs)`
- `app/prompts/template.j2` — example Jinja2 template with frontmatter

Nothing Google Ads-related exists yet. No API credentials needed.

### CSV Format (actual)

Files are placed in `app/data/`. Naming convention: `cr_DD_MM.csv` (e.g. `cr_10_04.csv`).

```
Row 1:  "Campaign report"                          ← skip
Row 2:  "April 10, 2026 - April 10, 2026"          ← parse date from here
Row 3:  Column headers                             ← see below
Rows 4+: Campaign data rows
Last rows: Start with "Total:" or "Total: ..."    ← skip
```

**Relevant columns** (from row 3 headers):
| CSV Column | Description | Notes |
|---|---|---|
| `Campaign status` | Enabled / Paused | |
| `Campaign` | Campaign name | Used for WL classification |
| `Budget` | Daily budget (USD) | Already in USD |
| `Cost` | Spend (USD) | Already in USD; has comma thousands separator |
| `Impr.` | Impressions | Has comma thousands separator |
| `Clicks` | Clicks | Has comma thousands separator |
| `Conv. rate` | CVR | Has `%` suffix |
| `Conversions` | Conversions | May be decimal (e.g. 5.42) |
| `Cost / conv.` | CPA (USD) | Already in USD |
| `Avg. CPC` | Average CPC | Already in USD |

**Parsing rules:**
- Strip commas from numeric fields: `"6,627"` → `6627`
- Strip `%` from rates and divide by 100: `"8.81%"` → `0.0881`
- `"--"` or `"0"` → `0` (or `None` for derived metrics)
- Filter: only include rows where `Cost` > 0 (active campaigns only)
- Skip rows where `Campaign` starts with "Total"

### Desired Outcome

Running `python app/run_report.py` reads three CSVs from `app/data/`, processes them into two WoW comparisons (Apr 10→17, Apr 17→24), and generates two AI-narrated Markdown reports — one for WL campaigns and one for Non-WL — written to `app/reports/`.

### Success Criteria

- `python app/run_report.py` completes without unhandled exceptions
- `app/reports/report_wl_YYYY-MM-DD.md` and `app/reports/report_nonwl_YYYY-MM-DD.md` are written (date = most recent CSV)
- WL report contains only campaigns whose name contains "weight" (case-insensitive)
- Non-WL report contains all other campaigns with Cost > 0
- Each report shows two WoW comparison periods: Apr 10→17 and Apr 17→24
- PPP section contains specific, AI-generated recommendations referencing campaign names
- No hardcoded paths — data directory configurable via CLI flag

---

## Implementation Specification

### Data Models & Types

**File: `app/schemas/google_ads_event_schema.py`**

```python
from pathlib import Path
from pydantic import BaseModel, Field

class GoogleAdsReportEvent(BaseModel):
    data_dir: Path = Field(default=Path("app/data"), description="Directory containing CSV files")
```

**File: `app/schemas/google_ads_models.py`**

```python
from typing import Optional, Tuple, Literal
from pydantic import BaseModel

# (absolute_delta, pct_delta) — pct is None when baseline is 0
Delta = Tuple[Optional[float], Optional[float]]

class CampaignDayMetrics(BaseModel):
    cost_usd: float
    conversions: float
    clicks: int
    impressions: int
    ctr: Optional[float]      # clicks / impressions; None if impressions == 0
    cvr: Optional[float]      # conversions / clicks; None if clicks == 0
    cpa_usd: Optional[float]  # cost / conversions; None if conversions == 0
    avg_cpc: Optional[float]  # from CSV "Avg. CPC"; None if "--"

class WoWDeltas(BaseModel):
    cost_usd: Delta
    conversions: Delta
    clicks: Delta
    impressions: Delta
    ctr: Delta
    cvr: Delta
    cpa_usd: Delta

class ProcessedCampaign(BaseModel):
    name: str
    segment: Literal["WL", "NON_WL"]
    daily_budget_usd: float
    # Three time points
    date_oldest: CampaignDayMetrics   # Apr 10
    date_mid: CampaignDayMetrics      # Apr 17
    date_latest: CampaignDayMetrics   # Apr 24
    # Two WoW deltas
    wow1: WoWDeltas  # Apr 10 → Apr 17
    wow2: WoWDeltas  # Apr 17 → Apr 24

class SegmentAggregate(BaseModel):
    segment: Literal["WL", "NON_WL"]
    campaign_count: int
    # Aggregates per time point
    total_cost_oldest: float
    total_cost_mid: float
    total_cost_latest: float
    total_conversions_oldest: float
    total_conversions_mid: float
    total_conversions_latest: float
    total_clicks_oldest: int
    total_clicks_mid: int
    total_clicks_latest: int
    total_impressions_oldest: int
    total_impressions_mid: int
    total_impressions_latest: int
    blended_cpa_oldest: Optional[float]
    blended_cpa_mid: Optional[float]
    blended_cpa_latest: Optional[float]
    avg_cvr_oldest: Optional[float]
    avg_cvr_mid: Optional[float]
    avg_cvr_latest: Optional[float]
    avg_ctr_oldest: Optional[float]
    avg_ctr_mid: Optional[float]
    avg_ctr_latest: Optional[float]
    # Segment-level WoW deltas
    wow1: WoWDeltas  # Apr 10 → Apr 17
    wow2: WoWDeltas  # Apr 17 → Apr 24
```

---

### Interfaces & Contracts

**File: `app/services/csv_loader.py`**

```python
class CSVLoader:
    def load_csvs(self, data_dir: Path) -> dict[str, dict[str, dict]]:
        """
        Loads all cr_*.csv files from data_dir, sorted chronologically.

        Returns:
            {
              "oldest":  {campaign_name: raw_row_dict},   # Apr 10
              "mid":     {campaign_name: raw_row_dict},   # Apr 17
              "latest":  {campaign_name: raw_row_dict},   # Apr 24
            }

        Raises:
            FileNotFoundError: If data_dir doesn't exist or fewer than 3 CSVs found.
            ValueError: If CSV format is unexpected (missing required columns).

        Notes:
            - Skips rows where Cost == 0
            - Skips rows starting with "Total"
            - Parses date from row 2 of each CSV to determine chronological order
            - File naming convention: cr_DD_MM.csv used as fallback for sorting
        """

    def _parse_date_from_header(self, csv_path: Path) -> date:
        """
        Reads row 2 of CSV to extract the report date.
        Example: '"April 10, 2026 - April 10, 2026"' → date(2026, 4, 10)
        """

    def _parse_row(self, row: dict) -> dict:
        """
        Cleans a raw CSV row:
        - Strips commas from numeric fields
        - Strips % and divides by 100 for rates
        - Converts '--' to None
        - Returns cleaned dict with float/int values
        """
```

---

### Plan - High-Level Tasks

- [ ] **L1** Create directory structure, create `app/data/`, install `google-ads` removed (no longer needed)
- [ ] **L2** Implement data models (`google_ads_event_schema.py`, `google_ads_models.py`)
- [ ] **L3** Implement `CSVLoader` service
- [ ] **L4.1** Implement `LoadCSVDataNode`
- [ ] **L4.2** Implement `ClassifyAndProcessNode`
- [ ] **L4.3** Implement `GenerateWLReportNode`
- [ ] **L4.4** Implement `GenerateNonWLReportNode`
- [ ] **L4.5** Implement `WriteReportsNode`
- [ ] **L5** Define `GoogleAdsWorkflow` + register in `WorkflowRegistry`
- [ ] **L6** Write `app/prompts/report_generation.j2`
- [ ] **L7** Implement `app/run_report.py`
- [ ] **L8** E2E test with the three real CSVs

---

### Implementation Order — Step-by-Step

#### Step 1: Directory setup

```
app/
├── data/          ← drop CSVs here (cr_10_04.csv, cr_17_04.csv, cr_24_04.csv)
├── reports/       ← generated output
├── schemas/
├── services/
├── workflows/
│   └── google_ads_workflow_nodes/
└── prompts/
```

No new pip dependencies required beyond what the framework already has (`pandas` is available; alternatively use stdlib `csv` module — prefer stdlib `csv` to avoid dependency).

#### Step 2: `app/schemas/google_ads_event_schema.py`

```python
from pathlib import Path
from pydantic import BaseModel, Field

class GoogleAdsReportEvent(BaseModel):
    data_dir: Path = Field(default=Path("app/data"))
```

#### Step 3: `app/schemas/google_ads_models.py`

Implement all models as defined above.

#### Step 4: `app/services/csv_loader.py`

```python
import csv
from datetime import date, datetime
from pathlib import Path

class CSVLoader:
    REQUIRED_COLS = {"Campaign", "Budget", "Cost", "Impr.", "Clicks",
                     "Conv. rate", "Conversions", "Cost / conv.", "Avg. CPC"}

    def load_csvs(self, data_dir: Path) -> dict[str, dict[str, dict]]:
        csv_files = sorted(data_dir.glob("cr_*.csv"))
        if len(csv_files) < 3:
            raise FileNotFoundError(
                f"Expected 3 CSV files in {data_dir}, found {len(csv_files)}"
            )
        # Parse date from each file and sort chronologically
        dated = [(self._parse_date_from_header(f), f) for f in csv_files]
        dated.sort(key=lambda x: x[0])
        oldest_date, oldest_file = dated[0]
        mid_date,    mid_file    = dated[1]
        latest_date, latest_file = dated[2]

        return {
            "oldest":  {"date": oldest_date, "campaigns": self._load_file(oldest_file)},
            "mid":     {"date": mid_date,    "campaigns": self._load_file(mid_file)},
            "latest":  {"date": latest_date, "campaigns": self._load_file(latest_file)},
        }

    def _parse_date_from_header(self, path: Path) -> date:
        with open(path, encoding="utf-8") as f:
            next(f)  # skip "Campaign report"
            date_line = next(f).strip().strip('"')
            # "April 10, 2026 - April 10, 2026" → take first part
            date_str = date_line.split(" - ")[0]
            return datetime.strptime(date_str, "%B %d, %Y").date()

    def _load_file(self, path: Path) -> dict[str, dict]:
        """Returns {campaign_name: cleaned_row} for rows with Cost > 0."""
        result = {}
        with open(path, encoding="utf-8") as f:
            next(f)  # skip "Campaign report"
            next(f)  # skip date line
            reader = csv.DictReader(f)
            for row in reader:
                name = row.get("Campaign", "").strip()
                if not name or name.startswith("Total"):
                    continue
                cleaned = self._parse_row(row)
                if cleaned["cost_usd"] > 0:
                    result[name] = cleaned
        return result

    def _parse_row(self, row: dict) -> dict:
        def to_float(val):
            if not val or val.strip() in ("--", ""):
                return 0.0
            return float(val.replace(",", "").replace("%", "").strip())

        cost = to_float(row.get("Cost", "0"))
        conversions = to_float(row.get("Conversions", "0"))
        clicks = int(to_float(row.get("Clicks", "0")))
        impressions = int(to_float(row.get("Impr.", "0")))
        avg_cpc_raw = row.get("Avg. CPC", "--")
        avg_cpc = to_float(avg_cpc_raw) if avg_cpc_raw.strip() not in ("--", "0", "") else None
        budget = to_float(row.get("Budget", "0"))

        # Conv. rate is already a percentage string like "8.81%"
        cvr_raw = row.get("Conv. rate", "0%")
        cvr = to_float(cvr_raw) / 100 if cvr_raw.strip() not in ("--", "") else None

        cpa_raw = row.get("Cost / conv.", "--")
        cpa = to_float(cpa_raw) if cpa_raw.strip() not in ("--", "0", "") and conversions > 0 else None

        return {
            "cost_usd": cost,
            "conversions": conversions,
            "clicks": clicks,
            "impressions": impressions,
            "cvr": cvr,
            "cpa_usd": cpa,
            "avg_cpc": avg_cpc,
            "daily_budget_usd": budget,
        }
```

#### Step 5: Workflow nodes (`app/workflows/google_ads_workflow_nodes/`)

Create `__init__.py` (empty).

**5a. `load_csv_data_node.py`**

```python
from core.nodes.base import Node
from core.task import TaskContext
from services.csv_loader import CSVLoader

class LoadCSVDataNode(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        loader = CSVLoader()
        data = loader.load_csvs(task_context.event.data_dir)
        task_context.update_node(self.node_name, **data)
        return task_context
```

Stores in task_context:
```python
{
  "oldest":  {"date": date(2026,4,10), "campaigns": {name: row_dict}},
  "mid":     {"date": date(2026,4,17), "campaigns": {name: row_dict}},
  "latest":  {"date": date(2026,4,24), "campaigns": {name: row_dict}},
}
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
        raw = task_context.nodes["LoadCSVDataNode"]

        oldest_campaigns = raw["oldest"]["campaigns"]
        mid_campaigns    = raw["mid"]["campaigns"]
        latest_campaigns = raw["latest"]["campaigns"]

        # Union of all campaign names that appear in any file
        all_names = set(oldest_campaigns) | set(mid_campaigns) | set(latest_campaigns)

        wl, nonwl = [], []
        for name in sorted(all_names):
            segment = "WL" if "weight" in name.lower() else "NON_WL"
            oldest  = _build_metrics(oldest_campaigns.get(name, {}))
            mid     = _build_metrics(mid_campaigns.get(name, {}))
            latest  = _build_metrics(latest_campaigns.get(name, {}))
            budget  = (
                latest_campaigns.get(name, {})
                or mid_campaigns.get(name, {})
                or oldest_campaigns.get(name, {})
            ).get("daily_budget_usd", 0.0)

            pc = ProcessedCampaign(
                name=name, segment=segment, daily_budget_usd=budget,
                date_oldest=oldest, date_mid=mid, date_latest=latest,
                wow1=_compute_deltas(oldest, mid),
                wow2=_compute_deltas(mid, latest),
            )
            (wl if segment == "WL" else nonwl).append(pc)

        task_context.update_node(
            self.node_name,
            dates={
                "oldest": str(raw["oldest"]["date"]),
                "mid":    str(raw["mid"]["date"]),
                "latest": str(raw["latest"]["date"]),
            },
            wl_campaigns=[c.model_dump() for c in wl],
            nonwl_campaigns=[c.model_dump() for c in nonwl],
            wl_aggregates=_build_aggregate("WL", wl).model_dump(),
            nonwl_aggregates=_build_aggregate("NON_WL", nonwl).model_dump(),
        )
        return task_context
```

**Helper functions** (private, same file):

```python
def _build_metrics(raw: dict) -> CampaignDayMetrics:
    cost = raw.get("cost_usd", 0.0)
    conv = raw.get("conversions", 0.0)
    clicks = raw.get("clicks", 0)
    impr = raw.get("impressions", 0)
    return CampaignDayMetrics(
        cost_usd=cost,
        conversions=conv,
        clicks=clicks,
        impressions=impr,
        ctr=clicks / impr if impr > 0 else None,
        cvr=conv / clicks if clicks > 0 else None,
        cpa_usd=cost / conv if conv > 0 else None,
        avg_cpc=raw.get("avg_cpc"),
    )

def _delta(a, b) -> tuple:
    """Compute (abs_delta, pct_delta). Both None if either input is None."""
    if a is None or b is None:
        return (None, None)
    abs_d = round(a - b, 4)
    pct_d = round((abs_d / b) * 100, 2) if b != 0 else None
    return (abs_d, pct_d)

def _compute_deltas(from_: CampaignDayMetrics, to_: CampaignDayMetrics) -> WoWDeltas:
    return WoWDeltas(
        cost_usd=_delta(to_.cost_usd, from_.cost_usd),
        conversions=_delta(to_.conversions, from_.conversions),
        clicks=_delta(to_.clicks, from_.clicks),
        impressions=_delta(to_.impressions, from_.impressions),
        ctr=_delta(to_.ctr, from_.ctr),
        cvr=_delta(to_.cvr, from_.cvr),
        cpa_usd=_delta(to_.cpa_usd, from_.cpa_usd),
    )

def _build_aggregate(segment: str, campaigns: list) -> SegmentAggregate:
    def total(field, period):
        return sum(getattr(getattr(c, period), field) or 0 for c in campaigns)

    def blended_cpa(period):
        cost = total("cost_usd", period)
        conv = total("conversions", period)
        return cost / conv if conv > 0 else None

    def avg_cvr(period):
        conv = total("conversions", period)
        clicks = total("clicks", period)
        return conv / clicks if clicks > 0 else None

    def avg_ctr(period):
        clicks = total("clicks", period)
        impr = total("impressions", period)
        return clicks / impr if impr > 0 else None

    # Build aggregate metrics objects for delta computation
    agg_oldest = CampaignDayMetrics(
        cost_usd=total("cost_usd","date_oldest"), conversions=total("conversions","date_oldest"),
        clicks=int(total("clicks","date_oldest")), impressions=int(total("impressions","date_oldest")),
        ctr=avg_ctr("date_oldest"), cvr=avg_cvr("date_oldest"), cpa_usd=blended_cpa("date_oldest"), avg_cpc=None,
    )
    agg_mid = CampaignDayMetrics(
        cost_usd=total("cost_usd","date_mid"), conversions=total("conversions","date_mid"),
        clicks=int(total("clicks","date_mid")), impressions=int(total("impressions","date_mid")),
        ctr=avg_ctr("date_mid"), cvr=avg_cvr("date_mid"), cpa_usd=blended_cpa("date_mid"), avg_cpc=None,
    )
    agg_latest = CampaignDayMetrics(
        cost_usd=total("cost_usd","date_latest"), conversions=total("conversions","date_latest"),
        clicks=int(total("clicks","date_latest")), impressions=int(total("impressions","date_latest")),
        ctr=avg_ctr("date_latest"), cvr=avg_cvr("date_latest"), cpa_usd=blended_cpa("date_latest"), avg_cpc=None,
    )

    return SegmentAggregate(
        segment=segment, campaign_count=len(campaigns),
        total_cost_oldest=agg_oldest.cost_usd, total_cost_mid=agg_mid.cost_usd, total_cost_latest=agg_latest.cost_usd,
        total_conversions_oldest=agg_oldest.conversions, total_conversions_mid=agg_mid.conversions, total_conversions_latest=agg_latest.conversions,
        total_clicks_oldest=agg_oldest.clicks, total_clicks_mid=agg_mid.clicks, total_clicks_latest=agg_latest.clicks,
        total_impressions_oldest=agg_oldest.impressions, total_impressions_mid=agg_mid.impressions, total_impressions_latest=agg_latest.impressions,
        blended_cpa_oldest=blended_cpa("date_oldest"), blended_cpa_mid=blended_cpa("date_mid"), blended_cpa_latest=blended_cpa("date_latest"),
        avg_cvr_oldest=avg_cvr("date_oldest"), avg_cvr_mid=avg_cvr("date_mid"), avg_cvr_latest=avg_cvr("date_latest"),
        avg_ctr_oldest=avg_ctr("date_oldest"), avg_ctr_mid=avg_ctr("date_mid"), avg_ctr_latest=avg_ctr("date_latest"),
        wow1=_compute_deltas(agg_oldest, agg_mid),
        wow2=_compute_deltas(agg_mid, agg_latest),
    )
```

**5c. `generate_wl_report_node.py`**

```python
import json, os
from pydantic import BaseModel
from core.nodes.agent import AgentNode, AgentConfig, ModelProvider
from core.task import TaskContext
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
        user_prompt = _format_prompt(
            segment="Weight Loss (WL)",
            campaigns=data["wl_campaigns"],
            aggregates=data["wl_aggregates"],
            dates=data["dates"],
        )
        result = await self.agent.run(user_prompt)
        task_context.update_node(self.node_name, report_markdown=result.output.report_markdown)
        return task_context
```

**5d. `generate_nonwl_report_node.py`** — identical to WL node, uses `nonwl_campaigns`/`nonwl_aggregates`, segment label `"Non-Weight Loss (Non-WL)"`.

**5e. `write_reports_node.py`**

```python
from pathlib import Path
from core.nodes.base import Node
from core.task import TaskContext

class WriteReportsNode(Node):
    async def process(self, task_context: TaskContext) -> TaskContext:
        reports_dir = Path("app/reports")
        reports_dir.mkdir(exist_ok=True)
        latest_date = task_context.nodes["ClassifyAndProcessNode"]["dates"]["latest"]

        wl_path    = reports_dir / f"report_wl_{latest_date}.md"
        nonwl_path = reports_dir / f"report_nonwl_{latest_date}.md"

        wl_path.write_text(task_context.nodes["GenerateWLReportNode"]["report_markdown"], encoding="utf-8")
        nonwl_path.write_text(task_context.nodes["GenerateNonWLReportNode"]["report_markdown"], encoding="utf-8")

        print(f"\nReports written:\n  {wl_path}\n  {nonwl_path}")
        task_context.update_node(self.node_name, wl_path=str(wl_path), nonwl_path=str(nonwl_path))
        return task_context
```

#### Step 6: `app/workflows/google_ads_workflow.py`

```python
from core.schema import WorkflowSchema, NodeConfig
from core.workflow import Workflow
from schemas.google_ads_event_schema import GoogleAdsReportEvent
from workflows.google_ads_workflow_nodes.load_csv_data_node import LoadCSVDataNode
from workflows.google_ads_workflow_nodes.classify_and_process_node import ClassifyAndProcessNode
from workflows.google_ads_workflow_nodes.generate_wl_report_node import GenerateWLReportNode
from workflows.google_ads_workflow_nodes.generate_nonwl_report_node import GenerateNonWLReportNode
from workflows.google_ads_workflow_nodes.write_reports_node import WriteReportsNode

class GoogleAdsWorkflow(Workflow):
    workflow_schema = WorkflowSchema(
        description="Daily Google Ads performance report from CSV exports",
        event_schema=GoogleAdsReportEvent,
        start=LoadCSVDataNode,
        nodes=[
            NodeConfig(node=LoadCSVDataNode,          connections=[ClassifyAndProcessNode]),
            NodeConfig(node=ClassifyAndProcessNode,    connections=[GenerateWLReportNode]),
            NodeConfig(node=GenerateWLReportNode,      connections=[GenerateNonWLReportNode]),
            NodeConfig(node=GenerateNonWLReportNode,   connections=[WriteReportsNode]),
            NodeConfig(node=WriteReportsNode,          connections=[]),
        ],
    )
```

#### Step 7: Register in WorkflowRegistry

```python
# app/workflows/workflow_registry.py
from enum import Enum
from workflows.example_streaming_workflow import ExampleStreamingWorkflow
from workflows.google_ads_workflow import GoogleAdsWorkflow

class WorkflowRegistry(Enum):
    EXAMPLE_STREAMING_WORKFLOW = ExampleStreamingWorkflow
    GOOGLE_ADS_REPORT = GoogleAdsWorkflow
```

#### Step 8: `app/prompts/report_generation.j2`

```jinja2
---
description: System prompt for Google Ads daily performance report
author: Google Ads Assistant
---

You are an expert Google Ads performance analyst. Generate a complete Markdown report for the campaign segment provided.

The data covers THREE dates with TWO week-over-week comparison periods:
- Period 1 (WoW 1): Change from the oldest date to the middle date
- Period 2 (WoW 2): Change from the middle date to the most recent date

CPA target: ${{ cpa_target }}. Lower CPA = better. Higher conversions = better.

## Required Report Structure

### 1. Executive Summary
2–4 sentence narrative: overall trend across both periods, most significant signal, performance vs ${{ cpa_target }} CPA target.

Then output a **Key Metrics** table:
| Metric | Date 1 (oldest) | Date 2 (mid) | Date 3 (latest) | WoW 1 Δ | WoW 2 Δ |
Use ↑/↓ for direction. Format: ↑+12.5% or ↓-8.3%

### 2. Campaign Breakdown
For each campaign, a metrics table with the same three-date + two-delta structure.
Use `N/A` for uncalculable metrics (zero denominator).
Use `—` for uncalculable deltas (zero baseline).
Metrics per campaign: Spend, Conversions, CPA, CVR, CTR, Impressions, Avg CPC, Daily Budget.

### 3. PPP Analysis
> ⚠️ AI-generated suggestions. No automated actions taken. Human review required.

**Progress** — Campaigns/metrics trending positively across both periods.
**Problems** — Campaigns with CPA above ${{ cpa_target }}, declining conversions, or worsening CTR.
**Priorities** — Ranked, specific, actionable recommendations. Name the campaign. No automated actions.

## Formatting
- $ prefix for monetary values, 2 decimal places
- % suffix for rates, 2 decimal places
- Use campaign names exactly as provided
```

#### Step 9: `app/run_report.py`

```python
import argparse
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path="app/.env")

sys.path.insert(0, "app")

from schemas.google_ads_event_schema import GoogleAdsReportEvent
from workflows.google_ads_workflow import GoogleAdsWorkflow


def main():
    parser = argparse.ArgumentParser(description="Google Ads Daily Report Generator")
    parser.add_argument(
        "--data-dir",
        default="app/data",
        help="Directory containing CSV files (default: app/data)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"Error: data directory '{data_dir}' does not exist.")
        sys.exit(1)

    event = GoogleAdsReportEvent(data_dir=data_dir)

    print("Google Ads Assistant — Report Generator")
    print(f"Reading CSVs from: {data_dir}")
    print("─" * 50)

    workflow = GoogleAdsWorkflow()
    workflow.run(event)


if __name__ == "__main__":
    main()
```

---

### Key Algorithms & Logic

**CSV date parsing:**
```
open file → skip row 1 → read row 2
strip quotes → split on " - " → take first part
parse with strptime("%B %d, %Y") → date object
sort files by parsed date → assign oldest/mid/latest
```

**User prompt for AI (in `_format_prompt`):**
```
SEGMENT: {segment}
DATES: oldest={dates.oldest}, mid={dates.mid}, latest={dates.latest}

=== SEGMENT AGGREGATES ===
{dates.oldest}: spend=${total_cost_oldest}, conv={total_conversions_oldest}, CPA=${blended_cpa_oldest}/N/A, CVR={avg_cvr_oldest*100:.2f}%/N/A, CTR={avg_ctr_oldest*100:.2f}%/N/A, impressions={total_impressions_oldest}
{dates.mid}:    [same]
{dates.latest}: [same]
WoW 1 ({dates.oldest}→{dates.mid}): spend Δ={wow1.cost_usd}, conv Δ={wow1.conversions}, CPA Δ={wow1.cpa_usd}, ...
WoW 2 ({dates.mid}→{dates.latest}): [same structure]

=== CAMPAIGNS ({campaign_count} total) ===
Campaign: {name}
  Budget: ${daily_budget_usd}/day
  {dates.oldest}: spend=${cost_oldest}, conv={conv_oldest}, CPA=${cpa_oldest}/N/A, CVR={cvr_oldest}/N/A, CTR={ctr_oldest}/N/A, impressions={impr_oldest}, avg_cpc=${avg_cpc_oldest}/N/A
  {dates.mid}:    [same]
  {dates.latest}: [same]
  WoW 1: [deltas]
  WoW 2: [deltas]
[repeat for each campaign]
```

---

### Error Handling

| Scenario | Behaviour |
|---|---|
| `app/data/` missing or <3 CSVs | `FileNotFoundError` raised in `LoadCSVDataNode`; workflow halts with message |
| CSV missing required columns | `KeyError` with column name; workflow halts |
| All campaigns have 0 cost in a file | Empty campaign dict; all metrics will be 0/None; report generates with N/A |
| Campaign in `latest` but not in `oldest`/`mid` | Missing periods default to `_build_metrics({})` → all zeros/None |
| Zero denominator in metric calc | Return `None`; render as `N/A` in report |
| Zero baseline in WoW delta | `pct_delta = None`; render as `—` |
| Claude API failure | Exception propagates; workflow halts before files written |
| `app/reports/` missing | `Path.mkdir(exist_ok=True)` creates it automatically |

---

## Testing Requirements

### E2E Test (PoC acceptance)

```
Given: app/data/ contains cr_10_04.csv, cr_17_04.csv, cr_24_04.csv
When:  python app/run_report.py
Then:
  - Exit code 0
  - app/reports/report_wl_2026-04-24.md exists and is non-empty
  - app/reports/report_nonwl_2026-04-24.md exists and is non-empty
  - WL report: every campaign name contains "weight" (case-insensitive)
  - Non-WL report: no campaign name contains "weight"
  - Both reports have sections: "Executive Summary", "Campaign Breakdown", "PPP Analysis"
  - Both reports show 3 date columns and 2 WoW delta columns in tables
  - Spend figures match CSV totals for each date
```

### Edge Cases

- **Campaign appears in Apr 24 but not Apr 10 or 17** → prior periods show 0/N/A
- **Campaign appears in Apr 10 and 17 but has 0 cost on Apr 24** → excluded (Cost filter on each file)
- **`--data-dir` override** → `python app/run_report.py --data-dir /tmp/test_data` reads from that path

---

## Dependencies & Constraints

```
# No new dependencies required
# stdlib csv module used for CSV parsing
# anthropic, pydantic-ai, python-dotenv already in framework
```

**Required `.env` variables** (much simpler than before — only AI key needed):
```bash
ANTHROPIC_API_KEY=...
CPA_TARGET_USD=500
```

### Constraints & Assumptions

- `app/run_report.py` run from project root; `sys.path.insert(0, "app")` enables absolute imports
- Exactly 3 CSVs expected in `app/data/`; naming must match `cr_*.csv` glob
- CSV date extracted from row 2 (format: `"Month DD, YYYY - Month DD, YYYY"`)
- Campaigns with `Cost == 0` on a given date are excluded from that date's analysis
- WL classification: `"weight" in campaign_name.lower()` — relies on naming convention
- `workflow.run(event)` is synchronous — appropriate for CLI
- `AgentConfig.instructions` = static system prompt (set at agent init); campaign data goes in `agent.run(user_prompt)`

## Open Questions

None — fully resolved for PoC.

## Assumptions

1. All three CSVs are for the same account and use the same column structure
2. The `cr_DD_MM.csv` filename pattern holds; date from row 2 is the authoritative sort key
3. `workflow.run(event)` accepts a Pydantic model instance directly
4. `result.output.report_markdown` accesses Claude's typed output
5. `PromptManager.get_prompt()` resolves templates relative to `app/prompts/` when run from project root with `app/` on sys.path
