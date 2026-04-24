## WBS Scratchpad

### Session: 2026-04-24

---

### Known Constraints
- Solo dev, ~2.5 hours total, hackday PoC
- Must be fully functional (not a prototype)
- No CI/CD, no formal testing — manual end-to-end is sufficient
- Sequential: setup → models → service → nodes → workflow → CLI → test

### Task Breakdown (draft)
1. Setup (15min): dirs, deps, .env
2. Data Models (15min): schemas + Pydantic models
3. Google Ads Service (30min): auth + 3 GAQL queries — HIGHEST RISK
4. Nodes (60min): 5 nodes + workflow definition
5. Prompt (10min): system prompt for Claude
6. CLI main.py (10min): argparse + workflow.run()
7. E2E Test (20min): real API run + verify output

Total estimate: ~160 min ≈ right at limit

### Final Decisions
- Build order: layer-by-layer
- WorkflowRegistry: register in existing enum
- Testing: E2E only — real credentials, verify 2 markdown files

### READY TO GENERATE WBS ✓
