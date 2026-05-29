# PRD Scratchpad

## Session
- Started: 2026-05-29
- Stage: ALL CAPTURED — generating PRD now

## Final Data Contract
- Table: DWH.MARKETING.ACQUISITION_MASTER
- Filters: BRAND = 'sop', SOURCE = 'Google', ATTRIBUTION = 'Last Click Attribution', IS_CAMPAIGN = 1
- Date logic: D-1 if COUNT(*) >= 400 for sop+Google; else fallback to D-2 + header note
- Trailing avg window: 7 days prior to reporting date (exclusive)
- Min spend threshold: £10 total in trailing 7d window
- Sort: reporting-date spend DESC, zero-spend campaigns at bottom

## SOURCE values confirmed
- Google Ads = SOURCE = 'Google' (channels: Paid Search, Shopping, Paid PMax, Display, Video, Multi_Channel)
- Meta = SOURCE = 'Meta', CHANNEL = 'Paid Social'
- V1 scope: Google only

## Freshness strategy: Option B
- Completeness check: COUNT(*) >= 400 for sop+Google on D-1
- Pass → use D-1
- Fail → use D-2, add header note "D-1 data incomplete — reporting on [D-2 date]"

## Funnel (healthcare-specific)
SESSIONS → STARTED_ASSESSMENT → SUBMITTED_ASSESSMENT → BASKET_PAGE → PURCHASED
+ NEW_ prefix = new customers only
ROAS = GROSS_REVENUE / COST, CPA = COST / NEW_ORDERS (new customer CPA)

## Report Sections
1. Header (date + freshness flag)
2. Headline (AI, 2-3 sentences)
3. Account Snapshot (Tier 1 table)
4. Campaign Breakdown (Tier 1 per campaign)
5. Funnel Overview (Tier 2)
6. What Stands Out (AI narrative, 3-5 paras)
7. Recommendations (AI, 3-5 bullets)
