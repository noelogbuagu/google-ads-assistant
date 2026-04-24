# Product Requirements Document: Google Ads Assistant

**Version:** 1.0  
**Date:** 2026-04-24  
**Status:** Approved  
**Phase:** PoC (Hackday MVP)

---

## 1. Product Overview

The Google Ads Assistant is a CLI tool that connects to the Google Ads API, retrieves yesterday's campaign performance data for a given account, and generates two AI-narrated performance reports — one for Weight Loss (WL) campaigns and one for Non-Weight Loss (Non-WL) campaigns. Each report includes aggregated metrics, a per-campaign breakdown, and AI-generated recommendations, output as a Markdown file.

**Core value proposition:** Replace ~1 hour of daily manual reporting with a single terminal command that produces ready-to-read, insight-rich reports in seconds.

---

## 2. User Personas

### Primary Persona — Marketing Manager (KAP)

| Attribute | Detail |
|---|---|
| Role | Marketing Manager at KAP |
| Technical level | Non-technical; consumes reports, does not operate the tool |
| Goal | Understand daily campaign performance quickly and know what actions to take |
| Pain point | Spends ~1hr/day manually logging into Google Ads, comparing numbers, and writing up insights |
| Success | Receives a clear, accurate, actionable report with no manual effort |

### Secondary Persona — Developer / Operator

| Attribute | Detail |
|---|---|
| Role | Solo developer running and maintaining the tool |
| Technical level | High |
| Goal | Run the tool reliably with a single command; extend it post-PoC |
| Pain point | Currently no automated pipeline exists |
| Success | Tool runs end-to-end without errors; report is accurate and well-structured |

---

## 3. User Journey (PoC)

```
Developer runs CLI command
        ↓
Tool authenticates with Google Ads API
        ↓
Retrieves yesterday's campaign data for KAP account
        ↓
Segments campaigns → WL (name contains "weight") | Non-WL (all others)
        ↓
Calculates metrics per campaign + WoW delta (vs same calendar day last week)
        ↓
Aggregates metrics per segment
        ↓
Sends aggregated + per-campaign data to Claude API
        ↓
Claude generates narrative summary + recommendations per segment
        ↓
Outputs 2 Markdown files (WL report + Non-WL report)
        ↓
Developer shares reports with marketing manager
```

---

## 4. Functional Requirements

### FR-01: Google Ads API Connection

- **FR-01.1** The system must authenticate with the Google Ads API using a developer token and OAuth2 credentials
- **FR-01.2** Authentication credentials must be loaded from environment variables or a local config file (no hardcoded secrets)
- **FR-01.3** On authentication failure, the system must halt and display a clear error message

### FR-02: Data Retrieval

- **FR-02.1** The system must retrieve campaign-level data for a configurable Google Ads account (Customer ID)
- **FR-02.2** The primary date range is **yesterday** (the full previous calendar day)
- **FR-02.3** The comparison date range is **the same calendar day one week prior** (e.g. if yesterday was Wednesday, compare to last Wednesday)
- **FR-02.4** The system must retrieve the following metrics per campaign, for both date ranges:
  - Spend (cost)
  - Conversions
  - CPA (Cost per Conversion = spend / conversions)
  - Conversion Rate (CVR = conversions / clicks)
  - Impression Share
  - CTR (Click-Through Rate)
  - Impressions
  - Clicks
- **FR-02.5** The system must retrieve the campaign's configured **daily budget**
- **FR-02.6** The system must retrieve **all-time (lifetime) average** impressions per campaign to serve as a performance baseline
- **FR-02.7** If a campaign has zero conversions on a given day, CPA and CVR must be reported as `N/A` (no division by zero)

### FR-03: Campaign Segmentation

- **FR-03.1** Campaigns must be segmented into two groups:
  - **WL (Weight Loss):** campaign name contains the word "weight" (case-insensitive)
  - **Non-WL:** all other campaigns
- **FR-03.2** Segmentation must be applied before any aggregation or reporting

### FR-04: Metric Processing

- **FR-04.1** For each segment, compute **aggregate totals/averages** across all campaigns in the group:
  - Total Spend
  - Total Conversions
  - Blended CPA (total spend / total conversions)
  - Average CVR
  - Average CTR
  - Total Impressions
  - Average Impression Share
- **FR-04.2** For each metric, compute a **WoW delta** (absolute and percentage change vs same day last week)
- **FR-04.3** WoW delta must be displayed with directional indicator (↑ / ↓) and colour-coded context in the narrative (positive/negative framing depends on metric: lower CPA is good, higher conversions is good)

### FR-05: Report Generation

- **FR-05.1** The system must generate **two separate Markdown reports**:
  - `report_wl_YYYY-MM-DD.md`
  - `report_nonwl_YYYY-MM-DD.md`
  - Where `YYYY-MM-DD` is yesterday's date
- **FR-05.2** Both reports must follow the same structure (see Section 6)
- **FR-05.3** Reports must be written to a `/reports` output directory
- **FR-05.4** The system must pass structured data (aggregates + per-campaign breakdown + WoW deltas) to the Claude API to generate the narrative sections
- **FR-05.5** AI-generated content must be clearly labelled as AI-generated within the report
- **FR-05.6** All recommendations must be framed as suggestions, never as automated actions

### FR-06: CLI Interface

- **FR-06.1** The tool must be invocable with a single terminal command (e.g. `python main.py`)
- **FR-06.2** The tool must print progress to stdout (e.g. "Fetching data...", "Generating WL report...", "Done.")
- **FR-06.3** On completion, the tool must print the paths of the generated report files
- **FR-06.4** On any fatal error, the tool must print a clear, human-readable error message and exit with a non-zero code

---

## 5. Non-Functional Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| NFR-01 | **Reliability** | Tool completes successfully on valid API credentials and account access |
| NFR-02 | **Security** | No credentials hardcoded; loaded from env vars or `.env` file |
| NFR-03 | **Readability** | Generated Markdown renders cleanly in any standard Markdown viewer |
| NFR-04 | **Accuracy** | Metrics match what is visible in the Google Ads UI for the same date range |
| NFR-05 | **Maintainability** | Account ID and date range configurable without code changes |
| NFR-06 | **Portability** | Runs on Python 3.10+ with dependencies installable via pip |

---

## 6. Report Structure

Each report (WL and Non-WL) follows this structure:

```
# [WL / Non-WL] Campaign Performance Report — YYYY-MM-DD

---

## Executive Summary

[AI-generated brief narrative: 2-4 sentences covering overall performance, 
standout trends, and the most important signal for the day]

### Key Metrics (vs same day last week)

| Metric              | Yesterday | Last Week | Change     |
|---------------------|-----------|-----------|------------|
| Total Spend         | $X        | $X        | ↑/↓ X%    |
| Total Conversions   | X         | X         | ↑/↓ X%    |
| Blended CPA         | $X        | $X        | ↑/↓ X%    |
| Average CVR         | X%        | X%        | ↑/↓ X%    |
| Average CTR         | X%        | X%        | ↑/↓ X%    |
| Total Impressions   | X         | X         | ↑/↓ X%    |
| Avg Impression Share| X%        | X%        | ↑/↓ X%    |

---

## Campaign Breakdown

### [Campaign Name]

| Metric           | Yesterday | Last Week | Change   |
|------------------|-----------|-----------|----------|
| Spend            | $X        | $X        | ↑/↓ X%  |
| Conversions      | X         | X         | ↑/↓ X%  |
| CPA              | $X        | $X        | ↑/↓ X%  |
| CVR              | X%        | X%        | ↑/↓ X%  |
| CTR              | X%        | X%        | ↑/↓ X%  |
| Impressions      | X         | X         | ↑/↓ X%  |
| Impression Share | X%        | X%        | ↑/↓ X%  |
| Daily Budget     | $X        |           |          |
| All-time Avg Imp | X         |           |          |

[Repeat for each campaign in segment]

---

## AI Recommendations

> ⚠️ The following recommendations are AI-generated suggestions. 
> No automated actions have been taken. All decisions require human review.

[AI-generated narrative: specific, actionable recommendations based on 
the data above. References campaign names and specific metrics.]
```

---

## 7. Data Requirements

### Data Objects

**Campaign**
- `id`: string
- `name`: string
- `segment`: enum (WL | NON_WL)
- `daily_budget_micros`: integer (converted to USD)
- `status`: enum (ENABLED | PAUSED | REMOVED)

**CampaignMetrics** (per date range)
- `date`: date
- `cost_micros`: integer (converted to USD)
- `conversions`: float
- `clicks`: integer
- `impressions`: integer
- `impression_share`: float (0–1)
- `ctr`: float (derived)
- `cvr`: float (derived, nullable)
- `cpa`: float (derived, nullable)

**SegmentAggregate**
- `segment`: enum
- `metrics_yesterday`: CampaignMetrics
- `metrics_last_week`: CampaignMetrics
- `wow_deltas`: dict of metric → (absolute_change, pct_change)

### Business Rules

- CPA = spend / conversions (null if conversions = 0)
- CVR = conversions / clicks (null if clicks = 0)
- WoW delta % = (yesterday - last_week) / last_week × 100 (null if last_week = 0)
- WL segment = campaign name contains "weight" (case-insensitive match)
- CPA target for KAP = $500 (used as context in AI prompt)
- Google Ads API returns monetary values in micros (÷ 1,000,000 for USD)

---

## 8. Interface Requirements

### CLI

```bash
python main.py [--account-id CUSTOMER_ID] [--date YYYY-MM-DD]
```

- `--account-id`: optional override; defaults to value in config/env
- `--date`: optional override for "yesterday"; defaults to `today - 1 day`

### External APIs

| API | Purpose | Auth Method |
|---|---|---|
| Google Ads API | Campaign data retrieval | OAuth2 + Developer Token |
| Anthropic Claude API | Report narrative generation | API Key |

### Output

- 2 Markdown files written to `./reports/`
- Progress and file paths printed to stdout

---

## 9. Constraints & Assumptions

### Constraints
- Google Ads API developer token must be available before build
- Claude API key must be configured in environment
- Campaign segmentation relies on "weight" appearing in campaign name — if naming convention changes, segmentation breaks
- PoC: no scheduling, no email, no Google Docs, no Google Analytics

### Assumptions
- KAP account has 13 active campaigns
- "weight" reliably distinguishes WL from Non-WL campaigns (confirmed by user)
- Historical average = all-time lifetime average impressions from campaign start date to today
- `ENABLED` campaigns only are included in reports (PAUSED/REMOVED excluded unless explicitly configured)
- All-time average requires a separate API call with date range from campaign start to yesterday

---

## 10. Prioritised Requirements (MoSCoW)

### Must Have (PoC blockers)
- Google Ads API authentication (FR-01)
- Yesterday's + last-week's campaign data retrieval (FR-02)
- WL / Non-WL segmentation (FR-03)
- Metric calculation + WoW deltas (FR-04)
- Two Markdown reports with correct structure (FR-05, FR-06)
- AI-generated executive summary and recommendations (FR-05.4)

### Should Have (post-PoC)
- `--date` and `--account-id` CLI flags (FR-06)
- Lifetime average impressions baseline (FR-02.6)
- Graceful handling of zero-conversion days (FR-02.7)

### Won't Have (this phase)
- Email delivery
- Google Docs output
- Scheduled execution
- Google Analytics integration
- Anomaly detection with defined thresholds
- Multi-account support

---

## 11. Acceptance Criteria

| ID | Criterion |
|---|---|
| AC-01 | Running `python main.py` produces two `.md` files in `./reports/` |
| AC-02 | Each report contains an Executive Summary, Campaign Breakdown, and AI Recommendations section |
| AC-03 | Metrics in the report match the Google Ads UI for the same date and account |
| AC-04 | WL report contains only campaigns with "weight" in the name; Non-WL report contains the rest |
| AC-05 | WoW delta is calculated against the same calendar day one week prior |
| AC-06 | AI Recommendations section contains actionable, campaign-specific suggestions |
| AC-07 | Tool exits with a clear error message if API credentials are invalid or missing |
| AC-08 | No credentials appear in source code or output files |

---

## 12. Out of Scope

- Email automation
- Google Docs integration
- Scheduled/cron execution
- Google Analytics data
- Multi-account support
- Anomaly detection with defined numeric thresholds
- Ad-level or keyword-level data
- Dashboard or web UI
