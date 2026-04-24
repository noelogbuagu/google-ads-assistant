# Google Ads Assistant — Workflow Architecture

This document describes the end-to-end pipeline that runs when you execute `python app/run_report.py`.

---

```mermaid
flowchart TD

    %% ── ENTRY POINT ────────────────────────────────────────────────────────────
    subgraph CLI["🖥️  CLI  ·  run_report.py"]
        A1["parse arguments\n--data-dir  /  --files"] --> A2{files\nprovided?}
        A2 -- yes --> A3["validate each of the\n3 file paths exists on disk"]
        A2 -- no  --> A4["glob cr_*.csv from data_dir\nassert ≥ 3 files found"]
        A3 & A4 --> A5["build event payload\n{ data_dir, files }"]
    end

    A5 --> EVT

    EVT["📥  GoogleAdsReportEvent\n─────────────────────\ndata_dir : Path\nfiles    : list[Path] | None"]

    EVT --> LOAD

    %% ── NODE 1 — LOAD CSV DATA ─────────────────────────────────────────────────
    subgraph LOAD["📂  LoadCSVDataNode"]
        L1["select source files\nexplicit list OR glob cr_*.csv"] --> L2
        L2["for each file\n① skip row 1  →  'Campaign report'\n② read row 2  →  parse report date\n   e.g. 'April 10, 2026 - April 10, 2026'\n③ DictReader from row 3  →  headers + data"]
        L2 --> L3{"filter rows"}
        L3 -- "Campaign == '--'" --> L3X["✗ skip total row"]
        L3 -- "status starts with 'Total'" --> L3X
        L3 -- "Cost == 0" --> L3X
        L3 -- "valid row" --> L4
        L4["parse_row()\n· strip commas from numeric strings\n· Conv. rate  %  →  decimal  ÷ 100\n· '--'  →  None or 0.0\n· extract: cost_usd, conversions,\n  clicks, impressions, cvr, cpa_usd,\n  avg_cpc, daily_budget_usd"]
        L4 --> L5["sort all 3 files chronologically\nby extracted date header\n→ label as  oldest / mid / latest"]
    end

    LOAD --> TC1

    TC1["🗂  TaskContext  ·  after LoadCSVDataNode\n─────────────────────────────────────\noldest : { date: date, campaigns: dict }\nmid    : { date: date, campaigns: dict }\nlatest : { date: date, campaigns: dict }"]

    TC1 --> CLASSIFY

    %% ── NODE 2 — CLASSIFY & PROCESS ────────────────────────────────────────────
    subgraph CLASSIFY["⚙️  ClassifyAndProcessNode"]
        C1["union of all campaign names\nacross oldest ∪ mid ∪ latest\n(handles campaigns absent on some dates)"]
        C1 --> C2{"classify\neach campaign"}
        C2 -- "'weight' in name.lower()" --> CWL["→ segment = WL"]
        C2 -- "otherwise" --> CNWL["→ segment = NON_WL"]
        CWL & CNWL --> C3
        C3["build CampaignDayMetrics × 3 dates\n──────────────────────────────\ncost_usd     · conversions\nclicks       · impressions\nCTR  =  clicks ÷ impressions\nCVR  =  conversions ÷ clicks\nCPA  =  cost ÷ conversions\navg_cpc  (raw from CSV)\n── all nullable when denominator = 0 ──"]
        C3 --> C4["compute WoW deltas per metric\n──────────────────────────────\nWoW 1  oldest → mid\nWoW 2  mid → latest\nΔ = ( abs_delta ,  pct_delta )\npct = None  when baseline = 0"]
        C4 --> C5["build SegmentAggregate  ×2  (WL & NON_WL)\n──────────────────────────────\ntotal spend / conv / clicks / impressions\nblended CPA  =  Σcost ÷ Σconv\navg CVR      =  Σconv ÷ Σclicks\navg CTR      =  Σclicks ÷ Σimpressions\nWoW 1 & WoW 2 computed on aggregates"]
    end

    CLASSIFY --> TC2

    TC2["🗂  TaskContext  ·  after ClassifyAndProcessNode\n──────────────────────────────────────────────────\ndates            : { oldest, mid, latest }  str\nwl_campaigns     : list[ ProcessedCampaign ]\nnonwl_campaigns  : list[ ProcessedCampaign ]\nwl_aggregates    : SegmentAggregate\nnonwl_aggregates : SegmentAggregate"]

    TC2 --> WL_NODE

    %% ── NODE 3 — GENERATE WL REPORT ────────────────────────────────────────────
    subgraph WL_NODE["🤖  GenerateWLReportNode  (AgentNode)"]
        W1["_format_prompt()\n─────────────────\nSEGMENT header + date labels\n\nSEGMENT AGGREGATES block\n  spend · conv · CPA · CVR · CTR\n  impressions · clicks\n  per date: oldest / mid / latest\n  WoW 1 Δ  &  WoW 2 Δ\n\nCAMPAIGNS block  × N campaigns\n  same metrics per date\n  + daily budget · WoW 1 Δ · WoW 2 Δ"]
        W2["load system prompt\nPromptManager.get_prompt()\n→ open  prompts/report_generation.j2\n→ strip YAML frontmatter  (--- ... ---)\n→ Jinja2 render  { cpa_target }"]
        W1 --> W3
        W2 --> W3
        W3["agent.run( user_prompt )\n─────────────────\nmodel    : claude-sonnet-4-6\nprovider : Anthropic\noutput   : str"]
        W3 --> W4["result.output  →  report_markdown\n─────────────────\n§1 Executive Summary\n   narrative + Key Metrics table\n   3 dates × 7 metrics + WoW 1/2 Δ\n§2 Campaign Breakdown\n   per-campaign table\n   CPA ⚠️  flag if CPA > $target\n§3 PPP Analysis  (AI-generated)\n   Progress · Problems · Priorities"]
    end

    WL_NODE --> TC3WL
    TC3WL["🗂  TaskContext  +\nGenerateWLReportNode.report_markdown  : str"] --> NWL_NODE

    %% ── NODE 4 — GENERATE NON-WL REPORT ────────────────────────────────────────
    subgraph NWL_NODE["🤖  GenerateNonWLReportNode  (AgentNode)"]
        N1["_format_prompt()\n─────────────────\nsame structure as WL node\nuses  nonwl_campaigns\n      nonwl_aggregates"]
        N2["load system prompt\nPromptManager.get_prompt()\n→ open  prompts/report_generation.j2\n→ strip YAML frontmatter  (--- ... ---)\n→ Jinja2 render  { cpa_target }"]
        N1 --> N3
        N2 --> N3
        N3["agent.run( user_prompt )\n─────────────────\nmodel    : claude-sonnet-4-6\nprovider : Anthropic\noutput   : str"]
        N3 --> N4["result.output  →  report_markdown\n─────────────────\n§1 Executive Summary\n§2 Campaign Breakdown\n§3 PPP Analysis  (AI-generated)"]
    end

    subgraph ANTHROPIC["☁️  Anthropic API"]
        CL["claude-sonnet-4-6"]
    end

    W3 <--> CL
    N3 <--> CL

    NWL_NODE --> TC3

    TC3["🗂  TaskContext  +\nGenerateNonWLReportNode.report_markdown  : str"]

    TC3 --> WRITE

    %% ── NODE 5 — WRITE REPORTS ──────────────────────────────────────────────────
    subgraph WRITE["💾  WriteReportsNode"]
        WR1["mkdir  app/reports/  (if not exists)"]
        WR2["read  latest_date\nfrom ClassifyAndProcessNode.dates.latest"]
        WR1 & WR2 --> WR3["write  report_wl_{date}.md\n  ← GenerateWLReportNode.report_markdown\nwrite  report_nonwl_{date}.md\n  ← GenerateNonWLReportNode.report_markdown"]
        WR3 --> WR4["print file paths to stdout\nstore paths in TaskContext"]
    end

    WRITE --> OUT1
    WRITE --> OUT2

    OUT1[/"📄  app/reports/report_wl_{date}.md"/]
    OUT2[/"📄  app/reports/report_nonwl_{date}.md"/]

    %% ── STYLES ──────────────────────────────────────────────────────────────────
    style CLI       fill:#f5f5f5,stroke:#888,color:#111
    style LOAD      fill:#fff8e6,stroke:#e6a817,color:#111
    style CLASSIFY  fill:#fff8e6,stroke:#e6a817,color:#111
    style WL_NODE   fill:#eaf7ea,stroke:#2e9e2e,color:#111
    style NWL_NODE  fill:#eaf7ea,stroke:#2e9e2e,color:#111
    style ANTHROPIC fill:#fceaea,stroke:#d94f4f,color:#111
    style WRITE     fill:#eeebff,stroke:#7c4dff,color:#111

    style EVT    fill:#ddeeff,stroke:#4a90d9,color:#111
    style TC1    fill:#ddeeff,stroke:#4a90d9,color:#111
    style TC2    fill:#ddeeff,stroke:#4a90d9,color:#111
    style TC3WL  fill:#ddeeff,stroke:#4a90d9,color:#111
    style TC3    fill:#ddeeff,stroke:#4a90d9,color:#111
    style OUT1   fill:#e8ffe8,stroke:#2e9e2e,color:#111
    style OUT2   fill:#e8ffe8,stroke:#2e9e2e,color:#111
    style L3X    fill:#ffeaea,stroke:#d94f4f,color:#111
```

---

## Node Reference

| Node | Type | Input | Output |
|---|---|---|---|
| `LoadCSVDataNode` | `Node` | `GoogleAdsReportEvent` (data_dir, files) | `{ oldest, mid, latest }` with date + campaign rows |
| `ClassifyAndProcessNode` | `Node` | Raw campaign dicts × 3 dates | `ProcessedCampaign[]` per segment, `SegmentAggregate` × 2, dates |
| `GenerateWLReportNode` | `AgentNode` | WL campaigns + aggregates + dates | `report_markdown: str` |
| `GenerateNonWLReportNode` | `AgentNode` | Non-WL campaigns + aggregates + dates | `report_markdown: str` |
| `WriteReportsNode` | `Node` | Both report markdown strings | Written `.md` files + paths stored in TaskContext |

## Data Models

```
CampaignDayMetrics        WoWDeltas                  ProcessedCampaign
─────────────────         ─────────────────          ─────────────────────────
cost_usd    : float       cost_usd     : Delta       name             : str
conversions : float       conversions  : Delta       segment          : WL | NON_WL
clicks      : int         clicks       : Delta       daily_budget_usd : float
impressions : int         impressions  : Delta       date_oldest      : CampaignDayMetrics
ctr         : float?      ctr          : Delta       date_mid         : CampaignDayMetrics
cvr         : float?      cvr          : Delta       date_latest      : CampaignDayMetrics
cpa_usd     : float?      cpa_usd      : Delta       wow1             : WoWDeltas
avg_cpc     : float?                                 wow2             : WoWDeltas

Delta = ( abs_delta: float | None,  pct_delta: float | None )
```

## Running the Pipeline

```bash
# Auto-select 3 most recent CSVs from app/data/
python app/run_report.py

# Specify exact files (e.g. Thursday data)
python app/run_report.py --files app/data/cr_09_04.csv app/data/cr_16_04.csv app/data/cr_23_04.csv
```

## Report Structure

Each generated report contains:

1. **Executive Summary** — narrative overview + key metrics table across 3 dates with WoW 1 and WoW 2 deltas
2. **Campaign Breakdown** — per-campaign metrics table; CPA flagged with ⚠️ where it exceeds the target
3. **PPP Analysis** *(AI-generated)* — Progress, Problems, and Priorities with specific, actionable recommendations

> ⚠️ All AI-generated recommendations require human review. No automated actions are taken.
