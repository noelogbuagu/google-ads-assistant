# Google Ads Assistant — Hackday Summary
**Date:** 24 April 2026

---

## Original Plan (`gads-assistant-mvp`)

The initial objective was to build a fully automated Google Ads reporting pipeline connected directly to the Google Ads API.

**Planned objectives:**
- Authenticate with the Google Ads API using OAuth2 + a developer token
- Retrieve yesterday's campaign data programmatically for the KAP account
- Segment campaigns into Weight Loss (WL) and Non-WL groups
- Calculate core metrics (Spend, Conversions, CPA, CVR, CTR, Impressions) with week-over-week comparisons
- Generate two AI-narrated Markdown reports via Claude — one per segment
- Output reports with an Executive Summary, Campaign Breakdown, and AI Recommendations (PPP)

---

## Blocker

- **No access to a Google Ads manager account** — a manager account is required to generate a developer token, which is the entry point for any Google Ads API integration
- Without the developer token, the originally planned API-based data retrieval flow is **currently blocked and redundant**
- As a workaround, **campaign reports were exported manually as CSV files** directly from the Google Ads UI and used as the data source for this session
- The API integration path remains intact in the architecture and can be activated once manager account access is granted

---

## What Was Built (`gads-assistant-mvp` — current branch)

**Objectives:**
- Pivot the data ingestion layer from API calls to CSV file parsing
- Build the full end-to-end pipeline on top of the GenAI Launchpad workflow framework
- Deliver two production-quality AI-generated reports from a single CLI command

**Deliverables:**

- **CSV Loader** — parses Google Ads campaign export CSVs, extracts dates from report headers, filters out zero-spend and summary rows
- **Campaign Classifier & Metric Processor** — segments campaigns into WL / Non-WL, computes CPA, CVR, CTR, CPC, and two week-over-week delta comparisons across three dates (oldest → mid → latest)
- **AI Report Generator (WL)** — sends structured WL segment data to Claude and generates a full Markdown report
- **AI Report Generator (Non-WL)** — same pipeline for the Non-WL segment
- **Report Writer** — writes both reports to `app/reports/` as `report_wl_{date}.md` and `report_nonwl_{date}.md`
- **CLI interface** — `python app/run_report.py` with `--data-dir` (auto-pick 3 CSVs) and `--files` (specify exact files) flags
- **Workflow architecture diagram** — documented in `app/WORKFLOW.md` with Mermaid diagram

**Report structure (both WL and Non-WL):**
- Executive Summary with narrative + key metrics table across 3 dates
- Per-campaign breakdown with metrics and WoW 1 / WoW 2 deltas
- CPA target flags (⚠️) where CPA exceeds the $500 threshold
- PPP Analysis (Progress, Problems, Priorities) — AI-generated, labelled as suggestions, no automated actions

**How to run:**
```bash
# Auto-select 3 most recent CSVs from app/data/
python app/run_report.py

# Specify exact files (e.g. Thursday data)
python app/run_report.py --files app/data/cr_09_04.csv app/data/cr_16_04.csv app/data/cr_23_04.csv
```

---

## Future Work

- **Direct Google Ads API integration** — once manager account access is granted, replace the manual CSV download step with automated data retrieval via the Google Ads API; the rest of the pipeline stays unchanged
- **Scheduled execution** — run the pipeline automatically every morning (e.g. 7am trigger) so reports are ready before the working day starts, with no manual steps required
- **Email automation** — automatically send generated reports to the marketing manager as a Google Doc with editor access, removing the need to manually share files
- **Keyword management** — analyse keyword-level performance to flag keywords that should be enabled or disabled based on traffic thresholds, surfaced as recommendations in the report
- **Anomaly detection** — identify and flag statistical anomalies in spend, conversions, or CPA (e.g. sudden drops or spikes) with contextual explanations to help prioritise investigation
- **Marketing targets integration** — connect a shared Google Sheet or Google Doc where the marketing team can input their targets (CPA, CVR, budget) so the automation uses live, team-defined benchmarks for comparison instead of hardcoded values
- **Multi-account support** — extend the pipeline to support multiple Google Ads accounts with similar campaign structures, enabling the tool to scale across clients
