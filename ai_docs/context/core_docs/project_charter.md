# Project Charter: Google Ads Intelligence Assistant

**Version:** 1.0  
**Date:** 2026-05-29  
**Author:** Solo developer / data engineer  
**Status:** Approved — Hackathon build begins immediately

---

## 1. Executive Summary

A marketing manager at SOP (UK) spends roughly one hour every weekday morning manually pulling metrics from Google Ads and Google Analytics, assembling a campaign performance report, and sending it to the team on Microsoft Teams. The data they need already exists — fully modelled and joined — in Snowflake. Nothing reads it, thinks about it, and delivers it.

This project builds an automated AI assistant that queries Snowflake each morning, analyses campaign performance against a rolling 7-day baseline, detects anomalies, and generates a ready-to-send narrative report delivered to the SOP marketing team's Teams channel by 7:30 AM UTC. The manager's hour becomes a 5-minute read. Anomalies surface before budget bleeds. The Head of Growth gets visibility without asking for it.

V1 is strictly read-only — observe, analyse, recommend. V2 introduces a Human-in-the-Loop approval flow for campaign-level interventions.

---

## 2. Problem Statement

| Pain Point | Impact |
|---|---|
| ~1 hour of daily data assembly | Manager's analytical time consumed by formatting |
| Manual pattern recognition across 13 campaigns | Anomalies (e.g. 25% CPA spike) missed for 2–3 days |
| Inconsistent report quality | Team discounts reports; coverage gaps on absence days |
| No ad-spend ↔ on-site funnel linkage | Cannot prove daily which campaigns drive buyers vs. bouncers |
| Process doesn't scale | Adding SOP/KAP/SOD requires another hire doing the same work |
| ACQUISITION_MASTER table unused at daily cadence | Funnel and attribution data exists; nobody reads it |

---

## 3. Vision Statement

> Replace the daily manual reporting ritual with an AI assistant that reads the data, understands the account, surfaces what matters, and delivers a trustworthy report — before the manager's first coffee.

---

## 4. Project Scope

### In Scope — V1 (Hackathon → Production)

- Daily weekday report for **SOP (UK)**
- Queries **Snowflake** via service account (ACQUISITION_MASTER + supporting tables)
- Compares **yesterday vs. 7-day trailing average** per campaign
- Generates structured narrative report with:
  - Headline summary (account-level performance signal)
  - Campaign breakdown table (Tier 1 metrics with Δ vs. baseline and ▲▼ indicators)
  - "What Stands Out" section (anomaly narrative, specific and non-generic)
  - Funnel layer (Tier 2 metrics — sessions, signups, funnel rates, revenue)
- Delivers to **Microsoft Teams** channel via incoming webhook
- Scheduled trigger: **7:30 AM UTC, weekdays**

### In Scope — V1.1 (Post-hackathon)

- Weekly report (Mondays, prior week vs. week before)
- Same workflow, configurable comparison window parameter
- Transaction data layer (orders, gross, contribution margin — schemas TBD)

### Out of Scope — V1

- Google Ads API calls (all data via Snowflake only)
- Campaign modifications of any kind
- Multi-brand support (KAP, SOD) — follows once SOP is proven
- External users, onboarding, multi-tenancy
- Natural language query interface

### Future — V2

- Human-in-the-Loop approval flow: AI recommends budget/bid changes → manager approves/dismisses via Teams action
- Expansion to KAP (DE) and SOD (AU) — duplicate workflow, change brand filter and currency

---

## 5. Metrics

### Tier 1 — Non-negotiable (every report)

| Metric | Notes |
|---|---|
| Spend (GBP) | Native SOP currency |
| Conversions (last-click) | Google Ads direct attribution |
| CPA | Efficiency signal |
| ROAS | Return signal |
| Impressions | Delivery health |
| Clicks / CTR | Ad relevance |
| CPC | Auction competitiveness |

### Tier 2 — High-value additions (the real differentiator)

| Metric | Notes |
|---|---|
| Sessions (GA4) | Click → site visit validation |
| Signups | Top-of-funnel conversion |
| Click → Signup rate | Landing page effectiveness per campaign |
| Signup → Purchase rate | Funnel quality per campaign |
| First-click conversions | Which campaigns start journeys |
| Revenue (GBP) | Actual business outcome |
| Orders (new, gross) | Transaction layer — schemas TBD |
| Contribution margin | Unit economics — schemas TBD |

---

## 6. Stakeholders

| Stakeholder | Role | Primary Need |
|---|---|---|
| **Marketing Manager** | Primary user + actioner | "What do I work on today?" — triage in under 5 min |
| **Head of Growth** | Sponsor | Morning visibility into spend efficiency; forward-able to leadership |
| **Performance marketers (×2–3)** | Awareness readers | Account pulse without logging into Google Ads |
| **Data engineer (builder)** | Creator + maintainer | Clean Snowflake access, reliable pipeline |

**Sponsor's v1 acceptance criteria:**

> *"I want to open Teams in the morning and immediately know if Google Ads spend is healthy or not — without waiting for someone to compile a report."*

---

## 7. Success Criteria

| Week | Milestone | Pass Condition |
|---|---|---|
| 1–2 | Reliability | Report arrives before 8:30 AM BST every weekday; numbers match Google Ads/GA within expected variance |
| 2–3 | Trust | Anomaly flags catch real issues; false positive rate < 1/week; narrative earns manager agreement |
| 3–4 | Adoption | Manager stops parallel manual process; Head of Growth references report in team meetings |

**Hard success bar:**

> *Manager reads report in 5 minutes and knows what to work on — without logging into Google Ads to verify the numbers.*

**Hackathon demo bar (today, 4 PM):**

> Real Snowflake query → AI-generated narrative → printed to console (Teams delivery as stretch goal)

---

## 8. Technical Architecture Overview

| Layer | Technology |
|---|---|
| Workflow orchestration | GenAI Launchpad (FastAPI + Celery + PostgreSQL) |
| Data source | Snowflake (service account) — ACQUISITION_MASTER + raw tables |
| AI analysis | pydantic_ai Agent (Anthropic Claude) |
| Delivery | Microsoft Teams incoming webhook |
| Scheduling | Celery beat / cron trigger |

**Data flow:**

```
Cron Trigger (7:30 AM UTC)
  → Snowflake Query Node (fetch yesterday + 7-day trailing)
  → Data Processing Node (compute deltas, flag anomalies)
  → AI Narrative Node (generate headline + table + "What Stands Out")
  → Teams Delivery Node (POST to webhook)
```

**Node-by-node build order** (matches hackathon sequencing):

1. Snowflake Query Node
2. Data Processing / Anomaly Detection Node
3. AI Narrative Generation Node
4. Teams Delivery Node *(last)*

---

## 9. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **Data misalignment** — report numbers don't match Google Ads UI (attribution windows, GA vs. Google Ads conversion counting, currency conversion) | High | Critical — destroys trust immediately | Explicitly label data source and attribution model in every report; document known variance expectations |
| AI narrative is generic / not account-specific | Medium | High — report gets ignored | Prompt engineering with campaign names, historical context, and anomaly specifics; avoid generic filler phrases |
| Snowflake data lag — yesterday's data not yet landed at 7:30 AM | Medium | High — stale report is worse than no report | Check data freshness before generating; delay send or flag if data is incomplete |
| False positive anomaly alerts | Medium | Medium — team starts ignoring flags | Tune anomaly thresholds (start at >30% vs. trailing avg); add context ("CPA is high but spend is <£50") |
| Teams webhook reliability | Low | Low — console fallback for demo | Webhook setup is last node; pipeline works without it |
| Healthcare ad content liability | Low | Medium — UK MHRA/ASA guidelines | AI narrative describes performance metrics only, not medical claims; no endorsement of ad content |

---

## 10. Constraints

| Constraint | Detail |
|---|---|
| **Timeline** | Hackathon demo today at 4 PM; production for SOP within weeks |
| **Team** | Solo developer + data engineer (same person) |
| **Budget** | Not a constraint — internal project |
| **Data access** | Snowflake service account (exists); ACQUISITION_MASTER + supporting tables |
| **Google Ads API** | Not used in V1 — all data via Snowflake |
| **Teams** | Incoming webhook (to be configured); last node |

---

## 11. Scale Path

Once SOP V1 is stable and trusted:

1. Duplicate workflow
2. Change `BRAND = 'sop'` → `'kap'` or `'sod'`
3. Adjust currency display (GBP → EUR / AUD)
4. Point to corresponding Teams channel
5. No architectural changes required

---

## 12. Immediate Next Steps

1. **Now:** Generate PRD (`/02_generate_prd`) — define node specs and data contracts
2. **Then:** Architecture Design (`/03_generate_architecture_design`) — Snowflake schema, workflow graph
3. **Then:** WBS (`/04_generate_wbs`) — hackathon task breakdown
4. **Build order:** Snowflake Node → Processing Node → AI Node → Teams Node
5. **Demo target:** Nodes 1–3 working end-to-end with real data by 4 PM
