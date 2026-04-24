## PRD Scratchpad

### Session: 2026-04-24

---

### From Project Charter (established)
- **Product:** Google Ads Assistant PoC
- **User:** Marketing manager (KAP), non-technical consumer of report
- **Invocation:** Single command → full report
- **Campaigns:** 13 total; WL = contains "weight" in name; Non-WL = rest
- **Metrics:** spend, conversions, CPA/CAC, CVR, impression share, CTR, WoW comparison, daily budget vs historical average
- **CPA target:** $500
- **Output:** file/stdout (PoC)
- **AI:** Claude API, narrative recommendations per segment
- **Scope exclusions:** email, Google Docs, GA, anomaly thresholds, multi-account, scheduling

---

### Coverage Status
- [ ] Invocation method (CLI? how run?)
- [ ] Report date range (today? yesterday? configurable?)
- [ ] WoW definition (same day -7? last 7d vs prior 7d?)
- [ ] Report structure / sections
- [ ] Output format (markdown? plain text? HTML?)
- [ ] Performance context calc (daily budget vs historical avg — formula?)
- [ ] Non-functional requirements (speed, reliability)
- [ ] Error handling expectations
- [ ] Data granularity (campaign-level only? or ad/keyword level too?)
- [ ] Acceptance criteria

### Answered
- **Invocation:** CLI (`python main.py` or similar), terminal
- **Output:** Markdown file
- **Date range:** Yesterday's data
- **WoW:** Same calendar day last week (e.g. Wednesday vs last Wednesday)
- **Granularity:** Campaign-level only
- **Report structure:**
  1. Executive Summary
  2. WL Section
  3. Non-WL Section
  4. AI Recommendations

---

### Final Decisions
- **2 separate reports:** one WL report, one Non-WL report
- **Same structure per report:**
  1. Executive Summary — brief narrative + aggregate key metrics across all campaigns in the group (spend, conversions, CPA, impressions, CVR, CTR — with WoW delta)
  2. Campaign Breakdown — per-campaign metrics
  3. AI Recommendations — specific to that report's segment
- **Output:** 2 markdown files (e.g. `report_wl_2026-04-24.md`, `report_nonwl_2026-04-24.md`)

### Assumptions for PRD (not explicitly confirmed, reasonable defaults)
- Error handling: halt with clear error message to stdout
- Speed: no strict SLA for PoC
- AI recommendations: one recommendations section per report
