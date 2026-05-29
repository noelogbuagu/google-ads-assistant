# Product Requirements Document: Google Ads Intelligence Assistant

**Version:** 1.0  
**Date:** 2026-05-29  
**Status:** Approved for build  
**Brand:** SOP (UK) — v1

---

## 1. Product Overview

An automated AI assistant that queries Snowflake each morning, computes Google Ads campaign performance against a rolling 7-day baseline, detects anomalies, and delivers a structured narrative report to the SOP marketing team's Microsoft Teams channel before 8:30 AM BST.

**Core value**: Replaces a ~1-hour daily manual reporting ritual with a 5-minute read that surfaces what matters, in the order it matters.

---

## 2. User Personas

### Persona 1 — Marketing Manager (Primary Actor)

- **Role**: Owns the SOP Google Ads account day-to-day
- **Goal**: Know within 5 minutes what needs attention today and where to focus optimization time
- **Pain**: Spends ~1hr assembling data before any thinking happens; anomalies slip through because manual scanning is imperfect
- **Technical level**: Fluent in Google Ads UI and GA; not a data engineer
- **Acceptance bar**: Reads the report, knows what to work on, does **not** open Google Ads to verify the numbers

### Persona 2 — Head of Growth (Sponsor / Visibility Reader)

- **Role**: Business owner of acquisition performance across SOP
- **Goal**: Open Teams in the morning and immediately know if Google Ads is healthy — without asking anyone
- **Pain**: Currently dependent on manager to proactively share updates; no consistent visibility
- **Acceptance bar**: Can forward the report to their own leadership without editing it

### Persona 3 — Performance Marketers / Team Members (Awareness Readers)

- **Role**: Adjacent team members (content, product, other performance channels)
- **Goal**: Stay informed on acquisition performance without logging into any tool
- **Acceptance bar**: Read the headline and "What Stands Out" in 60 seconds

---

## 3. User Journeys

### Journey 1 — Daily Triage (Marketing Manager)

```
7:30 AM UTC  Workflow triggers automatically
             ↓
             Snowflake query runs (D-1 completeness check + main query)
             ↓
             Processing node computes deltas, flags anomalies
             ↓
             AI node generates narrative
             ↓
8:00 AM UTC  Report appears in Teams channel
             ↓
8:30 AM BST  Manager opens Teams, reads headline (15 sec)
             → Scans anomaly flags in "What Stands Out" (60 sec)
             → Checks campaign breakdown for affected campaigns (90 sec)
             → Reads recommendations (60 sec)
             → Knows exactly where to go in Google Ads
```

### Journey 2 — Staleness Fallback

```
D-1 row count < 400 rows (data incomplete)
  ↓
Node falls back to D-2 as reporting date
  ↓
Report header clearly states: "⚠️ D-1 data incomplete — reporting on [D-2 date]"
  ↓
Report delivers as normal with D-2 data
```

### Journey 3 — Pipeline Failure

```
Snowflake query fails / workflow errors
  ↓
Error is logged to workflow task context
  ↓
Teams message sent: "⚠️ SOP Google Ads report failed to generate. Check pipeline logs."
  ↓
Manager knows to check Google Ads manually — same outcome as before automation
```

---

## 4. Functional Requirements

### FR-1: Snowflake Query Node

**FR-1.1 — Completeness check**
- Before the main query, execute:
  ```sql
  SELECT COUNT(*) AS row_count
  FROM DWH.MARKETING.ACQUISITION_MASTER
  WHERE DATE = CURRENT_DATE - 1
    AND BRAND = 'sop'
    AND SOURCE = 'Google'
  ```
- If `row_count >= 400`: set `reporting_date = CURRENT_DATE - 1`
- If `row_count < 400`: set `reporting_date = CURRENT_DATE - 2`, set `data_lag_flag = True`

**FR-1.2 — Main query**
- Fetch data from `DWH.MARKETING.ACQUISITION_MASTER` with filters:
  - `BRAND = 'sop'`
  - `SOURCE = 'Google'`
  - `ATTRIBUTION = 'Last Click Attribution'`
  - `IS_CAMPAIGN = 1`
  - `DATE BETWEEN (reporting_date - 7) AND reporting_date`
- Aggregate by `DATE, CAMPAIGN, CHANNEL`
- Use `SUM()` + `GROUP BY` to handle minor grain duplicates
- Return two result sets:
  - **reporting_day**: rows where `DATE = reporting_date`
  - **trailing_window**: rows where `DATE BETWEEN (reporting_date - 7) AND (reporting_date - 1)`

**FR-1.3 — Columns to fetch**

| Column | Purpose |
|---|---|
| DATE, CAMPAIGN, CHANNEL | Dimensions |
| COST | Spend (GBP) |
| IMPRESSIONS, CLICKS, CTR, CPC | Ad platform Tier 1 |
| NEW_ORDERS | New customer conversions |
| ORDERS | Total conversions |
| GROSS_REVENUE, NEW_GROSS_REVENUE | Revenue |
| GROSS_PROFIT, NEW_GROSS_PROFIT | Profit |
| SESSIONS, NEW_SESSIONS | Click → site visit |
| STARTED_ASSESSMENT, NEW_STARTED_ASSESSMENT | Funnel stage 1 |
| SUBMITTED_ASSESSMENT, NEW_SUBMITTED_ASSESSMENT | Funnel stage 2 |
| BASKET_PAGE, NEW_BASKET_PAGE | Funnel stage 3 |
| PURCHASED, NEW_PURCHASED | Funnel stage 4 |
| HAS_SPEND | Spend flag |

---

### FR-2: Data Processing Node

**FR-2.1 — Trailing average computation**
- For each campaign: compute 7-day average of each Tier 1 metric from the trailing window
- Trailing window = `reporting_date - 7` to `reporting_date - 1` (7 days, excluding reporting date)

**FR-2.2 — Delta computation**
- For each campaign and each metric:
  - `delta_pct = (reporting_day_value - trailing_avg) / trailing_avg × 100`
  - Direction indicator: `▲` if positive (worse for CPA/CPC/CPM), `▼` if negative (worse for spend/conversions/impressions), `→` if within ±5%
  - Note: direction indicator semantics are metric-dependent (see FR-2.4)

**FR-2.3 — Account-level rollup**
- Sum all campaign values for reporting_day → account snapshot
- Sum all campaign trailing averages → account trailing snapshot
- Compute account-level deltas same as per-campaign

**FR-2.4 — Anomaly detection**
- Flag a campaign as anomalous if ANY of the following are true:
  - `|CPA delta| > 30%` vs trailing avg (high or low)
  - `|COST delta| > 50%` vs trailing avg
  - `|IMPRESSIONS delta| > 40%` vs trailing avg (delivery issue signal)
  - `|NEW_ORDERS delta| > 40%` vs trailing avg
  - `COST > 0` yesterday but `NEW_ORDERS = 0` (spend with zero conversions)
  - Campaign had spend in trailing window but `COST = 0` yesterday (sudden stop)
- Anomaly severity:
  - **Critical**: CPA > 2× trailing avg, or complete delivery stop on high-spend campaign
  - **Warning**: Any other threshold breach
- Suppress anomalies where trailing 7d total COST < £10 (noise filter)

**FR-2.5 — Campaign inclusion / exclusion**
- Include: any campaign where `SUM(COST) >= £10` in trailing 7-day window
- Include: campaigns with spend yesterday even if below threshold
- Exclude: campaigns with `SUM(COST) < £10` in both reporting day and trailing window
- Sort order: reporting_day COST descending; campaigns with zero reporting_day spend sorted to bottom

**FR-2.6 — Computed metrics**
- `CPA = COST / NEW_ORDERS` (new customer CPA; suppress if NEW_ORDERS = 0)
- `ROAS = GROSS_REVENUE / COST` (suppress if COST = 0)
- `CTR` — use directly from table
- `CPC` — use directly from table
- Funnel rates (reporting day only):
  - `session_to_assessment_rate = STARTED_ASSESSMENT / SESSIONS`
  - `assessment_completion_rate = SUBMITTED_ASSESSMENT / STARTED_ASSESSMENT`
  - `assessment_to_basket_rate = BASKET_PAGE / SUBMITTED_ASSESSMENT`
  - `basket_to_purchase_rate = PURCHASED / BASKET_PAGE`
  - `click_to_purchase_rate = PURCHASED / CLICKS`

---

### FR-3: AI Narrative Generation Node

**FR-3.1 — Input to AI**
The node passes to the LLM:
- Account-level snapshot (reporting day vs. trailing avg, all deltas)
- Per-campaign breakdown (all campaigns above threshold, with deltas)
- Anomaly list with severity, metric, and magnitude
- Funnel rates for reporting day
- `data_lag_flag` and `reporting_date`
- Current date context

**FR-3.2 — Output sections**

The AI generates a single markdown document with these sections in order:

1. **Report header** (templated, not AI-generated):
   ```
   📊 SOP Google Ads — Daily Report | {weekday} {date}
   Data source: Snowflake ACQUISITION_MASTER | Attribution: Last Click | {note if data_lag_flag}
   ```

2. **Headline** (AI-generated, 2–3 sentences):
   - Must state: total spend, direction vs. baseline, CPA direction, and the single biggest story
   - Example: *"Yesterday's spend was £4,280 (flat vs. 7d avg), but conversions dropped 18% to 42, pushing CPA to £102 (+15%). Weight Loss Search drove the decline — impressions fell 35%, suggesting a delivery issue."*
   - Must NOT be generic (e.g. "Performance was mixed" is rejected)

3. **Account Snapshot** (templated table):
   ```markdown
   | Metric          | Yesterday | 7d Avg | Δ      |
   |-----------------|-----------|--------|--------|
   | Spend           | £X,XXX    | £X,XXX | ▲ +X%  |
   | Conversions (LC)| XX        | XX     | ▼ -X%  |
   | CPA             | £XX       | £XX    | ▲ +X%  |
   | ROAS            | X.XX      | X.XX   | ▼ -X%  |
   | Impressions     | XXX,XXX   | XXX,XXX| → 0%   |
   | Clicks          | X,XXX     | X,XXX  | ▼ -X%  |
   | CTR             | X.X%      | X.X%   | → 0%   |
   | CPC             | £X.XX     | £X.XX  | ▲ +X%  |
   ```

4. **Campaign Breakdown** (templated table, sorted by spend):
   ```markdown
   | Campaign | Spend | Δ | Conv | Δ | CPA | Δ | ROAS | Δ |
   |----------|-------|---|------|---|-----|---|------|---|
   ...
   ```
   - Anomalous campaigns marked with 🔴 (critical) or 🟡 (warning)
   - Paused / zero-spend campaigns grouped at bottom with "(no spend)" note

5. **Funnel Overview** (templated table, reporting day only):
   ```markdown
   | Stage                   | Volume | Rate vs Sessions |
   |-------------------------|--------|-----------------|
   | Sessions                | X,XXX  | —               |
   | Started Assessment      | XXX    | X.X%            |
   | Submitted Assessment    | XXX    | X.X%            |
   | Basket Page             | XXX    | X.X%            |
   | Purchased               | XXX    | X.X%            |
   ```

6. **What Stands Out** (AI-generated, 3–5 paragraphs):
   - Must reference specific campaign names and specific numbers
   - Must explain anomalies in context (e.g. "spend fell 30% but CPA is still above target — this isn't a recovery")
   - Must distinguish between signal and noise
   - Must NOT include generic filler ("Overall performance was mixed today")
   - Each paragraph covers one story (campaign, pattern, or structural observation)

7. **Recommendations** (AI-generated, 3–5 bullets):
   - Each recommendation is specific and actionable (not "monitor performance")
   - References the specific campaign and metric driving the recommendation
   - Phrased as observations + suggested action (not commands)
   - Example: *"WL Search impressions dropped 35% — check campaign status, budget cap, and Quality Score in Google Ads before assuming audience fatigue."*

**FR-3.3 — Quality constraints**
- AI must not make claims about medical efficacy of advertised products
- AI must not recommend changes that require Google Ads API access (V1 is read-only)
- AI must flag uncertainty where data is ambiguous (e.g. "this may reflect normal Monday seasonality")
- Total output must stay under 25,000 characters (Teams 28KB limit with buffer)

---

### FR-4: Teams Delivery Node

**FR-4.1** — POST the markdown report to the SOP marketing Teams channel via incoming webhook URL (configured as environment variable `TEAMS_SOP_WEBHOOK_URL`)

**FR-4.2** — If report length exceeds 24,000 characters: split into two messages
- Message 1: Header + Headline + Account Snapshot + Campaign Breakdown
- Message 2: Funnel Overview + What Stands Out + Recommendations

**FR-4.3** — On pipeline failure: send a minimal alert message:
```
⚠️ SOP Google Ads daily report failed to generate.
Time: {timestamp} UTC
Error: {error_summary}
Action: Check pipeline logs or run manual report.
```

**FR-4.4** — For hackathon demo: console/stdout print is acceptable in place of Teams POST

---

### FR-5: Scheduling

**FR-5.1** — Workflow triggers automatically, weekdays only (Mon–Fri), at **7:30 AM UTC**

**FR-5.2** — No trigger on UK public holidays (V1: accept this gap; not worth engineering around)

**FR-5.3** — Manual trigger must be possible for testing and catch-up runs (accept an event payload with optional `override_date` parameter)

---

## 5. Non-Functional Requirements

| ID | Requirement | Acceptance Criteria |
|---|---|---|
| NFR-1 | **Delivery time** | Report in Teams before 8:30 AM BST (8:30 AM UTC in summer / 7:30 AM UTC in winter) |
| NFR-2 | **Reliability** | ≥ 99% weekday delivery (max 1 missed report per quarter, excluding infra outages) |
| NFR-3 | **Accuracy** | Numbers match Snowflake source exactly; any variance from Google Ads UI must be documented as known (attribution window, not a bug) |
| NFR-4 | **False positive rate** | Anomaly flags correspond to real issues; < 1 false positive per week in steady state |
| NFR-5 | **Pipeline duration** | Full run (query → narrative → delivery) completes within 10 minutes |
| NFR-6 | **Failure visibility** | Any pipeline failure results in a Teams alert within 5 minutes of failure |
| NFR-7 | **Data labelling** | Every report header includes: data source, attribution model, reporting date, and staleness flag if applicable |
| NFR-8 | **Configurability** | Brand, comparison window, anomaly thresholds, and delivery channel are environment-variable configurable — not hardcoded |

---

## 6. Data Requirements

### Primary Source

| Property | Value |
|---|---|
| Table | `DWH.MARKETING.ACQUISITION_MASTER` |
| Connection | Snowflake service account |
| Grain | DATE × BRAND × REGION × SOURCE × CHANNEL × CAMPAIGN × ATTRIBUTION |
| Dedup strategy | `SUM() + GROUP BY` (minor grain duplicates exist) |

### Query Filters (SOP Google Ads, V1)

```sql
WHERE BRAND = 'sop'
  AND SOURCE = 'Google'
  AND ATTRIBUTION = 'Last Click Attribution'
  AND IS_CAMPAIGN = 1
  AND DATE BETWEEN :trailing_start AND :reporting_date
```

### Date Logic

```
reporting_date = D-1 if COUNT(sop+Google on D-1) >= 400 else D-2
trailing_window = reporting_date - 7  to  reporting_date - 1  (7 days)
```

### Known Data Caveats (document in every report)

1. **Attribution window**: ACQUISITION_MASTER inherits Google Ads account-level attribution (likely 30-day click). Numbers will differ from Google Ads UI if the UI uses a different window.
2. **Conversion definition**: `NEW_ORDERS` = first-time customer orders attributed to this campaign/date. Does not include repeat orders.
3. **Funnel metrics**: Session-scoped (GA4). A session can contain multiple funnel events; rates may exceed 100% in edge cases.
4. **Data lag**: D-1 data settles during the day. Report flags if D-2 fallback is used.

---

## 7. Interface Requirements

### 7.1 Teams Message Format

- Format: **plain markdown** (renders in Teams desktop and mobile)
- Max length: 24,000 characters (split into 2 messages if exceeded)
- Currency: **£** throughout (no conversion, data is natively GBP for SOP)
- Numbers: round to 2 decimal places for rates/ratios; integers for counts; £X,XXX for spend

### 7.2 Report Configuration (environment variables)

| Variable | Description | Default |
|---|---|---|
| `BRAND` | Brand filter | `sop` |
| `SOURCE_FILTER` | Source filter | `Google` |
| `ATTRIBUTION_MODEL` | Attribution filter | `Last Click Attribution` |
| `COMPLETENESS_THRESHOLD` | Min rows for D-1 acceptance | `400` |
| `MIN_SPEND_THRESHOLD_GBP` | Min 7d spend for campaign inclusion | `10.0` |
| `ANOMALY_CPA_THRESHOLD` | CPA deviation % to flag | `0.30` |
| `ANOMALY_SPEND_THRESHOLD` | Spend deviation % to flag | `0.50` |
| `ANOMALY_IMPRESSIONS_THRESHOLD` | Impression deviation % to flag | `0.40` |
| `ANOMALY_ORDERS_THRESHOLD` | Orders deviation % to flag | `0.40` |
| `TEAMS_WEBHOOK_URL` | Teams incoming webhook | (required) |
| `REPORT_TIMEZONE_LABEL` | Display timezone | `BST` |

### 7.3 Manual Trigger Payload

```json
{
  "workflow_type": "google_ads_report",
  "data": {
    "brand": "sop",
    "override_date": "2026-05-27"
  }
}
```

`override_date` is optional. If omitted, the standard D-1/D-2 logic applies.

---

## 8. Constraints and Assumptions

### Constraints

| Constraint | Detail |
|---|---|
| No Google Ads API | All data sourced from Snowflake only |
| Read-only | V1 makes no changes to campaigns, bids, or budgets |
| Google Ads only | V1 excludes Meta (`SOURCE = 'Meta'`) |
| Last Click only | V1 uses Last Click Attribution as primary; First Click not surfaced in report |
| SOP only | V1 scoped to `BRAND = 'sop'`; KAP and SOD follow same pattern |
| Solo build | One developer, one data engineer (same person) |
| Hackathon timeline | Core pipeline (nodes 1–3) demo-ready by 4 PM UTC 2026-05-29 |

### Assumptions

| ID | Assumption |
|---|---|
| A-1 | D-1 data is complete (≥400 rows) on most weekdays; D-2 fallback is rare |
| A-2 | Snowflake service account has SELECT access to `DWH.MARKETING.ACQUISITION_MASTER` |
| A-3 | Teams incoming webhook will be configured before production deployment |
| A-4 | Attribution window is 30-day click (Google Ads default); any variance from UI is known and documented, not a bug |
| A-5 | Campaign names in ACQUISITION_MASTER are normalised and stable (no daily renaming) |
| A-6 | £10 trailing 7d threshold correctly filters test/noise campaigns without excluding legitimate low-spend campaigns |

---

## 9. Acceptance Criteria

### Node 1 — Snowflake Query Node

- [ ] Completeness check runs before main query
- [ ] `reporting_date` set correctly based on row count threshold
- [ ] Main query returns correct columns for both reporting_day and trailing_window
- [ ] Data aggregated correctly (no double-counting from grain duplicates)
- [ ] `data_lag_flag` set and propagated when D-2 fallback is used

### Node 2 — Data Processing Node

- [ ] 7-day trailing average computed correctly per campaign per metric
- [ ] Deltas computed correctly as percentage change
- [ ] Direction indicators (▲▼→) applied correctly with metric-appropriate semantics
- [ ] Anomaly flags triggered at correct thresholds
- [ ] Campaign list filtered correctly (≥£10 trailing spend)
- [ ] Campaigns sorted: spend DESC, zero-spend at bottom
- [ ] Account-level rollup matches sum of campaign-level values
- [ ] Computed metrics (CPA, ROAS, funnel rates) handle zero-denominator safely

### Node 3 — AI Narrative Node

- [ ] All 7 report sections present and correctly formatted
- [ ] Headline references specific numbers and the biggest single story
- [ ] "What Stands Out" references specific campaign names and figures (not generic)
- [ ] Recommendations are actionable and campaign-specific
- [ ] Report length within 24,000 characters
- [ ] Data lag flag surfaced in header when applicable
- [ ] No medical efficacy claims in narrative

### Node 4 — Teams Delivery Node

- [ ] Message posts successfully to configured webhook
- [ ] Split logic triggers correctly if length > 24,000 characters
- [ ] Failure alert sends if pipeline errors
- [ ] Console fallback works for demo

### End-to-End

- [ ] Full pipeline completes within 10 minutes
- [ ] Report arrives in Teams before 8:30 AM BST
- [ ] Numbers in report match Snowflake source query output exactly
- [ ] Manager reads report in ≤5 minutes and identifies what to work on

---

## 10. Prioritised Requirements

### P0 — Must have for hackathon demo (today, 4 PM)

- Snowflake query with completeness check
- Delta computation and anomaly detection
- AI-generated headline + "What Stands Out" + recommendations
- Console output of full report

### P1 — Must have for production launch

- Account snapshot table (templated)
- Campaign breakdown table (templated)
- Funnel overview table (templated)
- Teams webhook delivery
- Scheduled weekday trigger at 7:30 AM UTC
- Pipeline failure alert

### P2 — Should have (post-launch, pre-KAP rollout)

- Weekly report variant (same workflow, `window=7d` param)
- Transaction data layer (NEW_ORDERS, GROSS_PROFIT, GROSS_REVENUE surfaced more prominently)
- `override_date` manual trigger support

### P3 — Nice to have (future)

- First Click Attribution report as supplementary section
- Repeat vs. new customer breakdown in campaign table
- Multi-brand support (KAP, SOD) via config

---

## 11. Edge Cases and Error Scenarios

| Scenario | Behaviour |
|---|---|
| D-1 row count < 400 | Fall back to D-2; add header note |
| D-2 also incomplete | Log error; send failure alert to Teams; abort report |
| Campaign with spend but ORDERS = 0 | Flag as anomaly; display CPA as "—" not divide-by-zero error |
| New campaign (no trailing window data) | Show reporting day data; omit trailing avg and delta columns; label "(new)" |
| Campaign deactivated mid-window | Include in report if trailing 7d spend ≥ £10; note "(no spend yesterday)" |
| SESSIONS = 0 but CLICKS > 0 | Flag in funnel section as tracking discrepancy |
| Snowflake connection timeout | Retry once; on second failure, send Teams alert and abort |
| Teams webhook failure | Log error; do not retry (avoid duplicate messages) |
| Report > 24,000 chars | Split: message 1 = header+snapshot+breakdown, message 2 = funnel+analysis+recommendations |
| Weekend trigger (if misconfigured) | Cron pattern `0 7 * * 1-5` prevents this; no explicit guard needed |
| `override_date` set to future date | Return error: "Cannot report on future date" |
| Currency rounding | Always round spend to 2dp; counts to integers; rates to 1dp for %, 2dp for ratios |
