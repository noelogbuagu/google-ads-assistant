## Project Charter Scratchpad

### Session: 2026-04-24

---

### What We Know (from questions.txt)
- **Project:** Google Ads Assistant for a client ("KAP")
- **Core pain:** Daily reporting takes ~1 hour manually + must cross-reference GA data
- **Campaigns:** 13 total → 2 report buckets: WL (contains "weight" in name) vs Non-WL
- **Daily deliverable:** Performance report per bucket — spend, conversions, CPA/CAC, CVR, impression share, WoW comparison, suggestions
- **Secondary tasks:** CTR review for ads, CVR review for keywords, search term exclusion monitoring (cost-driven)
- **CPA target:** $500 for KAP
- **Data sources:** Google Ads + Google Analytics (GA)

---

### Coverage Status
- [ ] Project vision / problem statement
- [ ] Who is the user? (internal tool vs product?)
- [ ] Business objectives + success metrics
- [ ] Stakeholders
- [ ] Market / competitive landscape
- [ ] Resource constraints (time, budget, team)
- [ ] Risk assessment
- [ ] Revenue model / business strategy
- [ ] Regulatory / compliance (data privacy)
- [ ] Timeline + milestones
- [ ] Ethical considerations
- [ ] Future growth / scalability

---

### Answered
- **Scope:** MVP = KAP only; long-term = multi-account (similar campaign structures)
- **Primary reader:** Marketing manager (one person for MVP); may expand to team later
- **Output format:** Google Doc, delivered daily via email with editor access
- **Assistant role:** Generate reports faster + surface recommendations + flag anomalies; NO automated actions — human takes action

---

### Answered
- **Delivery:** Automated report generated from 7am, emailed ASAP
- **Anomalies defined:**
  1. High spend (>$1000) + low CAC — measured over ALL TIME (since campaign launch)
  2. Significant impression drop = below all-time average impressions
- **Recommendations:** AI-generated narrative suggestions
- **Builder:** Solo dev, **2.5 HOURS** (hackday), must be fully functional
- **Data source:** Google Ads API only (no GA), no existing pipeline — needs to be built
- **No prior tools** tried; gap = no existing tools do AI recommendations + anomaly flagging
- **Business model:** Internal tool (for now)

### Final Scoping Decisions
- **API token:** Not yet retrieved but easy to get — not a blocker
- **Anomaly logic:** TBD with marketing manager; for now use daily budget vs historical average as performance proxy
- **Email delivery:** DESCOPED from PoC
- **Google Doc output:** DESCOPED from PoC
- **PoC scope (FINAL):** Connect to Google Ads API → retrieve data → process → generate report output
- Anomaly definitions, email sending, Google Docs integration = post-MVP

### MVP Scope (Hackday PoC — 2.5hrs)
1. Google Ads API auth + connection
2. Retrieve campaign data (WL vs Non-WL split by "weight" in name)
3. Process: spend, conversions, CPA/CAC, CVR, impression share, CTR, WoW comparison
4. Performance context: daily budget vs historical average
5. AI-generated narrative report with recommendations
6. Output: file/stdout (no email, no Google Docs)
