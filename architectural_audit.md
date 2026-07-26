# DCPI EPC Platform — Architectural Audit & Technical Design Document

> **Prepared by:** Principal Software Architect  
> **Date:** 2026-07-16  
> **Scope:** 100% based on direct inspection of the repository at `MY_version_ET`  
> **Policy:** Zero-code, zero-invention — every finding is traceable to a specific file and line.

---

## 1. Architectural Map & Dependencies

### 1.1 Macro System Topology

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  USER (Browser)                                                              │
│  React SPA — Vite, React Router v6, Framer Motion, Tailwind CSS            │
│  Auth: AuthContext (JWT-like in sessionStorage) / WorkspaceContext          │
│  Routing: BrowserRouter → AnimatedRoutes → 19 Page Components               │
│  API Layer: single api/client.js (fetch, no axios, no global state mgr)    │
└──────────────┬───────────────────────────────────────────────────────────────┘
               │ HTTP (REST + multipart/form-data)
               │ VITE_API_BASE → /api  (same-origin SPA serving)
               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  FastAPI (main.py) — Uvicorn ASGI server, port 8000                         │
│  CORS: localhost:5173 (dev) / env CORS_ORIGINS (prod)                       │
│  Middleware: X-Process-Time header, X-Request-ID UUID, global exc handlers  │
│  Static: /uploads → filesystem, /assets → client/dist/assets               │
│  SPA catch-all: serves client/dist/index.html for unknown paths             │
│                                                                              │
│  13 Routers registered via _register_router() (upload=CRITICAL, rest=opt.) │
│  /api/upload   /api/auth      /api/projects   /api/bids                     │
│  /api/compliance  /api/schedule  /api/rfi      /api/dashboard               │
│  /api/commissioning  /api/supply-chain  /api/webhooks                       │
│  /api/design   /api/integrations                                            │
└──────────────┬───────────────────────────────────────────────────────────────┘
               │ Direct Python import (no message bus)
               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Services Layer                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐  ┌────────────────┐ │
│  │ llm_client   │  │ vector_store │  │ spec_parser   │  │ pdf_extractor  │ │
│  │ (Groq API)   │  │ (ChromaDB +  │  │ (LLM+batch)   │  │ (PyMuPDF/PDF   │ │
│  │ Multi-key    │  │  sentence-   │  │               │  │  plumber)      │ │
│  │ round-robin  │  │  transformers│  │               │  │                │ │
│  │ Semaphore 3  │  │  all-MiniLM) │  │               │  │                │ │
│  └──────────────┘  └──────────────┘  └───────────────┘  └────────────────┘ │
│  ┌──────────────┐  ┌──────────────┐                                         │
│  │ ingestion_   │  │ cache        │                                         │
│  │ queue        │  │ (TTLCache    │                                         │
│  │ (asyncio     │  │  in-memory,  │                                         │
│  │  semaphore,  │  │  max=256,    │                                         │
│  │  max=2 jobs) │  │  TTL=300s)   │                                         │
│  └──────────────┘  └──────────────┘                                         │
└──────────────┬───────────────────────────────────────────────────────────────┘
               │ Direct Python import
               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Agent Layer (LangGraph)                                                     │
│  orchestrator_agent.py — StateGraph, single classify→route→execute DAG     │
│    ├── knowledge_agent.py    (RAG: spec_clauses + rfis + document_memory)   │
│    ├── compliance_agent.py   (deviation scoring + NCR generation, batch LLM)│
│    ├── schedule_agent.py     (risk scoring, topo-sort, mitigation, batch LLM│
│    ├── commissioning_agent.py (checklist gen, step runner, auto NCR)        │
│    ├── procurement_agent.py  (bid analysis, mock shipment tracking)         │
│    └── supply_chain_agent.py (Haversine math + LLM risk narrative)         │
└──────────────┬───────────────────────────────────────────────────────────────┘
               │ get_db() → sqlite3 conn per call
               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Persistence Layer                                                           │
│  ┌─────────────────────────────┐  ┌────────────────────────────────────────┐│
│  │  SQLite (dcpi.db)           │  │  ChromaDB (./chroma_db/)              ││
│  │  WAL mode, PRAGMA fk=ON     │  │  PersistentClient, cosine HNSW        ││
│  │  16 tables (see §3.1)       │  │  4 collections:                       ││
│  │  sqlite3.Row factory        │  │  - spec_clauses                       ││
│  └─────────────────────────────┘  │  - rfis                               ││
│                                   │  - standards                          ││
│                                   │  - commissioning_checklists           ││
│                                   │  - document_memory                    ││
│                                   └────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
               │ aiohttp async
               ▼
         Groq Cloud API (llama-3.1-8b-instant, multi-key, max 3 concurrent)
```

### 1.2 Dependency Graph — Coupling Analysis

| Component | Depends On | Coupling Type |
|---|---|---|
| `main.py` | All 13 routers, `database.schema`, `services.ingestion_queue`, `services.vector_store` | **Tight** (import-time registration) |
| Every Agent | `database.connection.get_db()` — opens a **new connection per call** | **Tight** (shared mutable SQLite) |
| Every Agent | `services.llm_client` | **Loose** (via `has_available_provider()` guard + heuristic fallback) |
| `compliance_agent` | `services.vector_store.search_spec_clauses`, `services.llm_client` | **Moderate** (ChromaDB fallback to SQLite) |
| `knowledge_agent` | `services.vector_store` (5 functions), `services.llm_client` | **Tight** (both required for full functionality) |
| `orchestrator_agent` | All 5 worker agents (direct Python imports, not HTTP) | **Tight** (monolithic, no dynamic dispatch) |
| `routers/upload.py` | `services.spec_parser`, `services.pdf_extractor`, `services.ingestion_queue`, `services.llm_client` | **Tight** |
| `routers/dashboard.py` | `database.connection`, `services.cache` | **Loose** (only reads SQLite) |
| `client/src/api/client.js` | Backend via `/api/*` fetch calls | **Loose** (HTTP boundary) |

**Identified Extension Points (already in code):**
1. `_register_router()` in `main.py` — safe dynamic router registration by module name
2. `has_available_provider()` guard in `llm_client.py` — all agents gracefully degrade to heuristics
3. `CHROMADB_AVAILABLE` flag in `vector_store.py` — all agents fall back to SQLite if ChromaDB is unavailable
4. `get_or_create_collection(name)` in `vector_store.py` — any new collection can be created with a single call
5. `ingestion_queue.submit(coro_factory=...)` — lambda-captured coroutine allows any background task
6. `agent_runs` table — all agent invocations are already logged with input/output/status/timing

---

## 2. End-to-End Data Flow

### 2.1 Document Processing — Specification Upload

```
User uploads PDF → POST /api/upload/specification
  → routers/upload.py: save_upload_async() → filesystem (./uploads/<uuid>.pdf)
  → INSERT INTO documents (status='uploaded')
  → ingestion_queue.submit(coro_factory=lambda: _parse_spec_bg(doc_id, path))
  → [RETURNS 202 immediately with doc_id + job_id]

Background (asyncio semaphore, max 2 concurrent):
  _parse_spec_bg()
    → services/spec_parser.parse_spec_document_async()
      → services/pdf_extractor.extract_text_from_pdf() → raw text pages
      → Split text into clauses (regex on numbered headings)
      → BATCH call llm_client.call_claude_json_batch() [MAX_PARALLEL=5 concurrent]
        → Each clause → GROQ API → structured JSON (attribute, required_value,
          tolerance_type, mandatory, unit, confidence_score)
      → For each extracted clause:
        → INSERT INTO spec_clauses (requirements_json)
        → services/vector_store.index_spec_clause() → ChromaDB 'spec_clauses'
      → UPDATE documents SET status='ready', page_count=N

Frontend polls GET /api/upload/status/{doc_id} every 2s (max 30 attempts)
  → Returns {status: 'queued'|'processing'|'ready'|'failed'}
```

### 2.2 Vendor Submittal Upload → Compliance Check

```
User uploads submittal PDF → POST /api/upload/submittal (with po_id in form)
  → save_upload_async() → filesystem
  → pdf_extractor.extract_full_text() → raw text (synchronous, inline)
  → llm_client.call_claude_json() → extract technical_attributes_json
    (key-value dict: efficiency_pct, rated_kva, battery_autonomy_min, etc.)
  → INSERT/UPDATE purchase_orders (technical_attributes_json, document_id)
  → ingestion_queue.submit(lambda: _run_compliance_bg(po_id))

Background compliance check (compliance_agent.run_compliance_check):
  → get_db() → SELECT purchase_orders, equipment_items
  → normalize_attributes() → apply ATTR_ALIASES (30+ synonym map)
  → CHROMADB: search_spec_clauses(equipment_class, n_results=10)
    [FALLBACK: SELECT spec_clauses WHERE equipment_class=?]
  → compare_attributes() → per-attribute deviation detection
    (MIN/MAX/EXACT/RANGE tolerance types, numeric + string comparison)
  → IF no attributes → flag INVALID_DOCUMENT deviation
  → _score_deviations_batch() → call_claude_json_batch() [concurrent]
    → each deviation → GROQ → {severity, justification, w_conform}
    → FALLBACK: heuristic based on deviation_pct thresholds (15/10/5%)
  → INSERT INTO deviations (all scored deviations)
  → _generate_ncrs_batch() → call_claude_batch() [concurrent]
    → each CRITICAL/MAJOR/MINOR deviation → GROQ → formatted NCR text
    → INSERT INTO ncrs (title, description, actions_json, schedule_impact_json)
      → _compute_schedule_impact() → cross-reference schedule_tasks by eq_id
  → UPDATE purchase_orders (compliance_status, conformance_score, deviation_count)
  → INSERT INTO agent_runs (status='completed')
```

### 2.3 RFI Query — RAG Pipeline

```
User types query → POST /api/rfi/query → {query: "What is the UPS transfer time?"}
  → routers/rfi.py → knowledge_agent.answer_query(query)
  
  knowledge_agent:
    [Special case] "remember: ..." → ingest_document_memory() → ChromaDB
    
    Parallel retrieval:
      search_spec_clauses(query, n=5) → ChromaDB 'spec_clauses' cosine search
      search_rfis(query, n=5, only_resolved=True) → ChromaDB 'rfis' w/ filter
      search_standards(query, n=5) → ChromaDB 'standards'
      _search_document_memory(query, n=3) → ChromaDB 'document_memory'
    
    _find_precedent_rfis() → filter score > 0.82 + is_resolved=true
      → SELECT rfis WHERE id=? for each hit → get resolution_text
    
    Live project context injection:
      SELECT projects ORDER BY created_at DESC LIMIT 1
      → HTTP GET https://wttr.in/{location}?format=j1 (timeout=1.5s)
      SELECT bids WHERE project_id ORDER BY created_at DESC LIMIT 3
      SELECT purchase_orders WHERE project_id ORDER BY po_date DESC LIMIT 3
    
    call_claude(RAG_SYSTEM, context + precedents + query)
      → GROQ API → answer text with [SOURCE N] citations + [Confidence: H/M/L]
    
    Response: {answer, sources[], precedent_rfis[], confidence, agent_run_id}
    → INSERT INTO agent_runs
    → INSERT INTO rfis (if new RFI raised)
```

### 2.4 Schedule Risk Analysis

```
POST /api/schedule/analyze → schedule_agent.run_schedule_risk_analysis()

  1. SELECT schedule_tasks ORDER BY planned_start ASC
  2. SELECT ncrs WHERE status='open' → group by equipment_item_id
  3. _build_dependency_graph() → {pred_id: [successor_ids]}
  4. _topological_sort() → Kahn's algorithm (handles cycles via append-remaining)
  5. For each task (topological order):
     → _get_procurement_delay(ncr_list) → CRITICAL=14d, MAJOR=7d, MINOR=2d (+0.5/NCR)
     → predecessor_risks = computed_scores[pred_id] (cascades)
     → compute_task_risk_score(float, procurement, predecessor, resource, weather)
       weights: float=0.25, procurement=0.30, predecessor=0.20, resource=0.15, weather=0.10
     → compute_delay_probability() → sigmoid(k=7, θ=0.45)
  6. Select tasks with risk > 0.50 → build mitigation prompts
  7. _generate_mitigations_batch() → call_claude_batch() [concurrent, 3 opt per task]
  8. UPDATE schedule_tasks (risk_score, delay_prob, risk_level, mitigation_text,
     predicted_delay_days, historical_avg_delay)
  9. _update_delay_metrics() → second pass for low-risk tasks
  10. INSERT INTO agent_runs
```

---

## 3. Component Analysis

### 3.1 SQLite Database — Table Inventory

| Table | Purpose | Key Relationships | Indexes |
|---|---|---|---|
| `projects` | Project master record (name, size_mw, deadline, budget, tier, pm) | Root entity | None defined |
| `documents` | Uploaded PDFs — spec, submittal, general (status: uploaded→ready/failed) | FK→projects | None defined |
| `spec_clauses` | Parsed spec requirements (clause_number, requirements_json, confidence_score) | FK→documents | doc, equipment_class |
| `equipment_items` | Equipment register (item_code, equipment_class, quantity, criticality) | FK→projects, spec_clause_ids_json[] | None defined |
| `purchase_orders` | Vendor POs (technical_attributes_json, compliance_status, conformance_score) | FK→projects, documents, equipment_items | equipment_item_id |
| `deviations` | Attribute-level deviations (attribute_name, specified_value, submitted_value, severity, w_conform) | FK→purchase_orders, spec_clauses | po_id, severity, spec_clause_id |
| `ncrs` | Non-Conformance Reports (title, actions_json, schedule_impact_json) | FK→projects, deviations, purchase_orders, equipment_items | severity, status, po_id, equipment_item_id |
| `schedule_tasks` | Construction tasks (planned_start/finish, float_days, risk_score, mitigation_text) | FK→projects, equipment_items | risk_score, equipment_item_id, is_critical_path |
| `commissioning_records` | Test steps per commissioning task (step_name, criteria, actual_value, pass_fail) | FK→schedule_tasks, ncrs | task_id, status |
| `rfis` | Request for Information records (rfi_type, chroma_doc_id, is_resolved) | FK→projects, equipment_items, spec_clauses | is_resolved |
| `agent_runs` | Audit trail of all agent executions (agent_name, status, input/output_summary, timing) | FK→projects | agent_name |
| `vendors` | Vendor auth accounts (company_name, email, password_hash) | Root entity | email (UNIQUE) |
| `bids` | Vendor bids (price, lead_time_days, equipment_catalog_json, ai_recommendation, ai_scores_json) | FK→projects, vendors | project_id, vendor_id |
| `cost_records` | Financial impact of delays (daily_rate, total_impact, mitigation_cost) | FK→purchase_orders, equipment_items | None defined |
| `vendor_scores` | Calculated vendor performance (compliance/delivery/quality scores, ncr_count) | FK→vendors, projects | None defined |
| `workforce_demand` | Headcount requirements per task week | FK→schedule_tasks | None defined |
| `reports` | Generated executive reports (executive_summary, summary_json) | FK→projects | None defined |
| `shipments` | Real-time shipment tracking (lat/lng, carrier, status, risk_level, ai_alternatives_json) | FK→purchase_orders, equipment_items, vendors | None defined |

**Schema Notes:**
- JSON blobs are stored as `TEXT` columns (requirements_json, actions_json, predecessor_ids_json, etc.). There is no JSON1 extension usage — all deserialization happens in Python.
- `_migrate_*` functions provide additive-only ALTER TABLE migrations. No destructive migrations exist.
- `project_id` was retrofitted via `_migrate_project_ids()` across 7 tables — confirmed by the migration code.
- The `dcpi.db` file is **249 KB** on disk, confirming live seeded data.

### 3.2 ChromaDB Collections

| Collection | Populated By | Searched By | Embedding Model |
|---|---|---|---|
| `spec_clauses` | `spec_parser.py` → `vector_store.index_spec_clause()` on upload | `compliance_agent` (equipment lookup), `knowledge_agent` (RAG) | all-MiniLM-L6-v2 (384-dim) |
| `rfis` | `routers/rfi.py` → `vector_store.index_rfi()` | `knowledge_agent` (precedent lookup, `only_resolved=True`) | all-MiniLM-L6-v2 |
| `standards` | `routers/integrations.py` → `vector_store.index_standard()` | `knowledge_agent` (standards RAG) | all-MiniLM-L6-v2 |
| `commissioning_checklists` | `routers/integrations.py` | `commissioning_agent` (checklist retrieval) | all-MiniLM-L6-v2 |
| `document_memory` | `knowledge_agent.ingest_document_memory()` (general uploads + "remember:" prefix) | `knowledge_agent` (project memory) | all-MiniLM-L6-v2 |

All metadata is serialized to `str` via `_serialize_metadata()`. `is_resolved` is canonicalized as `"true"/"false"` strings. A dual-strategy filter (ChromaDB `where` clause → Python fallback) handles RFI resolved filtering.

### 3.3 Agent Analysis

#### Orchestrator Agent (`orchestrator_agent.py`)
- **Framework:** LangGraph `StateGraph` with typed `OrchestratorState` (TypedDict)
- **Pattern:** `classify_node` → `route_intent()` → one of 6 worker nodes → `END` (linear, no loops)
- **LLM Role:** Single JSON call to classify intent into 7 categories (KNOWLEDGE/PROCUREMENT/QUALITY/SCHEDULE/COMMISSIONING/REPORT/GENERAL)
- **Compiled Graph:** Singleton `_compiled_graph` — compiled once, reused
- **Inter-agent Calls:** Direct Python function calls, no async
- **Inputs:** `{query: str, context: Dict}` | **Outputs:** `{query, intent, agent_response, processing_time_ms}`
- **Weakness:** `report_node` is a **stub** — returns `{"message": "Dashboard agent called."}` with no actual data aggregation

#### Compliance Agent (`compliance_agent.py`)
- **Version:** 2.1.0 | Registered as `"spec_compliance"` in `agent_runs`
- **Inputs:** `po_id: str`
- **Outputs:** `{po_id, compliance_status, conformance_score, deviations[], ncr_ids[], summary, processing_time_ms}`
- **Key Logic:** 30+ attribute alias normalization (`ATTR_ALIASES`), then attribute comparison (MIN/MAX/EXACT with percentage tolerance), then batch LLM severity scoring, then batch NCR generation
- **Cross-agent:** Reads `schedule_tasks` to compute `schedule_impact_json` in NCRs — implicit Schedule→Compliance coupling
- **LLM Usage:** `call_claude_json_batch()` for severity, `call_claude_batch()` for NCR text
- **Heuristic Fallback:** Complete — `_apply_heuristic_scoring()` uses deviation_pct thresholds

#### Schedule Risk Agent (`schedule_agent.py`)
- **Version:** 2.1.0 | Contains **3 inlined stub agents** (`critical_path_agent`, `weather_agent`, `workforce_agent`) — these are commented-out and non-functional
- **Inputs:** None (reads all `schedule_tasks`)
- **Outputs:** `{tasks_analyzed, high_risk_count, at_risk_tasks[], agent_run_id}`
- **Key Algorithm:** Weighted risk score: `0.25*float + 0.30*procurement + 0.20*predecessor + 0.15*resource + 0.10*weather`
- **Weather:** `get_mock_weather_data()` always returns `"Heavy rain and thunderstorms expected"` — **hardcoded mock**
- **Cross-agent:** Reads `ncrs` (open, by equipment) to calculate procurement delay — cross-reads Compliance Agent output
- **LLM Usage:** `call_claude_batch()` for mitigation text (3 options per at-risk task)

#### Knowledge Agent (`knowledge_agent.py`)
- **Version:** 2.0.0 | AGENT_NAME: `"knowledge_intelligence"`
- **Inputs:** `query: str`
- **Outputs:** `{answer, sources[], precedent_rfis[], confidence, agent_run_id}`
- **RAG Sources:** spec_clauses (ChromaDB) + rfis (ChromaDB, resolved-only) + standards (ChromaDB) + document_memory (ChromaDB)
- **Special Feature:** `"remember: ..."` prefix triggers direct ingestion to `document_memory`
- **Live Context:** Makes an outbound HTTP call to `wttr.in` (1.5s timeout) for current weather at the project location — **network dependency in hot path**
- **Precedent Detection:** Cosine similarity > 0.82 against resolved RFIs
- **LLM Usage:** Single `call_claude()` with combined context (max 400 words output)

#### Commissioning Agent (`commissioning_agent.py`)
- **Version:** 1.0.0 | AGENT_NAME: `"commissioning_copilot"`
- **Inputs:** `task_id: str` (for checklist gen) or none (for task listing)
- **Outputs:** `{commissioning_tasks[], total, pass_rate_pct}` or `{steps_generated, status}`
- **Step Templates:** Hardcoded `STEP_TEMPLATES` dict for UPS (10 steps), PDU (7), COOLING (7), GENERATOR (8), DEFAULT (6)
- **LLM Role:** Optional enhancement of templates via `call_claude_json()` — falls back to templates if LLM fails
- **Auto-NCR:** Failed commissioning steps auto-create a `deviation` + `ncr` record — tightly coupled to `purchase_orders` (requires at least one PO to exist)
- **Pass/Fail:** Heuristic keyword matching + numeric threshold extraction from criteria string

#### Procurement Agent (`procurement_agent.py`)
- **Version:** 2.0.0 | Contains **2 inlined stubs** (`vendor_agent`, `cost_agent`)
- **Inputs:** `bids: List[Dict]` for analysis, `po_id: str` for tracking
- **Outputs:** `{bids_analyzed, recommendations[{vendor_name, price_score, compliance_score, lead_time_score, risk_score, overall_score, recommendation, justification}]}`
- **Shipment Tracking:** `get_mock_shipment_tracking()` returns hardcoded mock data — not connected to `shipments` table
- **Cost Agent stub:** `calculate_delay_impact()` uses `$50,000/day` hardcoded penalty — illustrative only

#### Supply Chain Agent (`supply_chain_agent.py`)
- **Inputs:** `shipment_id: str`
- **Outputs:** `{risk_assessment, alternatives[], recommendation}`
- **Key Logic:** Haversine distance math → deterministic risk scoring (0-100) → conditional LLM call (only for HIGH/CRITICAL)
- **Cross-agent:** Reads `schedule_tasks` (float_days, is_critical_path) for shipment's linked equipment — implicit Schedule coupling

### 3.4 API Endpoints → Frontend Page Mapping

| Frontend Page | Route | Primary API Calls |
|---|---|---|
| `LandingPage.jsx` | `/` (unauthenticated) | None |
| `ProjectsPage.jsx` | `/projects` | `GET /api/projects/`, `GET /api/projects/open` |
| `NewProject.jsx` | `/projects/new` | `POST /api/projects/` |
| `Dashboard.jsx` | `/dashboard` | `GET /api/dashboard/summary` (TTL=300s cached), `POST /api/dashboard/resolve-all` |
| `Compliance.jsx` | `/compliance` | `GET /api/compliance/ncrs`, `POST /api/compliance/run/{poId}`, `GET /api/compliance/results/{poId}` |
| `NCRDetail.jsx` | `/ncr/:ncrId` | `GET /api/compliance/ncr/{ncrId}` |
| `Schedule.jsx` | `/schedule` | `POST /api/schedule/analyze`, `GET /api/schedule/tasks`, `GET /api/schedule/risks`, `GET /api/schedule/delay-comparison` |
| `RFIChat.jsx` | `/rfi` | `POST /api/rfi/query`, `GET /api/rfi/rfis` |
| `BidsAndContracts.jsx` | `/bids` | `GET /api/bids/{projectId}`, `POST /api/bids/recommend`, `PATCH /api/bids/update_status/{bidId}` |
| `CommissioningPage.jsx` | `/commissioning` | `GET /api/commissioning/tasks`, `POST /api/commissioning/checklist/generate/{taskId}`, `POST /api/commissioning/run/{taskId}/step/{stepNumber}` |
| `SupplyChainPage.jsx` | `/supply-chain` | `GET /api/supply-chain/shipments`, `GET /api/supply-chain/alerts`, `GET /api/supply-chain/map` |
| `DocumentsPage.jsx` | `/documents` | `GET /api/upload/documents`, `POST /api/upload/specification`, `POST /api/upload/general`, `DELETE /api/upload/document/{docId}` |
| `IntegrationsPage.jsx` | `/integrations` | `POST /api/integrations/upload` |
| `DesignPage.jsx` | `/design` | `GET /api/design/*` |
| `TeamPage.jsx` | `/team` | Static/local state only |
| `SettingsPage.jsx` | `/settings` | Static/local state only |
| `VendorDashboard.jsx` | `/` (vendor role) | `GET /api/bids/*`, `GET /api/projects/*` |
| `VendorBids.jsx` | `/vendor/bids` | `POST /api/bids/create`, `GET /api/bids/{projectId}` |

**Frontend State Management:** There is no Redux, Zustand, or React Query. State is managed via `useState`/`useEffect` within each page component. `AuthContext` (2 contexts: `AuthContext` + `WorkspaceContext`) provides cross-page state. The API client in `client.js` has no global state, caching, or request deduplication.

**Auth Model:** Client-side only — `AuthContext` stores `user` object in `sessionStorage`. No JWT validation occurs on the backend in any visible router. Vendor auth (`/api/auth/register/vendor`, `/api/auth/login`) uses `password_hash` in the `vendors` table (via `security.py`), but PM/admin auth is purely client-side.

---

## 4. Technical Debt Assessment

> These are **extension-blocking weaknesses**, not criticisms. Each item is an obstacle to safely adding the 9 new capabilities.

### 4.1 CRITICAL — Architectural Risks

**[DEBT-01] Per-call `get_db()` Connection Pattern**
Every agent and router opens a fresh `sqlite3.Connection` on each call and closes it in a `finally` block. Under concurrent load (e.g., compliance batch processing while a user queries the dashboard), SQLite WAL mode limits contention but does not eliminate it. The `busy_timeout=30000ms` is the only safeguard. At scale, this creates connection overhead and risk of `database is locked` errors.
- **Impacted files:** `database/connection.py`, every agent file, every router file
- **Extension risk:** Adding 9 new capabilities, each opening DB connections, increases this pressure.

**[DEBT-02] Hardcoded Mock Weather Data in Schedule Risk**
`schedule_agent._infer_weather_risk()` calls `get_mock_weather_data()` which unconditionally returns `"Heavy rain and thunderstorms expected"`. This means **all tasks have artificially inflated weather risk**. The `knowledge_agent` makes a real `wttr.in` call but the schedule agent does not.
- **File:** `server/agents/schedule_agent.py` lines 383–406

**[DEBT-03] `report_node` in Orchestrator is a Stub**
`orchestrator_agent.report_node()` returns `{"message": "Dashboard agent called."}`. The REPORT intent is routable but produces no useful output. The "Executive Dashboard" capability is therefore not addressable through the orchestrator today.
- **File:** `server/agents/orchestrator_agent.py` line 171–176

**[DEBT-04] Commissioning NCR Requires Existing PO**
`commissioning_agent._raise_commissioning_ncr()` falls back to `SELECT id FROM purchase_orders LIMIT 1` if no PO is linked to the equipment. In a fresh project with no POs, this silently skips NCR creation. No error is raised — the commissioning step is marked as failed but no NCR is linked.
- **File:** `server/agents/commissioning_agent.py` lines 404–415

**[DEBT-05] Inlined Stub Agents in Working Agent Files**
Three stub agents (`critical_path_agent`, `weather_agent`, `workforce_agent`) are inlined at the bottom of `schedule_agent.py` via comments like `# INTEGRATED FROM: critical_path_agent.py`. They define a `process_request()` function that conflicts with the live `process_request()` in `procurement_agent.py` (also inlined). At import time, the second definition silently shadows the first.
- **Files:** `schedule_agent.py` lines 730–817, `procurement_agent.py` lines 139–209
- **Risk:** Python module-level name collision — `process_request` in `procurement_agent.py` is redefined twice.

### 4.2 MAJOR — Performance & Reliability

**[DEBT-06] In-Memory Ingestion Queue State — No Persistence**
`ingestion_queue` is an in-process asyncio queue. If the server restarts mid-ingestion, all queued/processing jobs are lost. The DB `status` remains `'uploaded'` forever (neither `ready` nor `failed`). The frontend will poll indefinitely.
- **File:** `server/services/ingestion_queue.py`

**[DEBT-07] `wttr.in` Live HTTP Call in RAG Hot Path**
`knowledge_agent._build_user_message()` makes a blocking HTTP call to `wttr.in` with a 1.5s timeout. This adds latency to every RFI query and can cause a 1.5s hard delay if the external service is slow or unreachable. The call is inside a `try/except` but the latency still applies on the happy path.
- **File:** `server/agents/knowledge_agent.py` lines 342–351

**[DEBT-08] TTL Cache Not Invalidated on Agent Writes**
`dashboard.py` caches `/summary` with `TTL=300s`. NCR creation, compliance checks, and schedule analysis all write to the tables the dashboard aggregates, but they do not invalidate the cache. A user who runs a compliance check will see stale dashboard metrics for up to 5 minutes.
- **Files:** `server/routers/dashboard.py` (cache set), `compliance_agent.py`, `schedule_agent.py` (no cache invalidation)

**[DEBT-09] No Pagination on Any List Endpoint**
`routers/compliance.py`, `routers/schedule.py`, `routers/rfi.py` all return unbounded result sets. In a production project with 500+ tasks and 200+ NCRs, these endpoints will return full table scans on every frontend load.

**[DEBT-10] `resolve-all` is a Destructive Data Mutation**
`POST /api/dashboard/resolve-all` bulk-updates all open NCRs to `'closed'`, resets all risk scores to `0.1`, and resolves all RFIs — without soft-delete, audit trail, or confirmation. It is available without authentication at the backend router level.
- **File:** `server/routers/dashboard.py` lines 160–177

### 4.3 MINOR — Code Quality

**[DEBT-11] Duplicate `index_commissioning_checklist` Function**
`vector_store.py` defines `index_commissioning_checklist` **twice** (lines 314 and 604). The second definition (line 604) is a more complete version that raises `IndexingError`. The first (line 314) is a duplicate with slightly different behavior.

**[DEBT-12] `getPurchaseOrders` API Call Routes Through Dashboard**
`client.js` line 162: `getPurchaseOrders()` calls `GET /api/dashboard/summary` and extracts `data.purchase_orders`. This means fetching POs triggers the full dashboard aggregation (all NCR counts, health score, etc.) — a semantically incorrect and wasteful coupling.

**[DEBT-13] No Project-Scoped Filtering in Most Agent Calls**
`schedule_agent.run_schedule_risk_analysis()` runs `SELECT * FROM schedule_tasks` with no `WHERE project_id=?` filter. Same for `compliance_agent.run_compliance_check()`. In a multi-project deployment, every analysis spans all projects' data.

**[DEBT-14] `security.py` exists but is not wired to API routes**
`server/security.py` (2197 bytes) defines auth utilities but no FastAPI middleware or `Depends()` wiring was visible in any router. The API is effectively unauthenticated at the HTTP layer.

---

## 5. Extension Strategy & Integration Points

> For each of the 9 capabilities, the following defines: exact files to modify (never delete), which existing DB tables/collections to reuse, what new tables are needed, and the specific extension points to use.

---

### 5.1 Living Intelligence Layer

**What it is:** Continuous background monitoring that fires alerts when risk thresholds change — NCR spikes, float erosion, bid deadline proximity.

**Reused infrastructure:**
- `services/ingestion_queue.py` → submit new `monitor_*` coroutines on a periodic schedule
- `agent_runs` table → log each monitoring cycle
- `ncrs`, `schedule_tasks`, `bids` tables → read-only queries

**Files to MODIFY:**
- `main.py` → in `lifespan()`, after `ingestion_queue.start()`, start a new `asyncio` background task for the monitor loop (existing pattern: `loop.create_task(...)`)
- `routers/webhooks.py` → add `POST /api/webhooks/alert` endpoint (file already exists, extend it)

**New files (additive only):**
- `server/agents/monitor_agent.py` — new agent, polls DB, applies threshold rules, writes to `alerts` table

**New DB tables needed:**
- `alerts` table: `(id, project_id, alert_type, severity, message, entity_id, entity_type, created_ts, acknowledged_ts, acknowledged_by)`

**ChromaDB:** No new collection needed.

---

### 5.2 Cross-Agent Collaboration

**What it is:** Multi-step agent workflows where output from one agent feeds into another — e.g., a compliance deviation automatically triggers schedule re-analysis.

**Reused infrastructure:**
- `orchestrator_agent.OrchestratorState` (TypedDict) → add `collaboration_chain: List[str]` field
- `orchestrator_agent.get_orchestrator_graph()` → add new edges between existing nodes
- `agent_runs` table → link runs via a `parent_run_id` column (additive column via `_migrate_new_tables`)

**Files to MODIFY:**
- `orchestrator_agent.py` → add a `collaboration_router` conditional edge after `quality_node` → can route to `schedule` node if CRITICAL NCRs detected
- `compliance_agent.py` → return `trigger_schedule_reanalysis: bool` in output dict (no signature change, just add key)
- `schedule_agent.py` → `update_timeline_dynamic()` already exists for this purpose (line 639)

**No new tables needed** — `agent_runs` with a new `parent_run_id` column (added via existing `_migrate_new_tables` pattern) is sufficient.

---

### 5.3 Procurement Intelligence

**What it is:** Enhanced bid analysis with vendor history scoring, market price benchmarking, and lead-time risk scoring.

**Reused infrastructure:**
- `vendor_scores` table → already exists with compliance/delivery/quality scores
- `bids` table → `ai_recommendation` and `ai_scores_json` columns already exist
- `procurement_agent.analyze_bids()` → extend the BID_ANALYSIS_SYSTEM prompt
- `routers/bids.py` → `GET /api/bids/recommend` already calls procurement agent

**Files to MODIFY:**
- `procurement_agent.py` → add `analyze_vendor_history(vendor_id)` function that reads `vendor_scores`, `ncrs`, `deviations` tables
- `routers/bids.py` → wire the new function into the existing recommend endpoint
- `models/schemas.py` → add `VendorScoreResponse` Pydantic model

**New DB tables:** None required — `vendor_scores` table already exists.

---

### 5.4 Predictive Schedule Engine

**What it is:** Replace the hardcoded `_HISTORICAL_DELAY_MAP` with actual learned delay patterns from `schedule_tasks.actual_delay_days`, and integrate real weather data.

**Reused infrastructure:**
- `schedule_tasks` table → `actual_delay_days`, `predicted_delay_days`, `historical_avg_delay` columns **already exist**
- `schedule_agent._compute_historical_avg_delay()` → replace keyword lookup with DB aggregate query
- `schedule_agent._infer_weather_risk()` → replace `get_mock_weather_data()` with actual call
- `workforce_demand` table → already exists for headcount conflict detection

**Files to MODIFY:**
- `schedule_agent.py` → `_compute_historical_avg_delay()` (line 698) → add `SELECT AVG(actual_delay_days) FROM schedule_tasks WHERE description LIKE ?` query as primary source, keyword map as fallback
- `schedule_agent.py` → `get_mock_weather_data()` (line 400) → call the real `wttr.in` API (same pattern already used in `knowledge_agent.py` lines 342-351)

**No new files, no new tables needed.** The schema was already designed for this.

---

### 5.5 Commissioning Copilot

**What it is:** Enhanced commissioning with AI-driven acceptance criterion validation, digital sign-off workflow, and integration test tracking.

**Reused infrastructure:**
- `commissioning_records` table → already has `pass_fail`, `checked_by`, `checked_ts`, `flagged_ncr_id`
- `commissioning_agent.run_step()` → already auto-evaluates and raises NCRs
- `commissioning_checklists` ChromaDB collection → already populated via integrations
- `STEP_TEMPLATES` dict → extensible with new equipment classes

**Files to MODIFY:**
- `commissioning_agent.py` → enhance `_evaluate_pass_fail()` to use `call_claude()` for complex numerical criteria instead of heuristic string parsing
- `routers/commissioning.py` → add `GET /api/commissioning/summary/{project_id}` for per-project stats

**New DB tables:** None required.

**ChromaDB:** No new collection needed — `commissioning_checklists` is already wired.

---

### 5.6 Supply Chain Intelligence

**What it is:** Real shipment tracking integration, multi-shipment risk aggregation, and alternative sourcing recommendations.

**Reused infrastructure:**
- `shipments` table → fully designed, seeded with mock data (Ashburn/Dallas/NY routes)
- `supply_chain_agent.analyze_shipment_risk()` → full Haversine + LLM pipeline already implemented
- `routers/supply_chain.py` → endpoints already registered
- `ai_alternatives_json` column in `shipments` → stores LLM-generated alternatives

**Files to MODIFY:**
- `supply_chain_agent.py` → `get_mock_shipment_tracking()` in `procurement_agent.py` (line 107) → replace mock return with actual `SELECT FROM shipments WHERE po_id=?` query
- `routers/supply_chain.py` → add `POST /api/supply-chain/analyze/{shipment_id}` that calls `supply_chain_agent.analyze_shipment_risk()`

**New DB tables:** None required — `shipments` table is fully defined.

---

### 5.7 Standards Engine

**What it is:** Automated cross-referencing of spec clauses against IEC/EN/ANSI standards stored in ChromaDB.

**Reused infrastructure:**
- `standards` ChromaDB collection → already exists, indexed by `index_standard()`
- `routers/integrations.py` → already handles PDF upload to standards collection
- `knowledge_agent.search_standards()` → already searches the collection
- `spec_clauses.requirements_json` → `standards_referenced` field extracted by `spec_parser`

**Files to MODIFY:**
- `knowledge_agent.py` → add `check_clause_against_standards(clause_id)` function that retrieves the clause from SQLite, searches `standards` collection, and returns compliance assessment
- `routers/compliance.py` → add `GET /api/compliance/standards-check/{clause_id}` endpoint

**New DB tables:** 
- `standards_violations` table: `(id, spec_clause_id, standard_id, standard_ref, violation_text, severity, detected_ts)` — lightweight extension

---

### 5.8 Executive Dashboard

**What it is:** A fully populated dashboard endpoint that aggregates cross-agent KPIs — replacing the stub `report_node`.

**Reused infrastructure:**
- `reports` table → already exists with `executive_summary`, `summary_json` columns
- `routers/dashboard.py` → `GET /api/dashboard/summary` already exists with comprehensive aggregation (15+ metrics)
- `agent_runs` table → full audit trail queryable
- `services/cache.py` → `@cache.cached_async()` decorator already works

**Files to MODIFY:**
- `orchestrator_agent.py` → `report_node()` (line 171) → call `routers.dashboard.get_dashboard_summary()` or add a proper `report_agent.generate_report()` call
- `agents/report_agent.py` → already exists (1,722 bytes) — add actual aggregation logic pulling from `reports` table
- `routers/dashboard.py` → add `POST /api/dashboard/generate-report/{project_id}` that writes to `reports` table and invalidates cache

**No new tables needed.**

---

### 5.9 Computer Vision

**What it is:** Image-based document processing for site photos, drawing sheets, and QR-coded equipment labels.

**Extension approach (non-destructive):**
- The `pdf_extractor.py` already handles binary files. A new `image_extractor.py` service can follow the same pattern.
- `documents` table → `doc_type` field already accepts free-form strings; add `"site_photo"`, `"drawing"` as new types
- The `ingestion_queue` pattern (submit coroutine factory) handles the async processing naturally

**Files to MODIFY:**
- `routers/upload.py` → add `POST /api/upload/image` endpoint using the same `save_upload_async()` helper
- `main.py` → no change needed, `_register_router` pattern handles new routes

**New files (additive only):**
- `server/services/image_processor.py` — wraps vision API calls
- `server/agents/vision_agent.py` — processes site photos, identifies equipment, flags non-conformances

**New ChromaDB collection:**
- `site_photos` — stores image embeddings and metadata for visual search

**New DB tables:**
- `site_observations` table: `(id, project_id, image_path, observation_type, description, equipment_item_id, ncr_id, detected_ts, lat, lng)`

---

## 6. Recommended Implementation Sequence

The sequence below is ordered to maximize reuse of existing infrastructure, minimize breakage risk, and deliver visible value at each phase.

### Phase 1 — Fix Critical Debt First (Prerequisite)
> Before any new capability, remove the two blockers that will break new agents.

1. **Fix stub agent shadowing** (`schedule_agent.py`, `procurement_agent.py`) — extract stub content to separate files or delete
2. **Connect `getPurchaseOrders()` to a real endpoint** — add `GET /api/upload/pos` instead of routing through dashboard
3. **Implement cache invalidation** — `compliance_agent` and `schedule_agent` should call `cache.invalidate_prefix("dashboard_summary")` after DB writes

**Risk:** Very low. These are bug fixes with no API surface changes.

---

### Phase 2 — Predictive Schedule Engine + Standards Engine
> Both require zero new tables and only modify existing functions.

4. **Predictive Schedule** → Replace `get_mock_weather_data()` and `_compute_historical_avg_delay()` keyword lookup with real DB aggregation
5. **Standards Engine** → Add `standards_violations` table + `check_clause_against_standards()` in knowledge agent + new compliance router endpoint

**Risk:** Low. Additive changes only.

---

### Phase 3 — Living Intelligence Layer + Cross-Agent Collaboration
> Requires new table + new background task.

6. **Living Intelligence** → Add `alerts` table, add `monitor_agent.py`, wire to `main.py` lifespan
7. **Cross-Agent Collaboration** → Add `parent_run_id` to `agent_runs`, add collaboration edge in orchestrator graph

**Risk:** Medium. New background task in the event loop requires testing with existing `ingestion_queue`.

---

### Phase 4 — Supply Chain Intelligence + Procurement Intelligence
> Connect existing mock stubs to real data.

8. **Supply Chain** → Replace mock shipment tracking in `procurement_agent` with real `shipments` table query; add `POST /api/supply-chain/analyze/{shipment_id}`
9. **Procurement Intelligence** → Add `analyze_vendor_history()`, wire to existing bids recommend endpoint

**Risk:** Low. Replaces mock functions with DB reads.

---

### Phase 5 — Commissioning Copilot + Executive Dashboard
> Enhance existing agents, fill the stub.

10. **Commissioning Copilot** → Upgrade `_evaluate_pass_fail()` with LLM evaluation for complex criteria
11. **Executive Dashboard** → Implement `report_node()` in orchestrator; wire `report_agent.py`; add report generation endpoint

**Risk:** Low-Medium. Commissioning LLM upgrade changes existing auto-evaluation behavior.

---

### Phase 6 — Computer Vision (Last)
> Entirely new infrastructure; highest risk of disruption if introduced early.

12. **Computer Vision** → New `image_processor.py` service, new `vision_agent.py`, new `site_observations` table, new upload endpoint

**Risk:** Medium. New external dependency (vision API). No existing code is modified.

---

### Summary Table

| Phase | Capabilities | New Tables | New Files | Modified Files | Risk |
|---|---|---|---|---|---|
| 0 (Debt) | Bug fixes | 0 | 0 | 3 | Very Low |
| 1 | Schedule Engine, Standards Engine | 1 | 0 | 3 | Low |
| 2 | Living Intelligence, Cross-Agent | 1 | 1 | 3 | Medium |
| 3 | Supply Chain, Procurement | 0 | 0 | 3 | Low |
| 4 | Commissioning, Executive Dashboard | 0 | 0 | 4 | Medium |
| 5 | Computer Vision | 2 | 2 | 2 | Medium |

> **Golden Rule:** Every new capability follows the same three patterns already established in this codebase:
> 1. New agent file → imported into `orchestrator_agent.py` → new node in the LangGraph graph
> 2. New router file → registered via `_register_router()` in `main.py`
> 3. New DB table → added via `_migrate_new_tables()` pattern in `schema.py`

No existing API, schema, agent interface, or frontend route needs to be deleted or restructured to implement any of the 9 capabilities.
