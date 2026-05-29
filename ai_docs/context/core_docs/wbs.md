# Work Breakdown Structure: Google Ads Intelligence Assistant

**Version:** 1.0  
**Date:** 2026-05-29  
**Status:** Active — Hackathon build in progress  
**Complexity:** Low < 1hr · Medium 1–2hr · High 2–4hr

---

## Milestone Map

```
TODAY 4 PM ──────────────────────── PRODUCTION ──────────── V1.1
[P0 Demo]                           [P1 Launch]             [Weekly report]
  │                                    │
  ├─ 1. Environment setup              ├─ 5. Celery beat + docker
  ├─ 2. Snowflake client               ├─ 6. Teams delivery node
  ├─ 3. Schema + workflow skeleton     ├─ 7. Scheduling + ops
  ├─ 4. SnowflakeQueryNode             └─ 8. Multi-brand config
  ├─ 4. ProcessingNode
  ├─ 4. NarrativeNode
  └─ Console output demo
```

---

## P0 — Hackathon Demo (Today, by 4 PM)

**Goal:** Real Snowflake data → AI narrative → printed to console.

---

### Task 1 — Environment & Dependencies
**Complexity: Low**

- [ ] **1.1** Generate RSA key pair for Snowflake service account
  ```bash
  openssl genrsa 2048 | openssl pkcs8 -topk8 -inform PEM -out rsa_key.p8 -nocrypt
  openssl rsa -in rsa_key.p8 -pubout -out rsa_key.pub
  base64 -i rsa_key.p8 | tr -d '\n'  # → SNOWFLAKE_PRIVATE_KEY_B64
  ```

- [ ] **1.2** Register public key on Snowflake service account user
  ```sql
  ALTER USER <username> SET RSA_PUBLIC_KEY='<pub key content without headers/footers>';
  ```

- [ ] **1.3** Add env vars to `docker/.env` and `app/.env` (for local dev):
  ```
  SNOWFLAKE_ACCOUNT=
  SNOWFLAKE_USER=
  SNOWFLAKE_PRIVATE_KEY_B64=
  SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=   # leave blank if unencrypted
  SNOWFLAKE_WAREHOUSE=
  SNOWFLAKE_DATABASE=DWH
  SNOWFLAKE_SCHEMA=MARKETING
  SNOWFLAKE_ROLE=                     # optional
  ANTHROPIC_API_KEY=                  # verify already set
  TEAMS_SOP_WEBHOOK_URL=              # leave blank for demo; needed for P1
  ```

- [ ] **1.4** Add `snowflake-connector-python` to `pyproject.toml` and install
  ```bash
  poetry add snowflake-connector-python
  ```

- [ ] **1.5** Verify `cryptography` package is available (needed for key loading)
  ```bash
  python -c "from cryptography.hazmat.primitives.serialization import load_pem_private_key; print('ok')"
  ```

**Done when:** `python -c "import snowflake.connector; print('ok')"` succeeds.

---

### Task 2 — Snowflake Client Service
**Complexity: Low**

- [ ] **2.1** Create `app/services/snowflake_client.py`
  - `get_snowflake_connection()` — loads key from `SNOWFLAKE_PRIVATE_KEY_B64`, returns `snowflake.connector.connect(...)` 
  - Key loading: base64 decode → `load_pem_private_key()` → `.private_bytes(DER, PKCS8, NoEncryption)`
  - All connection params from env vars

- [ ] **2.2** Smoke-test the connection manually
  ```python
  from services.snowflake_client import get_snowflake_connection
  conn = get_snowflake_connection()
  cur = conn.cursor()
  cur.execute("SELECT CURRENT_DATE()")
  print(cur.fetchone())
  conn.close()
  ```

**Done when:** Connection returns current date from Snowflake.

---

### Task 3 — Schema, Workflow Skeleton & Registry
**Complexity: Low**

- [ ] **3.1** Create `app/schemas/google_ads_schema.py`
  ```python
  from datetime import date
  from typing import Optional
  from pydantic import BaseModel

  class GoogleAdsReportEventSchema(BaseModel):
      brand: str = "sop"
      override_date: Optional[date] = None
  ```

- [ ] **3.2** Create `app/workflows/google_ads_report_nodes/__init__.py` (empty)

- [ ] **3.3** Create stub node files (empty `process()` returning `task_context`):
  - `snowflake_query_node.py` → `SnowflakeQueryNode(Node)`
  - `processing_node.py` → `ProcessingNode(Node)`
  - `narrative_node.py` → `NarrativeNode(AgentNode)`
  - `teams_delivery_node.py` → `TeamsDeliveryNode(Node)`

- [ ] **3.4** Create `app/workflows/google_ads_report_workflow.py`
  ```python
  class GoogleAdsReportWorkflow(Workflow):
      workflow_schema = WorkflowSchema(
          event_schema=GoogleAdsReportEventSchema,
          start=SnowflakeQueryNode,
          nodes=[
              NodeConfig(node=SnowflakeQueryNode, connections=[ProcessingNode]),
              NodeConfig(node=ProcessingNode,      connections=[NarrativeNode]),
              NodeConfig(node=NarrativeNode,       connections=[TeamsDeliveryNode]),
              NodeConfig(node=TeamsDeliveryNode,   connections=[]),
          ]
      )
  ```

- [ ] **3.5** Register in `app/workflows/workflow_registry.py`
  ```python
  GOOGLE_ADS_REPORT_WORKFLOW = GoogleAdsReportWorkflow
  ```

- [ ] **3.6** Validate workflow instantiates without error
  ```python
  from workflows.google_ads_report_workflow import GoogleAdsReportWorkflow
  wf = GoogleAdsReportWorkflow()
  print("Workflow valid")
  ```

**Done when:** Workflow instantiates and all node stubs resolve.

---

### Task 4A — SnowflakeQueryNode
**Complexity: Medium**

- [ ] **4A.1** Implement completeness check
  - Query: `COUNT(*) WHERE DATE = CURRENT_DATE-1 AND BRAND=%(brand)s AND SOURCE='Google'`
  - Run via `asyncio.to_thread()` wrapping sync connector
  - Set `reporting_date = D-1` if count ≥ 400 (env: `REPORT_COMPLETENESS_THRESHOLD`)
  - Else set `reporting_date = D-2`, `data_lag_flag = True`
  - Honour `event.override_date` if set (skip completeness check)

- [ ] **4A.2** Implement main query
  - SQL from ADD Section 9 (main report query)
  - Parameters: `brand`, `reporting_date`, `trailing_start = reporting_date - 7`
  - Returns list of dicts via `DictCursor`
  - Split result into `reporting_day_rows` and `trailing_rows` by DATE

- [ ] **4A.3** Store results in TaskContext
  ```python
  task_context.update_node("SnowflakeQueryNode",
      reporting_date=reporting_date,
      data_lag_flag=data_lag_flag,
      reporting_day_rows=reporting_day_rows,
      trailing_rows=trailing_rows,
  )
  ```

- [ ] **4A.4** Add error handling
  - `except Exception as e` → `metadata["error"] = f"Snowflake query failed: {e}"` (do NOT call `stop_workflow()` — TeamsDeliveryNode handles that)

- [ ] **4A.5** Manual test — print row counts and spot-check one campaign's COST

**Done when:** Node returns correct row split and reporting_date resolves correctly.

---

### Task 4B — ProcessingNode
**Complexity: High**

- [ ] **4B.1** Aggregate trailing rows
  - Group `trailing_rows` by CAMPAIGN
  - For each campaign: compute 7-day average of each numeric metric
  - Handle divide-by-zero (no trailing data = new campaign, mark as `is_new=True`)

- [ ] **4B.2** Aggregate reporting day rows
  - Group `reporting_day_rows` by CAMPAIGN
  - Sum numeric columns (handle duplicates in grain)

- [ ] **4B.3** Compute account-level rollup
  - Sum all campaign reporting_day values → `account_snapshot`
  - Average the averages for trailing → `account_trailing`

- [ ] **4B.4** Compute per-campaign derived metrics
  - `CPA = COST / NEW_ORDERS` (None if NEW_ORDERS = 0)
  - `ROAS = GROSS_REVENUE / COST` (None if COST = 0)
  - `CTR, CPC` — use directly from aggregated data
  - Funnel rates: `STARTED_ASSESSMENT / SESSIONS`, etc. (safe division)

- [ ] **4B.5** Compute deltas and direction indicators
  - `delta_pct = (day_val - avg_val) / avg_val * 100` (None if avg = 0)
  - Direction indicators per metric (see ADD Section 6.2 table)
  - `→` if |delta_pct| ≤ 5%

- [ ] **4B.6** Apply anomaly detection rules
  - CPA delta > 30% → Warning; > 100% → Critical
  - Spend delta > 50% → Warning
  - Impressions delta > 40% → Warning; complete delivery drop → Critical
  - New orders delta > 40% → Warning
  - COST > 0 and NEW_ORDERS = 0 → Warning
  - Had trailing spend but COST = 0 yesterday → Warning
  - Suppress if trailing 7d COST < £10

- [ ] **4B.7** Filter and sort campaign list
  - Exclude campaigns where trailing 7d COST < £10 AND reporting day COST = 0
  - Sort: reporting_day COST DESC; zero-spend campaigns at bottom

- [ ] **4B.8** Compute funnel snapshot (account-level)
  - Aggregate funnel columns across all campaigns for reporting day

- [ ] **4B.9** Store structured output in TaskContext
  - `account_snapshot`, `campaign_rows`, `anomalies`, `funnel_snapshot`

- [ ] **4B.10** Manual test — verify anomaly detection fires on known data

**Done when:** ProcessingNode outputs correct deltas and anomalies match what you'd compute manually.

---

### Task 4C — NarrativeNode
**Complexity: Medium**

- [ ] **4C.1** Define `NarrativeOutput` Pydantic model
  ```python
  class NarrativeOutput(BaseModel):
      headline: str
      what_stands_out: str
      recommendations: str
  ```

- [ ] **4C.2** Implement `get_agent_config()`
  - Model: `ModelProvider.ANTHROPIC`, `"claude-sonnet-4-6"`
  - `output_type=NarrativeOutput`
  - System prompt from ADD Section 6.3 (SOP analyst persona + rules)

- [ ] **4C.3** Implement `process()`
  - Read `ProcessingNode` output from `task_context.nodes`
  - Build structured user prompt:
    - Reporting date + data lag note
    - Account snapshot (formatted as mini-table)
    - Top anomalies with severity and description
    - Campaign breakdown (top 5 by spend, all flagged anomalous campaigns)
    - Funnel snapshot
  - Call `await self.agent.run_async(prompt)` 
  - Store `result.output.headline`, `.what_stands_out`, `.recommendations`

- [ ] **4C.4** Check for upstream error before running
  ```python
  if task_context.metadata.get("error"):
      return task_context  # skip narrative, TeamsDeliveryNode will alert
  ```

- [ ] **4C.5** Manual test — print narrative output, verify specificity

**Done when:** AI generates a non-generic headline naming a specific campaign and metric.

---

### Task 5 — Console Output (Demo Deliverable)
**Complexity: Low**

- [ ] **5.1** Create `app/workflows/google_ads_report_nodes/teams_delivery_node.py` (demo version)
  - Check `metadata.get("error")` → print failure notice if set
  - Assemble full markdown report (header + all tables + AI sections)
  - Print to stdout (no HTTP call)
  - Store `delivery_status = "console_demo"`

- [ ] **5.2** Write demo runner script `scripts/run_report_demo.py`
  ```python
  import sys
  sys.path.insert(0, "app")
  from dotenv import load_dotenv
  load_dotenv("app/.env")
  
  from workflows.google_ads_report_workflow import GoogleAdsReportWorkflow
  
  workflow = GoogleAdsReportWorkflow()
  result = workflow.run({"brand": "sop", "override_date": None})
  ```

- [ ] **5.3** Run end-to-end and verify output
  - Reporting date resolves correctly
  - All sections present in output
  - Numbers look correct vs. manual spot-check in Snowflake
  - Narrative is specific (campaign names, exact figures)

**Done when:** Full report prints to console with real data. Demo-ready.

---

## P1 — Production Launch (Post-hackathon)

---

### Task 6 — Teams Delivery Node (Real Webhook)
**Complexity: Low**

- [ ] **6.1** Replace console print with `httpx.AsyncClient().post(webhook_url, json=payload)`
- [ ] **6.2** Implement retry logic (30s sleep, one retry)
- [ ] **6.3** Implement message split if > 24,000 chars
- [ ] **6.4** Implement failure alert format
- [ ] **6.5** Configure `TEAMS_SOP_WEBHOOK_URL` in Teams channel settings
- [ ] **6.6** Test delivery to Teams channel (check message renders correctly)

**Done when:** Report appears in SOP Teams channel, formatted correctly.

---

### Task 7 — Celery Beat Schedule
**Complexity: Low**

- [ ] **7.1** Add `process_google_ads_report` task to `app/worker/tasks.py`
  ```python
  @celery_app.task(name="process_google_ads_report")
  def process_google_ads_report(event: dict):
      workflow = WorkflowRegistry.GOOGLE_ADS_REPORT_WORKFLOW.value()
      workflow.run(event)
  ```

- [ ] **7.2** Add `beat_schedule` to `get_celery_config()` in `app/worker/config.py`
  - `crontab(hour=7, minute=30, day_of_week="1-5")`
  - args: `[{"brand": "sop", "override_date": None}]`

- [ ] **7.3** Add `celery_beat` service to `docker/docker-compose.yml`
  ```yaml
  celery_beat:
    build: ...  # same as celery_worker
    command: celery -A worker.config.celery_app beat --loglevel=info
    depends_on: [redis]
  ```

- [ ] **7.4** Test scheduled trigger fires at correct time
  - Temporarily set schedule to 2 minutes from now, verify task runs

**Done when:** Report triggers automatically at 7:30 AM UTC on a weekday.

---

### Task 8 — Ops & Reliability
**Complexity: Low**

- [ ] **8.1** Add Snowflake env vars to `.env.example` (no values)
- [ ] **8.2** Verify `docker logs -f genai_celery_worker` shows node execution logs
- [ ] **8.3** Test failure path: set bad Snowflake password, verify Teams gets alert
- [ ] **8.4** Test data lag path: verify D-2 fallback flag appears in report header
- [ ] **8.5** Document known variance vs. Google Ads UI in a team note (attribution window)

**Done when:** Failure produces Teams alert; normal run produces report by 8:30 AM BST.

---

## P2 — Post-launch Additions

### Task 9 — Weekly Report Variant
**Complexity: Low** (config change, not a rebuild)

- [ ] **9.1** Add `report_window` parameter to `GoogleAdsReportEventSchema` (`daily` | `weekly`)
- [ ] **9.2** Update `SnowflakeQueryNode` to handle `weekly` window (prior full week vs. prior week)
- [ ] **9.3** Add weekly beat schedule entry (Monday, 7:30 AM UTC)
- [ ] **9.4** Adjust `NarrativeNode` prompt to note weekly context

---

### Task 10 — KAP / SOD Expansion
**Complexity: Low** (per brand)

- [ ] **10.1** Add brand beat schedule entry in `worker/config.py`
- [ ] **10.2** Add `TEAMS_{BRAND}_WEBHOOK_URL` to `.env`
- [ ] **10.3** Update `TeamsDeliveryNode` to select webhook by `event.brand`
- [ ] **10.4** Verify correct currency symbol per brand (£ SOP, € KAP, A$ SOD)

---

## Task Dependency Graph

```
1 (env/deps)
  └─▶ 2 (Snowflake client)
        └─▶ 3 (schema + workflow skeleton)
              ├─▶ 4A (SnowflakeQueryNode)
              │     └─▶ 4B (ProcessingNode)
              │           └─▶ 4C (NarrativeNode)
              │                 └─▶ 5 (console demo) ◀── DEMO DEADLINE
              └─▶ [stub nodes for 4B, 4C, 5 created in Task 3]

Post-hackathon:
5 ──▶ 6 (Teams webhook)
3 ──▶ 7 (Celery beat)
6 + 7 ──▶ 8 (ops/reliability) ──▶ PRODUCTION LAUNCH
```

---

## Hackathon Timeline (Today)

| Time | Target |
|---|---|
| Now → +45 min | Tasks 1 + 2: Env setup, Snowflake connection working |
| +45 min → +1.5hr | Task 3: Schema, stubs, workflow skeleton validates |
| +1.5hr → +2.5hr | Task 4A: SnowflakeQueryNode returning real data |
| +2.5hr → +3.5hr | Task 4B: ProcessingNode with deltas + anomalies |
| +3.5hr → +4hr | Task 4C: NarrativeNode generating real narrative |
| +4hr → demo | Task 5: Console output polished, demo runner works |
| Stretch | Task 6: Teams webhook delivery |

---

## Testing Strategy

### During Build (Inline)
- Each node has a manual smoke test (see "Done when" per task)
- Run nodes in isolation before wiring into full workflow
- Use `override_date` to test against known historical data

### Pre-Demo Validation
- [ ] Run `scripts/run_report_demo.py` with `override_date="2026-05-27"` (D-2, known good data)
- [ ] Spot-check 3 campaigns: verify COST, NEW_ORDERS, CPA match Snowflake query output
- [ ] Verify at least 1 anomaly is flagged (check against known data)
- [ ] Verify narrative mentions specific campaign names (not generic)
- [ ] Verify data lag flag behaviour: test with `override_date` for a date with low row count

### Post-Launch (P1)
- [ ] Verify Teams message renders correctly on desktop + mobile
- [ ] Verify failure alert fires when Snowflake credentials are bad
- [ ] Monitor first 5 production runs manually; compare to manager's manual report

---

## Risks & Mitigations

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Snowflake key-pair setup takes longer than expected | Medium | High — blocks everything | Have fallback: username/password auth while key is being registered |
| ProcessingNode logic has edge case bugs (zero-division, None handling) | High | Medium — report shows wrong numbers | Defensive safe-division helper; test against real data before demo |
| AI narrative is generic / doesn't name campaigns | Medium | Medium — demo looks weak | Front-load campaign names and anomaly descriptions in user prompt; test multiple times |
| D-1 data is incomplete during demo | Low | Medium | Use `override_date="2026-05-27"` for demo to target known-complete data |
| Teams webhook not configured in time | Low | Low | Console output is the P0 demo target; Teams is stretch |
