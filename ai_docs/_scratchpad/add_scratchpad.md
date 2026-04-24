## Architecture Design Scratchpad

### Session: 2026-04-24

---

### Established Context
- **PoC:** CLI tool, single command, 2 markdown report outputs
- **Pipeline:** Google Ads API → segment → calculate metrics → AI narrative → .md files
- **Framework:** GenAI Launchpad (DAG workflow, Chain of Responsibility, Nodes)
- **AI:** Anthropic Claude via AgentNode
- **No:** FastAPI, Celery, DB, scheduling, email, Google Docs (PoC scope)

### Key Architectural Decision
- Use **workflow/node layer only** (no full stack) — CLI directly invokes Workflow.run()
- Full stack (FastAPI + Celery + DB) is Phase 2+ when scheduling + delivery needed

### Proposed Node Pipeline
1. FetchCampaignDataNode — Google Ads API auth + retrieve both date ranges
2. SegmentAndProcessNode — split WL/Non-WL + calculate all metrics + WoW deltas
3. GenerateReportsNode (concurrent) — WL AgentNode + Non-WL AgentNode in parallel
4. WriteReportsNode — write 2 markdown files to ./reports/

### Confirmed Decisions
- Sequential nodes (not concurrent) for simplicity
- Output dir: app/reports/
- Workflow layer only — no FastAPI/Celery/DB for PoC

### NEW from Diagram (Cognitive Architecture)
**Layers:**
- TRIGGER: Daily scheduler (7am cron) — Phase 2
- GROUNDING: Google Ads API → Campaign Classifier → Metrics Engine (CAC=Spend/Patients, Pacing, L7D Avg)
- MEMORY: Targets Config (hardcoded: £26K spend, £120 CAC, 258 orders/day) + Report History (prev day report)
- REASONING: LLM Interpreter (deltas vs targets, flags issues) → Report Drafter (PPP template: Progress/Problems/Priorities) → Reflection Loop (critic checks vs targets, refines)
- DECISION: Human Review Gate — analyst approves or edits (Phase 2)
- OUTPUT: Google Doc — Final PPP Report (Phase 2)

**Key deltas vs PRD:**
- Report format = PPP (Progress, Problems, Priorities) — not exec summary + breakdown + recommendations
- Metric: "Patients" = conversions (weight loss clinic context)
- Targets: £120 CAC (not $500), £26K spend, 258 orders/day
- Currency: £ (GBP), not USD
- Report History (prev day) as memory input — not discussed before
- Reflection Loop (LLM critic) — sophisticated but may be Phase 2 for PoC
- LLM Interpreter is separate step from Report Drafter

### Final Decisions
- Report = Exec Summary + Campaign Breakdown + AI PPP Section (combo)
- PPP (Progress, Problems, Priorities) is the AI-generated section
- Currency = USD from Google Ads API
- Reflection Loop = Phase 2 (deferred)
- Report History = Phase 2; WoW sufficient for PoC
- Sequential nodes confirmed
- Output: app/reports/

### READY TO GENERATE ADD ✓
