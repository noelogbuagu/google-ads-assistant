# Project Charter: Google Ads Assistant

**Version:** 1.0  
**Date:** 2026-04-24  
**Status:** Approved  
**Author:** Solo Developer  

---

## 1. Project Vision

Build an AI-powered Google Ads reporting assistant that automatically retrieves campaign performance data, processes it into structured insights, and generates narrative reports with anomaly flags and recommendations — eliminating the daily manual reporting burden for marketing teams managing Google Ads accounts.

---

## 2. Executive Summary

Currently, a marketing manager spends approximately one hour every day manually reviewing Google Ads performance across 13 campaigns for client KAP, logging into the platform, comparing metrics, and compiling insights. There are no automated tools that combine data retrieval, performance analysis, and AI-generated recommendations in a single workflow.

This project delivers a fully functional PoC (Proof of Concept) within a single hackday session that connects to the Google Ads API, retrieves and processes campaign data, and generates an AI-narrated performance report. The PoC validates the core pipeline. Subsequent phases will add anomaly detection, scheduled delivery, Google Docs output, and multi-account support.

---

## 3. Business Objectives & Success Metrics

| Objective | Success Metric |
|---|---|
| Eliminate manual daily reporting | Report generated with zero manual data retrieval |
| Deliver actionable intelligence | Report includes AI-generated narrative with recommendations |
| Validate the core pipeline | PoC successfully retrieves, processes, and outputs a report end-to-end |
| Provide performance context | Spend vs daily budget and historical average shown per campaign segment |
| Enable scale | Architecture supports adding additional accounts with minimal changes |

**PoC Success Criterion:** A single command produces a complete, readable performance report for KAP's Google Ads account, split by WL and Non-WL campaigns, with AI-generated narrative.

---

## 4. Scope

### Phase 1 — PoC (This Session, ~2.5hrs)

- Google Ads API authentication and connection
- Retrieve campaign-level data for KAP's account
- Segment campaigns into **Weight Loss (WL)** (campaign name contains "weight") and **Non-WL** (all others)
- Process core metrics per segment:
  - Spend
  - Conversions (orders)
  - CPA / CAC
  - Conversion Rate (CVR)
  - Impression Share
  - CTR (ads)
  - Week-over-Week (WoW) comparison
  - Daily budget vs historical average (performance context proxy)
- AI-generated narrative report with recommendations per segment
- Output: structured report to file or stdout

### Out of Scope (Phase 1)

- Email delivery automation
- Google Docs integration
- Precise anomaly thresholds (pending marketing manager input)
- Google Analytics data
- Multi-account support
- Scheduled/cron execution

### Phase 2 — Delivery Automation

- Scheduled daily execution (7am trigger)
- Automated email delivery to marketing manager with Google Doc
- Anomaly detection rules (once thresholds confirmed with marketing manager)

### Phase 3 — Scale & Productisation

- Multi-account support (similar campaign structures)
- Marketing team distribution
- Refined anomaly engine
- Historical trend visualisation

---

## 5. Stakeholders

| Stakeholder | Role | Engagement |
|---|---|---|
| Marketing Manager (KAP) | Primary report consumer | Daily recipient; defines success of report quality |
| Solo Developer | Builder and owner | Full delivery responsibility |
| KAP Marketing Team | Secondary future audience | Considered in Phase 2+ design |

---

## 6. Market & Competitive Context

Existing tools (Looker Studio, SuperMetrics, etc.) provide data visualisation and dashboards but do not offer:
- AI-generated narrative recommendations
- Automated anomaly flagging with contextual explanation
- A zero-touch daily report pipeline

This project's differentiator is the combination of automated data retrieval + AI reasoning layer, targeting marketing managers who need decision support, not just data display.

---

## 7. Constraints

| Constraint | Detail |
|---|---|
| **Time** | ~2.5 hours for PoC (hackday) |
| **Team** | Solo developer |
| **Budget** | Minimal — API costs only (Google Ads API, LLM API) |
| **Data Access** | Google Ads developer token required (not yet obtained; retrievable) |
| **Client** | Single account (KAP) for Phase 1 |
| **Analytics** | Google Analytics excluded from Phase 1 |

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Google Ads API setup takes longer than expected | Medium | High | Prioritise API auth as first task; halt point if >30min |
| API rate limits or data access restrictions | Low | Medium | Use test/limited queries first; cache responses |
| LLM output quality insufficient for recommendations | Low | Medium | Prompt engineering iteration; accept basic output for PoC |
| Anomaly thresholds undefined | High | Low (Phase 1) | Use daily budget vs historical average as proxy; defer precise rules |
| Scope creep during hackday | Medium | High | Strictly enforce Phase 1 scope; log deferred items |

---

## 9. Technical Assumptions

- Google Ads API developer token will be obtained before build begins
- KAP account has 13 active campaigns; "weight" in name reliably identifies WL segment
- LLM API (Anthropic Claude) is available and credentials are configured
- Python environment with required libraries available
- "Historical average" = lifetime average since campaign launch (all-time period)
- CPA target for KAP = $500

---

## 10. Timeline & Milestones

| Milestone | Target |
|---|---|
| Project Charter approved | 2026-04-24 |
| Google Ads API connected and data retrieved | 2026-04-24 (PoC session) |
| Data processing and segmentation working | 2026-04-24 (PoC session) |
| AI report generation working end-to-end | 2026-04-24 (PoC session) |
| Phase 2 planning (delivery automation) | TBD post-hackday |

---

## 11. Ethical Considerations

- Ad performance data is commercially sensitive; access must be restricted to authorised users
- AI-generated recommendations must be clearly labelled as suggestions — the system must never take automated actions on campaigns
- No client data to be stored beyond what is needed for report generation

---

## 12. Future Vision

A multi-account AI reporting platform used internally to serve multiple clients, with the potential to productise as a SaaS offering for marketing agencies running Google Ads at scale. The architecture prioritises modularity so additional accounts, metrics, and delivery channels can be added incrementally.

---

## 13. Immediate Next Steps

1. Obtain Google Ads developer token and OAuth credentials for KAP account
2. Run `/01_pre_dev:02_generate_prd` to define detailed product requirements
3. Run `/01_pre_dev:03_generate_architecture_design` to define technical architecture
4. Begin implementation — Google Ads API connection first
