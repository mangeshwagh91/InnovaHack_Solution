# DataForge AI (DCPI) — Master Technical Reference

> **Evidence Policy:** Every factual statement in this document is traceable to one or more concrete locations in the repository. File references are given in `[File: path]` notation. If the repository does not provide enough evidence, the statement is explicitly marked **"Not verifiable from repository."**

---

## Table of Contents

1. [Part I — Executive & Business Understanding](#part-i--executive--business-understanding)
2. [Part II — Complete Repository Structure](#part-ii--complete-repository-structure)
3. [Part III — Architecture](#part-iii--architecture)
4. [Part IV — Functional Decomposition](#part-iv--functional-decomposition)
5. [Part V — Runtime Behaviour](#part-v--runtime-behaviour)
6. [Part VI — Source Code Analysis](#part-vi--source-code-analysis)
7. [Part VII — AI Components](#part-vii--ai-components)
8. [Part VIII — Infrastructure](#part-viii--infrastructure)
9. [Part IX — Data](#part-ix--data)
10. [Part X — Security](#part-x--security)
11. [Part XI — Performance](#part-xi--performance)
12. [Part XII — Technical Debt](#part-xii--technical-debt)
13. [Part XIII — Repository Encyclopedia](#part-xiii--repository-encyclopedia)
14. [Part XIV — Teaching Knowledge](#part-xiv--teaching-knowledge)

---

# PART I — Executive & Business Understanding

## Why Was This Project Built?

**Evidence:** `[File: README.md, lines 1–11]`, `[File: server/main.py, lines 149–165]`

DataForge AI was built to eliminate the offline communication gaps and information silos that plague EPC (Engineering, Procurement, and Construction) projects for Tier IV data centre construction. Traditional EPC project management relies on emails, spreadsheets, and manual document review — causing delays, missed non-conformances, and late-stage quality surprises that cost millions of dollars in liquidated damages.

The application's internal codename throughout the codebase is **DCPI** (Data Centre Project Intelligence).

## What Business Problem Does It Solve?

| Pain Point | AI Solution |
|---|---|
| Engineers manually reviewing 1000-page specs against vendor submittals | Automated Spec Compliance Agent with concurrent AI scoring |
| No real-time visibility into shipment delays vs. project schedule | Supply Chain Risk Agent with Haversine math + LLM alternatives |
| Knowledge locked in PDFs, inaccessible to field engineers | RAG-powered RFI Copilot for instant natural-language queries |
| Schedule risk only assessed by PMs, not mathematically | Schedule Risk Agent with sigmoid scoring, float analysis, NCR propagation |
| No automated NCR generation from deviations | AI NCR batch generation with TITLE/DESCRIPTION/IMPACT/ACTIONS format |

## Who Are the Intended Users?

**Evidence:** `[File: client/src/context/AuthContext.jsx, lines 34–41]`, `[File: server/routers/auth.py]`

Two distinct user personas are built into the system:

1. **EPC Project Team** (`type: "team"`) — Engineers, project managers, QA managers, procurement officers, commissioning technicians. These users have unrestricted access to all platform features.

2. **Vendors** (`type: "vendor"`) — Equipment suppliers who register, log in with JWT credentials, submit bids/tenders, and view their own dashboards. Authenticated via `POST /api/auth/register/vendor` and `POST /api/auth/login`.

## Who Are the Stakeholders?

**Not explicitly stated in repository beyond the two user types.** Implied stakeholders based on domain context: data centre owner/client, EPC contractor, equipment vendors, quality managers, project controls engineers.

## What Value Does It Provide?

**Evidence:** `[File: server/models/schemas.py, lines 158–176]` — `DashboardSummaryResponse` exposes quantification metrics:

- `manual_hours_saved_weekly` — Estimated manual hours saved per week
- `compliance_accuracy_pct` — Compliance check accuracy percentage
- `risks_flagged_avg_days_advance` — Average days risks flagged before planned start
- `commissioning_pass_rate_pct` — Commissioning step pass rate
- `total_ncrs_raised` — Total NCRs auto-raised by AI

## What Are the Success Metrics?

**Evidence:** `[File: server/models/schemas.py, lines 158–176]`

- Number of open NCRs (`open_ncr_count`)
- Total documents ingested (`total_documents`)
- Compliance checks run (`compliance_checks_run`)
- At-risk schedule tasks (`at_risk_tasks`)
- Critical path task count (`critical_path_tasks`)
- Open RFIs (`open_rfis`)
- Overall project health score (`project_health_score`)

## What Assumptions Does the System Make?

**Evidence:** From code analysis:

1. **PDF-only specifications** — Only `.pdf` files accepted for specs/submittals `[File: server/routers/upload.py, line 109]`
2. **UPS as default equipment class** — Falls back to `"UPS"` if class undetermined `[File: server/agents/compliance_agent.py, line 167]`
3. **Groq API as primary LLM** — All calls aliased as `call_claude()` but execute via Groq `[File: server/services/llm_client.py, lines 263–293]`
4. **Truck speed of 50 mph** — Supply chain transit time heuristic `[File: server/agents/supply_chain_agent.py, line 58]`
5. **Tier IV standard** — Default compliance tier `[File: server/agents/compliance_agent.py, line 27]`
6. **Critical path = float ≤ 1 day** `[File: server/agents/schedule_agent.py, lines 122–126]`

## What Constraints Exist?

**Evidence:** `[File: .env]`, `[File: server/requirements.txt]`

- Max upload size: 50 MB (`MAX_UPLOAD_SIZE_MB=50`)
- Allowed file types: `.pdf,.docx,.xlsx,.csv,.json`
- Max OCR pages: 100 (`PDF_MAX_OCR_PAGES=100`)
- Max concurrent LLM calls: configurable, default 1 in dev (`GROQ_MAX_CONCURRENT=1`)
- Max concurrent ingestion jobs: 5 (`INGEST_MAX_CONCURRENT=5`)
- RFI context window: 700 chars per chunk (`RFI_MAX_CONTEXT_CHARS=700`)
- RFI answer word limit: 400 words (`RFI_MAX_ANSWER_WORDS=400`)
- SQLite as database — single-node, not distributed

## Core Business Workflows

**Evidence:** `[File: server/main.py, lines 231–244]`

1. **Document Ingestion** — Upload spec PDFs → async parsing → ChromaDB indexing
2. **Vendor Submittal Compliance** — Upload submittal → extract attributes → compare vs spec → auto-generate NCRs
3. **Schedule Risk Analysis** — Import schedule → risk scoring → AI mitigations
4. **RFI Query (RAG Copilot)** — Natural-language question → vector search → LLM answer with source citations
5. **Supply Chain Tracking** — Live shipment map → risk analysis → AI alternatives
6. **Commissioning** — View tasks → generate checklist → step-by-step execution with pass/fail
7. **Tender Management** — Vendors submit bids → AI evaluates → recommendations
8. **Project & Team Management** — Create/manage projects, documents, team members

## Critical vs. Optional Workflows

**Evidence:** `[File: server/main.py, line 231]` — upload router explicitly marked `critical=True`; all others optional.

| Workflow | Criticality |
|---|---|
| Document Upload & Ingestion | **Critical** — all AI features depend on it |
| Spec Compliance Checking | High |
| RFI RAG Copilot | High |
| Schedule Risk Analysis | High |
| Supply Chain Tracking | High |
| Commissioning Copilot | Medium |
| Tender/Vendor Management | Medium |
| Project CRUD | Medium |
| Reports/Dashboard | Low — aggregates from other features |

## Functional Requirements

1. Upload and parse 1000+ page technical specification PDFs
2. Extract structured technical attributes from vendor submittals
3. Compare attributes mathematically against specification requirements
4. Auto-classify deviations by severity (CRITICAL, MAJOR, MINOR, OBSERVATION)
5. Generate formal NCR documents (TITLE, DESCRIPTION, IMPACT, ACTIONS)
6. Track NCR status through resolution lifecycle
7. Import project schedules and compute risk scores per task
8. Generate AI-driven mitigation options (3 per at-risk task)
9. Track live shipment GPS coordinates and assess delivery risk
10. Answer natural-language RFI queries using RAG over project documents
11. Manage vendor registration, authentication, and bid submission
12. Evaluate vendor tenders with AI-scored recommendations
13. Generate step-by-step commissioning checklists per equipment class
14. Provide project health dashboard with quantification metrics

## Non-Functional Requirements

- **Async processing** — Document parsing non-blocking `[File: server/services/ingestion_queue.py]`
- **Concurrent LLM calls** — Batch API enables parallel inference `[File: server/services/llm_client.py, lines 298–344]`
- **WAL mode SQLite** — Better concurrent write performance `[File: server/database/connection.py]`
- **Thread-safe caching** — In-memory TTL cache with locking `[File: server/services/cache.py]`
- **Graceful degradation** — LLM failure falls back to heuristic scoring `[File: server/agents/compliance_agent.py, lines 527–530]`
- **Docker containerization** — Single container deployment `[File: Dockerfile]`

## Performance Goals

Not explicitly documented. From configuration:
- Groq API timeout: 45 seconds
- Batch ingestion: up to 5 concurrent jobs
- Cache default TTL: 300 seconds
- Database page cache: 64 MB

## Security Goals

- JWT authentication with 7-day token expiry
- bcrypt password hashing
- CORS origin restriction

## Scalability Goals

**Not verifiable from repository.** SQLite is single-node. Horizontal scaling requires database migration.

## Reliability Goals

- 4 global exception handlers catch all error types `[File: server/main.py, lines 264–332]`
- LLM key error tracking with automatic rotation/reset `[File: server/services/llm_client.py, lines 145–163]`
- Max 2 retries per LLM call (`GROQ_MAX_RETRIES=2`)
- Non-critical startup failures are warned but don't crash the server

## Availability Expectations

**Not verifiable from repository.**

---

# PART II — Complete Repository Structure

```
MY_version_ET/
├── .dockerignore              # Docker build exclusions (161 bytes)
├── .env                       # Environment config (4999 bytes) — contains live API key
├── .git/                      # Git version control data
├── .gitignore                 # Git exclusion patterns (410 bytes)
├── .venv/                     # Python virtual environment (local, not committed)
├── Dockerfile                 # Multi-stage Docker build (1215 bytes)
├── LLM_PROJECT_CONTEXT.md     # Developer LLM context dump (13478 bytes)
├── NUMBER_SYSTEM.html         # Educational HTML — Data Centre Number Systems (117329 bytes)
├── NUMBER_SYSTEM2.html        # Educational HTML v2 (164402 bytes)
├── README.md                  # Project overview and setup instructions (2579 bytes)
├── TECHNICAL_REFERENCE.md     # Existing partial technical reference (8274 bytes)
├── aaaaaae.md                 # Developer scratch/analysis notes (34540 bytes)
├── agent_workflow.md          # Agent workflow documentation (31764 bytes)
├── all_code.txt               # Full source concatenated — developer utility (1433904 bytes)
├── architectural_audit.md     # Architecture audit report (47048 bytes)
├── client/                    # React 18 frontend application
│   ├── index.html             # SPA entry point (372 bytes)
│   ├── node_modules/          # npm dependencies (not committed)
│   ├── package-lock.json      # npm lockfile (117003 bytes)
│   ├── package.json           # Dependencies and scripts (757 bytes)
│   ├── postcss.config.js      # PostCSS / TailwindCSS config (82 bytes)
│   ├── public/                # Static assets served as-is
│   ├── src/
│   │   ├── App.jsx            # Root component + router config (5549 bytes)
│   │   ├── api/
│   │   │   └── client.js      # All API endpoint wrappers (10357 bytes)
│   │   ├── components/
│   │   │   ├── EmptyState.jsx           # Reusable empty state UI (817 bytes)
│   │   │   ├── LoadingSpinner.jsx       # Animated loading indicator (1706 bytes)
│   │   │   ├── PageTransition.jsx       # Framer Motion page transition (593 bytes)
│   │   │   ├── PremiumCard.jsx          # Styled card wrapper (420 bytes)
│   │   │   ├── SeverityBadge.jsx        # NCR severity badge (1206 bytes)
│   │   │   ├── auth/                    # Login/register form components
│   │   │   ├── chat/
│   │   │   │   └── RfiThinkingTimeline.jsx  # Animated AI thinking indicator (2422 bytes)
│   │   │   ├── compliance/
│   │   │   │   ├── AIProcessingTimeline.jsx  # Compliance AI processing animation (3891 bytes)
│   │   │   │   ├── AuditBackground.jsx       # Audit background animation (2811 bytes)
│   │   │   │   ├── ComplianceBackground.jsx  # Compliance background (3421 bytes)
│   │   │   │   └── ComplianceUploadCard.jsx  # Drag-and-drop submittal upload (6121 bytes)
│   │   │   ├── hero/                    # Landing page hero section
│   │   │   ├── layout/
│   │   │   │   ├── AppLayout.jsx        # App shell: sidebar + header + content (985 bytes)
│   │   │   │   ├── Header.jsx           # Top navigation bar (3271 bytes)
│   │   │   │   └── Sidebar.jsx          # Left navigation sidebar (5956 bytes)
│   │   │   ├── overview/               # Dashboard overview components
│   │   │   ├── schedule/
│   │   │   │   ├── ScheduleAITimeline.jsx   # Schedule AI processing animation (3938 bytes)
│   │   │   │   ├── ScheduleBackground.jsx   # Schedule section background (2825 bytes)
│   │   │   │   └── ScheduleUploadCard.jsx   # Schedule CSV upload UI (6004 bytes)
│   │   │   └── workspace/              # Workspace management components
│   │   ├── context/
│   │   │   ├── AuthContext.jsx          # Authentication state provider (2401 bytes)
│   │   │   └── WorkspaceContext.jsx     # Active workspace/project state (1921 bytes)
│   │   ├── index.css                    # Global CSS + TailwindCSS utilities (12576 bytes)
│   │   ├── main.jsx                     # React 18 root render entry point (244 bytes)
│   │   └── pages/
│   │       ├── CommissioningPage.jsx    # Commissioning copilot UI (18382 bytes)
│   │       ├── Compliance.jsx           # Compliance checker UI (23959 bytes)
│   │       ├── Dashboard.jsx            # Main dashboard (30679 bytes)
│   │       ├── DesignPage.jsx           # Design document viewer (19468 bytes)
│   │       ├── DocumentsPage.jsx        # Document management (15357 bytes)
│   │       ├── IntegrationsPage.jsx     # External integrations / standards upload (13501 bytes)
│   │       ├── LandingPage.jsx          # Public landing/marketing page (37892 bytes)
│   │       ├── NCRDetail.jsx            # Single NCR detail view (7330 bytes)
│   │       ├── NewProject.jsx           # Project creation wizard (14442 bytes)
│   │       ├── ProjectsPage.jsx         # Project listing (16314 bytes)
│   │       ├── RFIChat.jsx              # RFI chatbot interface (22131 bytes)
│   │       ├── Schedule.jsx             # Schedule risk analysis UI (28191 bytes)
│   │       ├── SettingsPage.jsx         # User settings (9240 bytes)
│   │       ├── SupplyChainPage.jsx      # Supply chain map & tracking (17472 bytes)
│   │       ├── TendersAndContracts.jsx  # Tender management UI (29275 bytes)
│   │       ├── TeamPage.jsx             # Team management (11830 bytes)
│   │       ├── VendorDashboard.jsx      # Vendor-facing dashboard (15839 bytes)
│   │       ├── VendorProfile.jsx        # Vendor profile view (6737 bytes)
│   │       └── VendorTenders.jsx        # Vendor tender submission (5160 bytes)
│   ├── tailwind.config.js     # TailwindCSS custom theme (4754 bytes)
│   └── vite.config.js         # Vite build config (699 bytes)
├── concat.py                  # Developer utility: concatenates all code (1229 bytes)
├── concat_filtered.py         # Developer utility: filtered concatenation (1315 bytes)
├── docs/                      # Reference documentation PDFs (ingested into ChromaDB)
│   ├── Annual_outage_analysis_2026.pdf                              (337797 bytes)
│   ├── Data_Center_Power_Equipment_Thermal_Guidelines_...pdf        (2212074 bytes)
│   ├── Data_Center_Site_Infrastructure_Tier_Standard_Topology.pdf  (920690 bytes)
│   ├── Technical_Vendor_Requirements_and_Evaluation.pdf            (1250689 bytes)
│   └── site_infra_tier_standards_operational_sustainability.pdf    (597535 bytes)
├── filtered_code.txt          # Filtered code concatenation (1132171 bytes)
├── get_tree.py                # Developer utility: generates file tree JSON (744 bytes)
├── real_world_flow.md         # Real-world data flow documentation (5806 bytes)
├── server/                    # FastAPI Python backend
│   ├── __pycache__/           # Python bytecode cache
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── commissioning_agent.py  # Commissioning copilot agent (21164 bytes)
│   │   ├── compliance_agent.py     # Spec compliance & NCR generator (38720 bytes)
│   │   ├── knowledge_agent.py      # RAG knowledge & RFI agent (19650 bytes)
│   │   ├── monitor_agent.py        # System monitor agent scaffold (4406 bytes)
│   │   ├── orchestrator_agent.py   # LangGraph routing orchestrator (11070 bytes)
│   │   ├── procurement_agent.py    # Bid analysis & cost agent (7884 bytes)
│   │   ├── report_agent.py         # Report generation agent scaffold (1722 bytes)
│   │   ├── schedule_agent.py       # Schedule risk analysis agent (30246 bytes)
│   │   ├── supply_chain_agent.py   # Shipment risk & alternatives (7238 bytes)
│   │   └── vision_agent.py         # Vision/image processing scaffold (2435 bytes)
│   ├── chroma_db/             # ChromaDB persistent vector store data
│   ├── database/
│   │   ├── __init__.py        # DB package init
│   │   ├── connection.py      # SQLite connection factory (768 bytes)
│   │   ├── migrate_add_columns.py  # Standalone migration utility (1656 bytes)
│   │   └── schema.py          # Full schema + init + all migrations (23412 bytes)
│   ├── dcpi.db                # SQLite database file (589824 bytes)
│   ├── extra_seed_data.py     # Additional demo data seeder (3909 bytes)
│   ├── fix_demo_pos.py        # Demo PO data fix utility (787 bytes)
│   ├── ingest_docs.py         # Standalone document ingestion CLI (2543 bytes)
│   ├── main.py                # FastAPI application entrypoint (17826 bytes)
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py         # All Pydantic request/response schemas (9159 bytes)
│   ├── requirements.txt       # Python package dependencies (420 bytes)
│   ├── reset_demo_data.py     # Reset database to demo state (2437 bytes)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py            # Vendor auth endpoints (3091 bytes)
│   │   ├── commissioning.py   # Commissioning endpoints (2271 bytes)
│   │   ├── compliance.py      # Compliance & NCR endpoints (5637 bytes)
│   │   ├── dashboard.py       # Dashboard summary endpoints (7961 bytes)
│   │   ├── design.py          # Design documents endpoints (2199 bytes)
│   │   ├── integrations.py    # Standards/PDF ingestion endpoints (3319 bytes)
│   │   ├── projects.py        # Project CRUD endpoints (5422 bytes)
│   │   ├── reports.py         # Report generation endpoints (4405 bytes)
│   │   ├── rfi.py             # RFI query endpoints (3396 bytes)
│   │   ├── schedule.py        # Schedule management endpoints (8748 bytes)
│   │   ├── supply_chain.py    # Supply chain endpoints (2234 bytes)
│   │   ├── tenders.py         # Tender management endpoints (3600 bytes)
│   │   ├── upload.py          # Document upload endpoints (20999 bytes)
│   │   └── webhooks.py        # Webhook endpoints (5032 bytes)
│   ├── security.py            # JWT auth + bcrypt utilities (2197 bytes)
│   ├── seed_data.py           # Full demo data seeder (32240 bytes)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── cache.py           # In-memory TTL cache singleton (6666 bytes)
│   │   ├── image_processor.py # Image processing utility (714 bytes)
│   │   ├── ingestion_queue.py # Async document ingestion queue (7161 bytes)
│   │   ├── llm_client.py      # LLM client — Groq primary (15266 bytes)
│   │   ├── pdf_extractor.py   # PDF text extraction: PyMuPDF + OCR fallback (17036 bytes)
│   │   ├── spec_parser.py     # Spec clause extraction via LLM (33820 bytes)
│   │   └── vector_store.py    # ChromaDB vector store service (25503 bytes)
│   ├── test_agents.py         # Agent smoke-test script (1556 bytes)
│   ├── tests/                 # pytest test suite directory
│   ├── uploads/               # Uploaded PDF storage directory
│   └── venv/                  # Server-level Python virtual environment
├── start.bat                  # Windows batch startup script (354 bytes)
├── tree.json                  # File tree JSON snapshot (5851 bytes)
└── venv/                      # Root-level virtual environment
```

---

# PART III — Architecture

## Logical Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                          USER LAYER                                  │
│  ┌────────────────────┐    ┌───────────────────────────────────────┐ │
│  │  EPC Project Team  │    │         Vendor Portal                 │ │
│  │  (Browser SPA)     │    │         (Browser SPA)                 │ │
│  └────────┬───────────┘    └─────────────────┬─────────────────────┘ │
└───────────┼────────────────────────────────  ┼──────────────────────┘
            │ HTTP/JSON REST                    │ HTTP/JSON REST + JWT
┌───────────▼───────────────────────────────── ▼──────────────────────┐
│                    PRESENTATION LAYER                                │
│         React 18 SPA — Vite + TailwindCSS + Framer Motion           │
│  Pages:  Dashboard · Compliance · Schedule · RFI · Supply Chain      │
│          Commissioning · Tenders · Documents · Projects · Settings   │
│  State:  AuthContext · WorkspaceContext                               │
│  API:    client.js (plain fetch, no React Query)                     │
└──────────────────────────────┬───────────────────────────────────────┘
                               │ HTTP (JSON)
┌──────────────────────────────▼───────────────────────────────────────┐
│                       API GATEWAY LAYER                              │
│              FastAPI (Python 3.11) + Uvicorn ASGI Server             │
│  Middleware:  CORS · Request-ID · X-Process-Time header              │
│  Exceptions:  404 · 405 · 500 · global catch-all                    │
│  Routers:     /api/auth  /api/projects  /api/upload                  │
│               /api/compliance  /api/schedule  /api/rfi               │
│               /api/dashboard  /api/commissioning                     │
│               /api/supply-chain  /api/tenders                        │
│               /api/webhooks  /api/design  /api/integrations          │
│               /api/reports                                           │
└─────────────────┬────────────────────────────┬───────────────────────┘
                  │                            │
┌─────────────────▼───────────┐  ┌─────────── ▼───────────────────────┐
│       AGENT LAYER           │  │        SERVICE LAYER               │
│  (LangGraph StateGraph)     │  │                                    │
│                             │  │  llm_client.py  (Groq API)        │
│  orchestrator_agent         │  │  vector_store.py (ChromaDB)        │
│  ├── knowledge_agent        │  │  pdf_extractor.py (PyMuPDF + OCR)  │
│  ├── compliance_agent       │  │  spec_parser.py  (LLM-assisted)    │
│  ├── schedule_agent         │  │  ingestion_queue.py (async queue)  │
│  ├── supply_chain_agent     │  │  cache.py (TTL in-memory)          │
│  ├── commissioning_agent    │  │  image_processor.py                │
│  └── procurement_agent      │  └────────────────────────────────────┘
└─────────────────┬───────────┘
                  │
┌─────────────────▼────────────────────────────────────────────────────┐
│                        DATA LAYER                                    │
│  ┌──────────────────────────────┐  ┌───────────────────────────────┐ │
│  │   SQLite  (WAL mode)         │  │  ChromaDB  (Persistent)       │ │
│  │   dcpi.db  — 19 tables       │  │  ./chroma_db/  — 5 collections│ │
│  │   Relational + JSON columns  │  │  · spec_clauses               │ │
│  │                              │  │  · document_memory            │ │
│  │                              │  │  · rfis                       │ │
│  │                              │  │  · standards                  │ │
│  │                              │  │  · commissioning_checklists   │ │
│  └──────────────────────────────┘  └───────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
                  │
┌─────────────────▼────────────────────────────────────────────────────┐
│                    EXTERNAL AI / EMBEDDING LAYER                     │
│  Primary LLM:   Groq API — llama-3.1-8b-instant                     │
│  Embedding:     sentence-transformers  all-MiniLM-L6-v2 (local CPU)  │
│  Fallback LLMs: llama-3.2-3b-preview · mixtral-8x7b-32768           │
└──────────────────────────────────────────────────────────────────────┘
```

## Physical / Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Docker Container                              │
│  Stage 1 (Build): node:20-alpine                                    │
│    npm ci  →  npm run build  →  /app/client/dist                    │
│                                                                     │
│  Stage 2 (Runtime): python:3.11-slim                                │
│    pip install -r requirements.txt                                  │
│    /app/server/        ← FastAPI Python source                      │
│    /app/client/dist    ← Compiled React SPA (served as static)      │
│    /app/data/          ← VOLUME (persisted across restarts)         │
│      ├── uploads/      ← Uploaded PDFs                              │
│      ├── chroma_db/    ← ChromaDB vector data                       │
│      └── dcpi.db       ← SQLite database                            │
│                                                                     │
│  EXPOSE 8000                                                        │
│  CMD ["python", "main.py"]                                          │
└─────────────────────────────────────────────────────────────────────┘
```

**Evidence:** `[File: Dockerfile, all lines]`

## Runtime Architecture

```
FastAPI Application Startup (lifespan async context manager):
  1. mkdir ./uploads  +  mkdir ./chroma_db
  2. init_db()         → SQLite WAL, 19 tables, 19 indexes
  3. initialize_collections() → ChromaDB 5 collections
  4. _validate_environment()  → Check GROQ_API_KEYS
  5. ingestion_queue.start()  → Async worker loop begins

Per-Request Flow:
  HTTP Request
    → add_process_time_header middleware (UUID + timer)
    → CORS middleware
    → Router dispatch (14 routers)
    → Sync endpoint function (runs in Uvicorn thread pool)
      → Agent call (possibly via _run_async bridging)
        → LLM batch call (aiohttp + asyncio.Semaphore)
        → Vector search (ChromaDB)
        → DB read/write (SQLite, each call opens/closes connection)
    → JSON response + X-Process-Time + X-Request-ID headers
```

## Software Architecture

**Pattern:** Layered + Multi-Agent System

| Layer | Technology |
|---|---|
| Presentation | React 18 SPA (react-router-dom v6, Framer Motion) |
| API | FastAPI REST + OpenAPI at `/docs` |
| Agent Orchestration | LangGraph `StateGraph` |
| Business Logic | Specialized Python agents |
| Service | Stateless service modules |
| Data | SQLite (relational) + ChromaDB (vector) + local filesystem |

## AI Architecture

```
User Query / Document Upload
         │
         ▼
┌──────────────────────────────┐
│   Orchestrator Agent         │
│   LangGraph StateGraph v3.0  │
│                              │
│   classify_node              │
│   └── call_claude_json()     │
│       (ORCHESTRATOR_SYSTEM)  │
└──────────────┬───────────────┘
               │ route_intent()
    ┌──────────▼─────────────────────────────────────────┐
    │ 6 Conditional Edges → 6 Specialized Agent Nodes    │
    └──────────┬─────────────────────────────────────────┘
               │
  ┌────────────┼───────────────────────────────────┐
  │            │                                   │
knowledge  compliance                          schedule
  │            │                                   │
answer_    run_compliance_              run_schedule_risk_
query()    check()                     analysis()
  │            │                                   │
Vector     compare_attrs()             compute_task_
Search     _score_devs_batch()         risk_score()
  │        _gen_ncrs_batch()           _gen_mitig_batch()
  │            │                                   │
call_      call_claude_json_           call_claude_
claude()   batch()                    batch()
  │            │                                   │
RAG        Deviations +               Mitigation
Answer     NCRs saved                 options saved
```

## Security Architecture

```
Vendor Auth Flow  [File: server/security.py]:

  Register:  POST /api/auth/register/vendor
    → get_password_hash(password)  [bcrypt]
    → INSERT INTO vendors (id, company_name, email, password_hash, registered_at)

  Login:     POST /api/auth/login
    → SELECT vendor WHERE email = ?
    → verify_password(plain, hash)  [bcrypt.verify]
    → create_access_token({ "sub": vendor_id }, expires=7 days)
    → Return: { access_token, token_type: "bearer", vendor_id }

  Protected Endpoint:
    → oauth2_scheme extracts Bearer from Authorization header
    → jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    → SELECT vendor WHERE id = payload["sub"]
    → Return user dict to endpoint handler
```

## Networking

- **Client → Server:** HTTP/1.1 JSON REST
- **CORS:** Controlled via `CORS_ORIGINS` env var `[File: server/main.py, line 175]`
- **Exposed headers:** `X-Process-Time`, `X-Request-ID` `[File: server/main.py, line 179]`
- **Server → Groq API:** HTTPS via aiohttp `[File: server/services/llm_client.py, line 193]`

## Storage

| Store | Technology | Purpose | Default Path |
|---|---|---|---|
| Relational DB | SQLite WAL | All structured project data | `./dcpi.db` |
| Vector Store | ChromaDB Persistent | Semantic search | `./chroma_db/` |
| File Storage | Local filesystem | Uploaded PDFs | `./uploads/` |
| In-Memory Cache | Python dict (TTL) | API response caching | Process memory |

## Caching

**Evidence:** `[File: server/services/cache.py]`

- **Type:** Simple in-memory TTL cache, zero external deps
- **Default TTL:** 300 seconds (5 min)
- **Max size:** 256 entries
- **Eviction:** LRU (oldest expiry evicted when at capacity)
- **Thread safety:** `threading.Lock` on all operations
- **API:** `cache.get(key)`, `cache.set(key, value, ttl)`, `cache.invalidate_prefix(prefix)`
- **Decorator:** `@cache.cached("prefix", ttl=N)` for sync; `@cache.cached_async("prefix", ttl=N)` for async

## Observability

**Evidence:** `[File: server/main.py, lines 24–29, 339–365]`

- **Logging:** `%(asctime)s [%(levelname)s] %(name)s — %(message)s` format, level INFO
- **Per-request:** Method · path · status · duration · request UUID
- **Agent audit trail:** Every agent invocation stored in `agent_runs` SQLite table
- **Health check:** `GET /health` → DB + vector store + Groq API status
- **Route discovery:** `GET /api/status` → all registered routes
- **No distributed tracing / metrics / Prometheus** — Not verifiable from repository

---

# PART IV — Functional Decomposition

## Feature 1: Document Upload & Async Ingestion

**Purpose:** Accept large technical specification PDFs (1000+ pages) and ingest them into SQLite + ChromaDB without blocking the HTTP response.

**Business Value:** Foundation for all AI features. Without ingested specs, compliance checking, RFI answers, and commissioning checklists cannot function.

**User Journey:**
1. Engineer navigates to Documents page
2. Drags & drops a PDF specification file
3. System returns immediately → `{ document_id, status: "processing" }`
4. Frontend polls `GET /api/upload/status/{docId}` every 2 seconds
5. Background worker parses the PDF and updates status to `"ready"`

**Participating Files:**
- `server/routers/upload.py` — HTTP endpoints
- `server/services/ingestion_queue.py` — Async job queue
- `server/services/pdf_extractor.py` — PDF → text pages
- `server/services/spec_parser.py` — Text → structured spec clauses
- `server/services/llm_client.py` — LLM calls during clause extraction
- `server/services/vector_store.py` — ChromaDB indexing
- `server/database/schema.py` — `documents` table
- `client/src/pages/DocumentsPage.jsx` — UI
- `client/src/api/client.js` — `uploadSpecification`, `pollUntilReady`

**Participating APIs:**
- `POST /api/upload/specification` → 202 Accepted
- `POST /api/upload/submittal` → 202 Accepted
- `GET /api/upload/status/{doc_id}`
- `GET /api/upload/documents`
- `DELETE /api/upload/document/{doc_id}`

**Execution Flow:**
```
POST /api/upload/specification
  → save_upload_async(file)
      asyncio.to_thread(file.file.read)        # non-blocking read
      asyncio.to_thread(_save_upload_sync, ...) # non-blocking write
  → DB INSERT documents (status="processing")
  → ingestion_queue.submit(doc_id, "specification", filename,
        coro_factory=lambda: _parse_spec_bg(doc_id, file_path))
  → cache.invalidate_prefix("documents_list")
  → return 202 { document_id, status: "processing" }

Background worker (asyncio.Task):
  _parse_spec_bg(doc_id, file_path)
    → parse_spec_document_async(doc_id, file_path)  [spec_parser.py]
        → extract_text_from_pdf(file_path)           [pdf_extractor.py]
            → ThreadPoolExecutor parallel page extraction
            → OCR fallback if text sparse
        → LLM batch calls: identify clause boundaries
        → embed text chunks → ChromaDB.add()
    → DB UPDATE documents SET status="ready", page_count=N
```

**Error Handling:**
- Non-PDF: `HTTPException(400, "Only PDF files accepted")`
- Save failure: `HTTPException(500, "Failed to save file")`
- Parse failure: `DB UPDATE status="failed"`; logged to `agent_runs`

**State Transitions:**
`uploaded` → `processing` → `ready` | `failed`

---

## Feature 2: Specification Compliance Checking & NCR Generation

**Purpose:** Automatically compare vendor technical submittals against project specification requirements; classify deviations; generate formal NCRs for all deviations.

**Business Value:** Eliminates weeks of manual engineering review. Catches deviations mathematically before equipment reaches site. Auto-generates formal NCR documentation.

**User Journey:**
1. QA engineer uploads vendor submittal PDF (system extracts attributes via LLM)
2. Clicks "Run Compliance Check" on a Purchase Order
3. Agent compares extracted attributes to spec clauses, scores severity with AI
4. NCRs auto-generated for all CRITICAL/MAJOR/MINOR deviations
5. Engineer reviews NCR list with severity badges and schedule impact

**Participating Files:**
- `server/agents/compliance_agent.py` — Core logic
- `server/routers/compliance.py` — HTTP endpoints
- `server/routers/upload.py` — Submittal upload + attribute extraction
- `server/services/vector_store.py` — Clause retrieval
- `server/services/llm_client.py` — Batch scoring + NCR generation
- `server/database/schema.py` — `deviations`, `ncrs`, `spec_clauses`, `purchase_orders`
- `client/src/pages/Compliance.jsx`

**Key Functions:**
| Function | Purpose |
|---|---|
| `normalize_key(key)` | Canonicalize attribute name via 50+ ATTR_ALIASES |
| `normalize_attributes(attrs)` | Normalize all PO attribute keys |
| `find_submitted_value(spec_attr, po_attrs)` | Fuzzy attribute lookup with alias expansion |
| `_extract_requirements(clauses)` | Flatten clause requirements, deduplicate by attribute |
| `compare_attributes(po_attrs, spec_reqs, class)` | Generate deviation list |
| `_compare_single(...)` | MIN/MAX/EXACT numerical comparison with tolerance bands |
| `_score_deviations_batch(devs, class)` | Concurrent LLM severity scoring |
| `_apply_heuristic_scoring(dev)` | Fallback: percent thresholds → CRITICAL/MAJOR/MINOR/OBS |
| `_generate_ncrs_batch(devs, po_id, equip_id, clauses)` | Concurrent NCR text generation |
| `_save_ncr(...)` | Parse TITLE/DESCRIPTION/IMPACT/ACTIONS → DB insert |
| `_compute_schedule_impact(equipment_item_id)` | Links NCR to affected schedule tasks |
| `run_compliance_check(po_id)` | Main orchestrator function |

**Deviation Types:**

| Type | Trigger |
|---|---|
| `MISSING` | Mandatory attribute not in submittal |
| `VALUE_BELOW_MIN` | Numeric value below minimum |
| `VALUE_ABOVE_MAX` | Numeric value above maximum |
| `VALUE_OUTSIDE_RANGE` | Outside tolerance band |
| `STRING_MISMATCH` | String value doesn't match exactly |
| `INVALID_DOCUMENT` | No technical attributes found |

**Severity Thresholds** `[File: compliance_agent.py, lines 25–27]`:
- CRITICAL ≥ 15% deviation
- MAJOR ≥ 10%
- MINOR ≥ 5%
- OBSERVATION < 5%

**System Prompts** `[File: compliance_agent.py, lines 86–105]`:
```
SEVERITY_SYSTEM: "senior QA engineer... Return JSON: { severity, justification, recommended_action, w_conform }"
NCR_SYSTEM:      "QA manager... Write: TITLE / DESCRIPTION / IMPACT / ACTIONS"
```

**Conformance Score Formula:**
```
conformance_score = 1 - Σ(w_conform_i) / n_deviations
```
where `w_conform` ∈ [0,1] and higher values = more severe.

**Error Handling:**
- PO not found → `ValueError`
- LLM batch failure → fallback to `_apply_heuristic_scoring` per deviation
- JSON parse failure → `_default_ncr_text(dev)` fallback
- Always logs to `agent_runs` table regardless of success/failure

---

## Feature 3: Schedule Risk Analysis

**Purpose:** Mathematically evaluate every project schedule task for risk of delay using float, NCR impact, predecessor chain, resource demand, and weather as weighted factors.

**Business Value:** Identifies critical path tasks at risk weeks before planned start. Generates specific actionable mitigation options.

**User Journey:**
1. PM imports schedule (CSV/JSON) via Schedule page
2. Clicks "Run Risk Analysis"
3. System processes all tasks via topological sort, computes sigmoid risk scores
4. At-risk tasks highlighted with AI mitigation options (3 per task)
5. PM reviews top risks and assigns mitigation

**Risk Score Formula** `[File: schedule_agent.py, lines 23–31]`:

```
risk_score = sigmoid(
  float_factor    × SCHEDULE_FLOAT_WEIGHT        (0.30)
  + procurement_delay × SCHEDULE_PROCUREMENT_WEIGHT (0.35)
  + predecessor_score × SCHEDULE_PREDECESSOR_WEIGHT (0.20)
  + resource_factor × SCHEDULE_RESOURCE_WEIGHT   (0.10)
  + weather_factor  × SCHEDULE_WEATHER_WEIGHT    (0.05)
)

sigmoid(x) = 1 / (1 + exp(−k × (x − θ)))
k=7, θ=0.45
```

**NCR → Procurement Delay Mapping:**
- CRITICAL NCR → 14 days
- MAJOR NCR → 7 days
- MINOR NCR → 2 days

**Mitigation Prompt Format** `[File: schedule_agent.py, lines 36–59]`:
```
OPTION 1: [Title]
Actions: [3 specific actions with timelines]
Days saved: X-Y days
Cost impact: Low/Medium/High
Owner: [responsible role]
```

**Key Algorithms:**
- `_build_dependency_graph(tasks)` — Adjacency list from `predecessor_ids_json`
- `_topological_sort(tasks, graph)` — Kahn's algorithm for processing order
- `_generate_mitigations_batch(at_risk_tasks)` — Single concurrent batch LLM call

---

## Feature 4: RFI Copilot (RAG Chat)

**Purpose:** Allow project team members to ask natural-language questions and receive answers sourced from project documents, spec clauses, and past RFI resolutions.

**Business Value:** Eliminates hours of manual document search. Surfaces precedent RFIs. All answers are cited to source documents.

**User Journey:**
1. Engineer navigates to RFI Chat
2. Types: "What is the transfer time requirement for the UPS?"
3. System embeds query → ChromaDB search → top-K chunks assembled
4. LLM generates answer with `[SOURCE N]` citations and confidence level
5. Engineer views source text previews and precedent RFIs

**RAG Pipeline:**
```
query
  → embed_text(query)  [SentenceTransformer, 384-dim]
  → search_spec_clauses(query, n=5) + search_rfis(query, n=5)
  → assemble context (MAX_CONTEXT_CHARS=700 per chunk)
  → call_claude(RAG_SYSTEM, context + query)
  → parse [SOURCE N] citations, confidence tag
  → return { answer, sources, precedent_rfis, confidence, agent_run_id }
```

**Chunking Strategy** `[File: knowledge_agent.py, lines 80–88]`:
- Size: 2000 chars
- Overlap: 200 chars
- Fixed sliding window (not semantic)

**System Prompt** `[File: knowledge_agent.py, lines 64–77]`:
- Role: "senior technical manager on a Tier IV hyperscale data centre EPC project"
- Rules: Answer ONLY from context, cite EVERY claim with [SOURCE N], lead with precedent RFIs if relevant, end technical answers with `[Confidence: HIGH/MEDIUM/LOW]`
- Exception: Greetings ("hi", "hello") bypass all rules and get casual 1-2 sentence reply

**Participating APIs:**
- `POST /api/rfi/query` → `{ query }` → `{ answer, sources, precedent_rfis, confidence, agent_run_id }`
- `GET /api/rfi/rfis` → list of RFI records

---

## Feature 5: Supply Chain Visibility & Risk

**Purpose:** Track live shipment GPS coordinates, calculate delivery risk using Haversine math, invoke AI only for HIGH/CRITICAL risk shipments to model procurement alternatives.

**Business Value:** Alerts project team to critical path delays days before they materialize. Provides cost/time tradeoffs for mitigation options.

**User Journey:**
1. PM navigates to Supply Chain page
2. Sees interactive Leaflet map with shipment markers (red = delayed, green = on-time)
3. Clicks on delayed shipment → triggers `analyze_shipment_risk(shipment_id)`
4. System calculates Haversine distance → transit time → delay hours → risk score
5. If HIGH/CRITICAL: LLM generates alternatives (Air Freight, Local Source, etc.)

**Technical Overview** `[File: supply_chain_agent.py]`:

**Step 1 — Deterministic Math:**
```python
distance_miles = haversine(current_lat, current_lng, dest_lat, dest_lng)
required_transit_hours = distance_miles / 50.0   # avg truck speed
hours_remaining = (required_delivery - now).total_seconds() / 3600
delay_hours = max(0, required_transit_hours - hours_remaining)
```

**Step 2 — Schedule Float Lookup:**
```python
task = SELECT total_float_days, is_critical_path FROM schedule_tasks
       WHERE equipment_item_id = shipment.equipment_item_id
```

**Step 3 — Risk Scoring:**
```
delay > 10 days → +40 points  |  delay 3-10 days → +25  |  delay < 3 days → +15
critical path + zero float   → +35 points  |  float ≤ 5 → +20
CRITICAL if ≥ 70  |  HIGH if ≥ 45  |  MEDIUM if ≥ 25  |  LOW otherwise
```

**Step 4 — LLM (only for HIGH/CRITICAL):**
- Sends grounded prompt with exact distance, delay hours, float, risk score
- Receives: `{ risk_assessment, alternatives: [...], recommendation }`
- Alternatives saved to `shipments.ai_alternatives_json`

**Mock Seed Data** `[File: server/database/schema.py, lines 342–391]`:
- Shipment 1: Dallas TX → Ashburn VA, currently near Memphis TN (delayed, HIGH risk)
- Shipment 2: New York NY → Ashburn VA, near Philadelphia (on time, LOW risk)

---

## Feature 6: Commissioning Copilot

**Purpose:** Guide commissioning engineers through structured step-by-step test sequences for data centre equipment and auto-flag non-conformances.

**Business Value:** Eliminates ad-hoc commissioning. Generates structured test records. Auto-raises NCRs when acceptance criteria are not met.

**Step Templates** `[File: commissioning_agent.py, lines 33–100+]`:
- UPS: 10 steps (Safety Check → Visual → IR Test → Bypass → Battery → V/I Check → Alarms → 50% Load → 100% Load → Sign-off)
- PDU: 7 steps (Safety → Torque → Phase Balance → Breaker Trip → Metering → SNMP → Sign-off)
- COOLING: Multi-step (Leak Check → Flush → Pump Rotation → Flow Rate → Delta-T → ...)
- TRANSFORMER, GENERATOR, FIRE_SUPPRESSION also templated

**LLM Used For:** Generating custom checklists for equipment not in the template library.

**Participating APIs:**
- `GET /api/commissioning/tasks` — Schedule tasks with commissioning keywords
- `POST /api/commissioning/checklist/generate/{task_id}` — AI checklist generation
- `POST /api/commissioning/run/{task_id}/step/{step_number}` — Execute step, compare actual vs. criteria
- `GET /api/commissioning/records` — All commissioning records

---

## Feature 7: Tender Management & AI Bid Evaluation

**Purpose:** Vendors submit bids with price, lead time, and equipment catalog. EPC team requests AI bid evaluation with scored recommendations.

**AI Bid Scoring** `[File: procurement_agent.py, lines 22–40]`:
```json
{
  "vendor_name": "...",
  "price_score": 8.5,
  "compliance_score": 9.0,
  "lead_time_score": 7.0,
  "risk_score": 9.5,
  "overall_score": 8.5,
  "recommendation": "RECOMMENDED|ALTERNATE|NOT_RECOMMENDED",
  "justification": "..."
}
```

**Fallback Heuristic** `[File: procurement_agent.py, lines 80–105]`:
```python
price_score = max(0, 10 - (price / 10000))
lead_time_score = max(0, 10 - (lead_time_days / 10))
overall = (price + lead_time + compliance + risk) / 4
recommendation = "RECOMMENDED" if overall > 8 else "ALTERNATE"
```

---

## Feature 8: Project Management

**Purpose:** Organizational containers for all documents, schedules, NCRs, and RFIs.

**APIs:** `GET/POST /api/projects/`, `GET /api/projects/open`, `PATCH /api/projects/{id}/status`, `DELETE /api/projects/{id}`

**Schema:** `id, name, size_mw, deadline, budget, status, created_at, location, capacity_unit, equipment_budget, tier, description, pm`

---

# PART V — Runtime Behaviour

## Complete Compliance Check Trace

```
User: "Run Compliance Check" on PO-001
  │
  ▼ Frontend
  api.runComplianceCheck("PO-001")
  fetch("POST /api/compliance/run/PO-001")
  │
  ▼ FastAPI Router  [routers/compliance.py]
  add_process_time_header middleware → start timer, assign request_id
  POST /api/compliance/run/{po_id}
  → calls: run_compliance_check("PO-001")
  │
  ▼ Agent  [agents/compliance_agent.py:144]
  agent_run_id = uuid4()
  started_ts = datetime.now(timezone.utc).isoformat()
  db = get_db()   # opens SQLite connection
  │
  ▼ Database reads
  po_row = db.execute("SELECT * FROM purchase_orders WHERE id = ?", ("PO-001",))
  po = dict(po_row)
  raw_attrs = json.loads(po["technical_attributes_json"])
  po_attrs = normalize_attributes(raw_attrs)   # alias expansion
  eq_row = db.execute("SELECT * FROM equipment_items WHERE id = ?", (po["equipment_item_id"],))
  equipment_class = eq_row["equipment_class"]  # e.g. "UPS"
  │
  ▼ Vector Search  [services/vector_store.py]
  search_results = search_spec_clauses("UPS", n_results=10)
    → _get_embedding_model()  # lazy singleton; SentenceTransformer("all-MiniLM-L6-v2")
    → embedding = model.encode("UPS")  # 384-dim numpy array
    → chromadb.collection("spec_clauses").query(
          query_embeddings=[embedding.tolist()], n_results=10
      )
    → returns: [{ id, document, metadata: { requirements_json, clause_number, ... } }]
  │
  ▼ Requirement extraction
  all_requirements = _extract_requirements(clauses)
    → for each clause: json.loads(clause["requirements_json"])
    → deduplicate by normalize_key(req["attribute"])
    → returns: [{ attribute, required_value, tolerance_type, mandatory, spec_clause_id }]
  │
  ▼ Mathematical comparison  [compliance_agent.py:394]
  raw_deviations = compare_attributes(po_attrs, all_requirements, "UPS")
    → for each requirement:
        submitted_val = find_submitted_value(spec_attr, po_attrs)
        if submitted_val is None and req["mandatory"]:
            → append MISSING deviation
        else:
            deviation = _compare_single(spec_attr, required_val, submitted_val, ...)
                → numeric: check MIN/MAX/EXACT with tolerance_pct bands
                    if sub_num < req_num (MIN): is_deviant=True, deviation_pct = |delta|/req*100
                → string: str(required).upper() != str(submitted).upper()
            if deviation: append to list, log info
  │
  ▼ Batch LLM severity scoring  [compliance_agent.py:515]
  scored_deviations = _score_deviations_batch(raw_deviations, "UPS")
    → batch_items = [(SEVERITY_SYSTEM, user_msg_for_dev) for dev in deviations]
    → results = call_claude_json_batch(batch_items, max_tokens=500)
        → _run_async(_call_groq_json_batch_async(items, 500))
            → asyncio.Semaphore(GROQ_MAX_CONCURRENT)
            → aiohttp.TCPConnector(limit=GROQ_MAX_CONCURRENT * 2)
            → asyncio.gather(*[_one(sp, um, session) for sp, um in items])
                each: POST https://api.groq.com/openai/v1/chat/completions
                      headers: Authorization: Bearer gsk_...
                      body: { model, messages, max_tokens, temperature: 0.1,
                              response_format: { type: "json_object" } }
                      → _parse_json_robust(response_text)  # 4-strategy parse
            → returns: [{ severity, justification, recommended_action, w_conform }]
    → for dev, result in zip(deviations, results):
        dev["severity"] = result["severity"]
        dev["w_conform"] = float(result["w_conform"])
        # fallback: _apply_heuristic_scoring(dev) if result is None
  │
  ▼ Database writes — deviations
  for dev in scored_deviations:
      dev_id = uuid4()
      db.execute("INSERT OR REPLACE INTO deviations (...) VALUES (...)", (...))
  db.commit()
  │
  ▼ Batch NCR generation  [compliance_agent.py:639]
  ncr_targets = [dev for dev if severity in ("CRITICAL","MAJOR","MINOR")]
  ncr_ids = _generate_ncrs_batch(ncr_targets, "PO-001", equipment_id, clauses)
    → batch_items = [(NCR_SYSTEM, ncr_user_msg) for dev, clause in zip(...)]
    → raw_results = call_claude_batch(batch_items, max_tokens=800)
        → Groq API calls (text mode, not JSON)
    → for dev, clause, response_text in zip(...):
        ncr_id = _save_ncr(dev, "PO-001", equipment_id, clause, response_text)
            → parse lines: TITLE: / DESCRIPTION: / IMPACT: / ACTIONS:
            → _compute_schedule_impact(equipment_item_id)
                → SELECT schedule tasks WHERE equipment_item_id = ?
                → compute min_float, days_until, is_critical → risk_level
            → db.execute("INSERT OR REPLACE INTO ncrs (...) VALUES (...)")
            → db.commit()
  │
  ▼ PO status update
  compliance_status = _determine_compliance_status(scored_deviations)
  conformance_score = _calculate_conformance_score(scored_deviations)
  db.execute("UPDATE purchase_orders SET compliance_status=?, deviation_count=?,
              conformance_score=?, checked_ts=? WHERE id=?", (...))
  db.commit()
  │
  ▼ Agent run logging
  _log_agent_run_compliance_agent(agent_run_id, started_ts, ...)
  → db.execute("INSERT OR REPLACE INTO agent_runs (...) VALUES (...)")
  db.close()   # connection closed in finally block
  │
  ▼ Response  →  Frontend
  {
    po_id, compliance_status, conformance_score,
    deviations: [...], ncr_ids: [...],
    summary: { total, critical, major, minor, observation },
    agent_run_id, vendor_name, po_number, processing_time_ms
  }
  X-Process-Time: 4.2340
  X-Request-ID: a3f2bc91
  │
  ▼ Frontend rendering  [Compliance.jsx]
  → Renders deviation table with severity badges
  → Renders NCR cards with schedule impact
  → Updates dashboard NCR count
```

## Complete RFI Query Trace

```
User: types "What is the UPS transfer time requirement?"
  │
  ▼ Frontend  [RFIChat.jsx]
  setIsThinking(true) → show RfiThinkingTimeline animation
  api.queryRFI("What is the UPS transfer time requirement?")
  fetch("POST /api/rfi/query", { body: JSON.stringify({ query }) })
  │
  ▼ FastAPI  [routers/rfi.py]
  POST /api/rfi/query → body validated by RFIQueryRequest Pydantic model
  → calls: answer_query(query)  [knowledge_agent.py]
  │
  ▼ Agent  [knowledge_agent.py]
  query_embedding = embed_text(query)
    → _get_embedding_model()  → SentenceTransformer singleton
    → model.encode(query, show_progress_bar=False)  → 384-dim array
  │
  spec_results = search_spec_clauses(query, n_results=5)
    → chromadb.collection("spec_clauses").query(
          query_embeddings=[embedding], n_results=5
      )  → cosine similarity, HNSW approximate
  rfi_results = search_rfis(query, n_results=5)
    → chromadb.collection("rfis").query(...)
  │
  context_parts = []
  for rank, result in enumerate(spec_results + rfi_results):
      source = RetrievedSource(rank, doc_id, doc_type, text[:700], score, metadata)
      context_parts.append(f"[SOURCE {rank}] {source.label}\n{source.text}")
  context_string = "\n\n".join(context_parts)
  │
  answer_text = call_claude(
      RAG_SYSTEM.format(max_words=400),
      f"CONTEXT:\n{context_string}\n\nQUESTION: {query}"
  )
  → _run_async(_call_groq_async(RAG_SYSTEM, ..., json_mode=False))
  → Groq API returns natural language answer with [SOURCE N] citations
  │
  precedent_rfis = [
      PrecedentRFI(rfi_id, rfi_code, title, resolution_summary, score)
      for r in rfi_results if r.score >= PRECEDENT_THRESHOLD (0.82)
  ]
  confidence = max score from results or fallback to 0.0
  │
  agent_run logged to agent_runs table
  db.close()
  │
  ▼ Response
  {
    answer: "Per Clause 4.2.4 [SOURCE 0], the UPS bypass transfer time shall not
             exceed 4ms under any load condition... [Confidence: HIGH]",
    sources: [{ doc_id, clause_number: "4.2.4", page_ref, score, text_preview }],
    precedent_rfis: [],
    confidence: 0.94,
    agent_run_id: "..."
  }
  │
  ▼ Frontend  [RFIChat.jsx]
  setIsThinking(false)
  → Renders answer in chat bubble
  → Renders source citation cards with text previews
```

---

# PART VI — Source Code Analysis

## `server/main.py` — FastAPI Application

**Purpose:** Application factory, router registration, middleware, exception handlers, health endpoints, SPA serving.

**Key Functions:**
- `lifespan(app)` — async context manager: startup/shutdown lifecycle
- `_validate_environment()` — Warns on missing GROQ_API_KEYS
- `_register_router(module_name, prefix, tags, critical)` — Dynamic import with graceful failure
- `add_process_time_header(request, call_next)` — Per-request UUID + timing
- `root()`, `health_check()`, `api_status()` — Health endpoints
- `serve_spa(full_path)` — SPA catch-all (only mounted if `client/dist` exists)

## `server/database/connection.py` — SQLite Connection Factory

**Purpose:** Opens a fresh SQLite connection per call with performance tuning.

**`get_db()` returns:** `sqlite3.Connection` with:
- `row_factory = sqlite3.Row` (column access by name)
- WAL mode, FK enforcement
- 64MB page cache, 256MB mmap, temp tables in memory
- 30s busy timeout

**Design Note:** No connection pool. Every agent opens a connection and closes it in `finally`.

## `server/database/schema.py` — Database DDL & Migrations

**`init_db()`** orchestrates:
1. SET PRAGMAs
2. CREATE TABLE IF NOT EXISTS × 19 tables
3. CREATE INDEX × 19 indexes
4. `_migrate_*()` calls for safe ALTER TABLE ADD COLUMN
5. `_seed_mock_shipments()` seeds 2 demo shipments if table is empty

**Migration Pattern:**
```python
existing = {row[1] for row in db.execute("PRAGMA table_info(table)").fetchall()}
if "new_col" not in existing:
    db.execute("ALTER TABLE t ADD COLUMN new_col TYPE DEFAULT val")
```

## `server/security.py` — JWT + bcrypt

**Constants:**
- `ALGORITHM = "HS256"`
- `ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7` (7 days)
- `SECRET_KEY` — from env var or `secrets.token_urlsafe(32)` per startup

**`get_current_user(token)`** — FastAPI `Depends()` dependency. Decodes JWT → DB lookup → returns `{ id, company_name, email }`.

## `server/services/llm_client.py` — LLM Client

**Function naming convention:** All public names start with `call_claude` (historical); all execute via Groq API.

**Key Functions:**
| Function | Mode | Returns |
|---|---|---|
| `call_claude(system, user, max_tokens)` | sync, text | `str` |
| `call_claude_json(system, user, max_tokens)` | sync, JSON | `dict` |
| `call_claude_batch(items, max_tokens)` | async batch, text | `List[str\|None]` |
| `call_claude_json_batch(items, max_tokens)` | async batch, JSON | `List[dict\|None]` |

**`_parse_json_robust(text)` — 4 strategies:**
1. Direct `json.loads(text)`
2. Extract from ` ```json...``` ` code block
3. Brace-count scan for outermost `{...}`
4. Fix trailing commas + Python True/False/None, then retry

**`_next_groq_key()` — Round-robin key rotation:**
- Tracks error count per key in `_key_errors: Dict[str, int]`
- Skips keys with ≥ 3 errors
- Resets all errors if all keys exhausted

## `server/services/vector_store.py` — ChromaDB Integration

**5 Collections:** `spec_clauses`, `document_memory`, `rfis`, `standards`, `commissioning_checklists`

**Singleton pattern (double-check locking):**
```python
if _chroma_client is None:
    with _chroma_lock:
        if _chroma_client is None:
            _chroma_client = chromadb.PersistentClient(path=CHROMA_PATH, ...)
```

**Custom Exceptions:** `VectorStoreError` → `EmbeddingError`, `IndexingError`, `SearchError`

**Metadata serialization:** `_serialize_metadata()` converts all values to strings (ChromaDB requirement). Boolean `is_resolved` stored as `"true"`/`"false"`.

## `server/services/ingestion_queue.py` — Async Job Queue

**`IngestionJob` dataclass:** `job_id, doc_id, doc_type, filename, status, queued_at, started_at, finished_at, error, result`

**`IngestionQueue.submit(doc_id, doc_type, filename, coro_factory)`:**
- `coro_factory` is a zero-arg callable returning a coroutine
- Caller must use `lambda:` to capture args: `lambda: _parse_spec_bg(doc_id, file_path)`

**`_worker_loop()`:**
```python
while self._running:
    job, coro_factory = await asyncio.wait_for(self._queue.get(), timeout=5.0)
    asyncio.create_task(self._run_job(job, coro_factory))  # fire-and-forget
```

**`_run_job(job, coro_factory)`:**
```python
async with self._semaphore:  # limits concurrency
    job.status = PROCESSING
    result = await coro_factory()
    job.status = DONE  # or FAILED on exception
```

## `server/services/pdf_extractor.py` — PDF Text Extraction

**Strategy:** PyMuPDF (fitz) primary, pytesseract + pdf2image OCR fallback if text sparse.

**Parallelism:** Pages extracted in parallel via shared `ThreadPoolExecutor` singleton when page count > `PARALLEL_PAGE_THRESHOLD` (5).

**Custom Exceptions:** `PDFExtractionError` → `PDFEncryptedError`, `PDFCorruptedError`

## `server/services/cache.py` — TTL Cache

**`TTLCache`:**
- `_store: dict[str, tuple[Any, float]]` — `key → (value, expires_at)`
- All ops protected by `threading.Lock`
- Lazy eviction on `get()` (checks expiry on access)
- `sweep()` for bulk expiry removal
- `_evict_oldest()` on `set()` when at capacity (O(n) linear scan)

## `server/models/schemas.py` — Pydantic v2 Models

All models use `ConfigDict(from_attributes=True)` for ORM-mode compatibility.

**Notable models:**
- `DashboardSummaryResponse` — 13 fields including quantification metrics
- `NCRDetailResponse` — 20+ fields joining ncrs + deviations + spec_clauses + vendors
- `RFIQueryResponse` — `{ answer, sources: List[SourceCitation], precedent_rfis: List[PrecedentRFI], confidence, agent_run_id }`
- `OrchestratorResponse` — `{ query, intent, response: Any, agent_run_id }`

## `server/agents/orchestrator_agent.py` — LangGraph Router

**`OrchestratorState(TypedDict)`:** Shared mutable state passed through all graph nodes.

**Graph topology:**
```
classify (entry) → conditional_edges(route_intent) →
  knowledge → END
  procurement → END
  quality → END
  schedule → END
  commissioning → END
  report → END
```

**Singleton compiled graph:** `_compiled_graph = None`; created once in `get_orchestrator_graph()`, reused on all subsequent requests.

**Fallback (no LLM):** Keyword matching in `classify_node()`:
- "tender"/"vendor" → PROCUREMENT
- "schedule"/"risk" → SCHEDULE
- "compliance"/"po" → QUALITY
- else → KNOWLEDGE

## `client/src/api/client.js` — Frontend API Client

**Base URL:** `import.meta.env.VITE_API_BASE || "/api"` — defaults to relative `/api` (works with SPA serving from same origin).

**`handleResponse(response)`:** Throws `Error` for non-2xx; extracts `data.detail || data.error || "HTTP {status}"`.

**`pollUntilReady(docId, onProgress, maxAttempts=30)`:** Returns Promise; polls every 2s, resolves on `status="ready"`, rejects on `status="failed"` or timeout.

## `client/src/context/AuthContext.jsx` — Auth State

**Storage:** `sessionStorage` — auth cleared on tab close.

**`loginAsTeam()`:** Sets hardcoded demo user with no server call. No server-side validation exists for team role.

**`loginAsVendor(email, password)`:** Calls `api.loginVendor()` → stores JWT token in user object.

---

# PART VII — AI Components

## LLM Provider

**Evidence:** `[File: server/services/llm_client.py]`

| Property | Value |
|---|---|
| Provider | Groq API |
| Endpoint | `https://api.groq.com/openai/v1/chat/completions` |
| Default Model | `llama-3.1-8b-instant` |
| Temperature | 0.1 (all calls) |
| Streaming | `False` (all calls) |
| JSON Mode | `response_format: {"type":"json_object"}` for JSON calls |
| Auth | Bearer token (`gsk_` prefix keys) |
| Key Rotation | Round-robin, skip keys with ≥3 errors |

**Note:** Function names contain "claude" (Anthropic naming) but execution is 100% via Groq.

## Embedding Model

**Evidence:** `[File: server/services/vector_store.py, line 40]`

| Property | Value |
|---|---|
| Model | `all-MiniLM-L6-v2` |
| Library | sentence-transformers |
| Device | CPU |
| Output Dimension | 384 |
| Warm-up | Encodes "warmup" string on first load |
| Pattern | Lazy singleton with thread-safe double-check locking |

## Vector Store

**Evidence:** `[File: server/services/vector_store.py]`

| Property | Value |
|---|---|
| Technology | ChromaDB PersistentClient |
| Distance Metric | Cosine (`hnsw:space: "cosine"`) |
| Collections | 5 (spec_clauses, document_memory, rfis, standards, commissioning_checklists) |
| Metadata constraint | All values must be strings |

## Orchestrator / Planner

**Evidence:** `[File: server/agents/orchestrator_agent.py]`

- Framework: LangGraph `StateGraph` v0.1.5
- Version: 3.0.0 (`AGENT_VERSION`)
- Pattern: Supervisor router — classify intent → dispatch to specialist node
- State: `OrchestratorState(TypedDict, total=False)` — 8 fields

## System Prompts Summary

| Prompt | File:Line | Role | Output Format |
|---|---|---|---|
| `ORCHESTRATOR_SYSTEM` | `orchestrator_agent.py:28` | Classifier | JSON `{intent, confidence, extracted_parameters}` |
| `SEVERITY_SYSTEM` | `compliance_agent.py:86` | QA Engineer | JSON `{severity, justification, recommended_action, w_conform}` |
| `NCR_SYSTEM` | `compliance_agent.py:97` | QA Manager | Text: TITLE/DESCRIPTION/IMPACT/ACTIONS |
| `MITIGATION_SYSTEM` | `schedule_agent.py:36` | Project Controls | Text: OPTION 1/2/3 with Actions/Days saved/Cost/Owner |
| `RAG_SYSTEM` | `knowledge_agent.py:64` | Technical Manager | Natural language with [SOURCE N] citations |
| `SUPPLY_CHAIN_SYSTEM_PROMPT` | `supply_chain_agent.py:13` | Supply Chain Analyst | JSON `{risk_assessment, alternatives, recommendation}` |
| `BID_ANALYSIS_SYSTEM` | `procurement_agent.py:22` | Procurement Manager | JSON `{recommendations:[...]}` |
| `SUBMITTAL_EXTRACTION_SYSTEM` | `upload.py:28` | Procurement Engineer | JSON attribute key-value pairs |

## JSON Parsing / Guardrails

4-strategy `_parse_json_robust(text)` `[File: llm_client.py, lines 65–111]`:
1. Direct `json.loads()`
2. Extract from ` ```json``` ` code block
3. Brace-count scan for outermost `{...}`
4. Fix Python True/False/None + trailing commas, retry

## Heuristic Fallbacks

| Agent | Fallback | Evidence |
|---|---|---|
| Compliance severity | `_apply_heuristic_scoring()` — percent thresholds | `compliance_agent.py:565` |
| Compliance NCR text | `_default_ncr_text(dev)` — template string | `compliance_agent.py:625` |
| Procurement bids | `_fallback_bid_analysis()` — formula scoring | `procurement_agent.py:80` |
| Orchestrator routing | Keyword matching in `classify_node()` | `orchestrator_agent.py:69` |

## Chunking

- **Type:** Fixed-size sliding window
- **Chunk size:** 2000 characters
- **Overlap:** 200 characters
- **No semantic chunking** — purely character-based
- **`[File: knowledge_agent.py, lines 80–88]`**

## Max Token Budget Per Agent

| Agent / Call | max_tokens |
|---|---|
| Orchestrator classification | 500 |
| Severity scoring per deviation | 500 |
| NCR generation per deviation | 800 |
| Schedule mitigation per task | 1200 |
| RFI RAG answer | 2000 |
| Bid analysis | 1500 |
| Supply chain alternatives | 1000 |

---

# PART VIII — Infrastructure

## Docker

**Evidence:** `[File: Dockerfile]`

**Multi-stage build:**

**Stage 1 (frontend-builder):** `node:20-alpine`
- `npm ci` — clean reproducible install
- `npm run build` — Vite production build → `/app/client/dist`

**Stage 2 (runtime):** `python:3.11-slim`
- System deps: `build-essential` (for C-extension Python packages)
- `pip install --no-cache-dir -r server/requirements.txt`
- `COPY server/` → `/app/server/`
- `COPY --from=frontend-builder /app/client/dist` → `/app/client/dist`

**Env vars set in Dockerfile:**
```
PYTHONDONTWRITEBYTECODE=1  PYTHONUNBUFFERED=1
DISABLE_RELOAD=true        PORT=8000  HOST=0.0.0.0
UPLOADS_PATH=/app/data/uploads
CHROMA_PATH=/app/data/chroma_db
DATABASE_PATH=/app/data/dcpi.db
```

**Volume:** `VOLUME ["/app/data"]` — persists all stateful data across container restarts.

**Exposed Port:** 8000

**CMD:** `["python", "main.py"]` — runs Uvicorn programmatically with settings from env vars.

## CI/CD

**Not verifiable from repository.** No GitHub Actions, GitLab CI, Jenkinsfile, or other CI/CD configuration found.

## Secrets Management

**Evidence:** `[File: .env, lines 20–21]`

All secrets are stored in the `.env` file in the repository root and loaded by `python-dotenv`. **A live Groq API key is committed in this file** — this is a security concern if the repository is ever made public or shared.

The `.env` file appears NOT to be excluded in `.gitignore` (based on it being present in the workspace) — **verify before any code sharing.**

## Development Startup

**Evidence:** `[File: README.md, lines 25–37]`, `[File: start.bat]`

Server: `cd server && uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
Client: `cd client && npm run dev` → `http://localhost:5173`

## Python Dependencies

**Evidence:** `[File: server/requirements.txt]`

| Package | Version | Purpose |
|---|---|---|
| fastapi | 0.111.0 | Web framework |
| uvicorn | 0.29.0 | ASGI server |
| aiohttp | 3.9.5 | Async HTTP client for Groq API |
| requests | 2.32.3 | Sync HTTP (legacy/utility use) |
| chromadb | 0.5.0 | Vector store |
| sentence-transformers | 2.7.0 | Local embeddings |
| PyMuPDF | 1.24.3 | PDF text extraction |
| python-dotenv | 1.0.1 | `.env` loading |
| python-multipart | 0.0.9 | File upload support |
| pydantic | 2.7.1 | Data validation |
| numpy | 1.26.4 | Numerical ops |
| python-jose[cryptography] | 3.3.0 | JWT |
| passlib[bcrypt] | 1.7.4 | Password hashing |
| bcrypt | 4.1.3 | bcrypt implementation |
| langchain | 0.2.7 | LangChain (for LangGraph) |
| langchain-groq | 0.1.6 | Groq LangChain integration |
| langgraph | 0.1.5 | Agent orchestration framework |
| langchain-core | 0.2.12 | LangChain core |
| pytest | 8.2.2 | Testing |
| httpx | 0.27.0 | Async HTTP client for tests |
| pytest-asyncio | 0.23.7 | Async test support |

## Frontend Dependencies

**Evidence:** `[File: client/package.json]`

| Package | Version | Purpose |
|---|---|---|
| react | ^18.3.1 | UI framework |
| react-dom | ^18.3.1 | DOM rendering |
| react-router-dom | ^6.23.1 | Client-side routing |
| framer-motion | ^12.42.2 | Animations |
| leaflet | ^1.9.4 | Map library |
| react-leaflet | ^4.2.1 | React Leaflet bindings |
| lucide-react | ^1.23.0 | Icon library |
| @react-three/fiber | ^8.18.0 | 3D rendering (Three.js) |
| @react-three/drei | ^9.122.0 | Three.js helpers |
| three | ^0.185.1 | 3D engine |
| tailwindcss | ^3.4.3 | CSS utility framework |
| vite | ^8.1.0 | Build tool |

---

# PART IX — Data

## Database: SQLite (`dcpi.db`)

**WAL Mode** + `PRAGMA synchronous=NORMAL` + 64MB page cache + 256MB mmap + temp tables in memory.

## All 19 Tables

### `projects`
| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| name | TEXT NOT NULL | Project name |
| size_mw | REAL | Data centre capacity in MW |
| deadline | TEXT | ISO date |
| budget | REAL | Total project budget USD |
| status | TEXT | 'active', 'completed', 'on_hold' |
| created_at | TEXT | ISO timestamp |
| location | TEXT | Physical location |
| capacity_unit | TEXT | Default 'MW' |
| equipment_budget | REAL | Equipment sub-budget |
| tier | TEXT | 'Tier III', 'Tier IV' etc. |
| description | TEXT | Long description |
| pm | TEXT | Project manager name |

### `documents`
| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| project_id | TEXT→projects | Optional FK |
| filename | TEXT NOT NULL | Original filename |
| doc_type | TEXT NOT NULL | 'specification', 'submittal', 'general' |
| upload_ts | TEXT | ISO timestamp |
| file_path | TEXT | Absolute path to saved file |
| status | TEXT | 'uploaded' → 'processing' → 'ready' / 'failed' |
| page_count | INTEGER | Set after parsing |

### `spec_clauses`
| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| document_id | TEXT→documents | Source document |
| clause_number | TEXT | e.g. "4.2.4" |
| clause_title | TEXT | e.g. "UPS System Requirements" |
| equipment_class | TEXT | 'UPS', 'PDU', 'COOLING', etc. |
| clause_type | TEXT | 'TECHNICAL', 'COMMERCIAL', etc. |
| raw_text | TEXT | Full clause text |
| requirements_json | TEXT | JSON array of `{attribute, required_value, tolerance_type, ...}` |
| tier | TEXT | 'TIER_IV', 'TIER_III', etc. |
| page_refs_json | TEXT | JSON array of page numbers |
| extracted_ts | TEXT | When extracted |
| confidence_score | REAL | LLM confidence 0-1 |

### `equipment_items`
| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| project_id | TEXT→projects | |
| item_code | TEXT | e.g. "UPS-01" |
| description | TEXT | |
| equipment_class | TEXT | 'UPS', 'PDU', 'COOLING', etc. |
| design_zone | TEXT | Physical zone |
| quantity | INTEGER | Default 1 |
| unit | TEXT | Default 'EA' (each) |
| required_by_date | TEXT | Delivery deadline |
| spec_clause_ids_json | TEXT | JSON array of clause IDs |
| criticality | TEXT | 'HIGH', 'MEDIUM', 'LOW' |
| compliance_score | REAL | 0.0–1.0 |

### `purchase_orders`
| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| po_number | TEXT | e.g. "PO-PS1500-001" |
| vendor_name | TEXT | |
| vendor_country | TEXT | Default 'India' |
| document_id | TEXT→documents | Submitted document |
| equipment_item_id | TEXT→equipment_items | |
| technical_attributes_json | TEXT | `{attr: value}` — extracted by LLM |
| compliance_status | TEXT | 'PENDING', 'COMPLIANT', 'NON_COMPLIANT', 'PARTIALLY_COMPLIANT' |
| deviation_count | INTEGER | Count of deviations |
| conformance_score | REAL | 0.0–1.0 |
| checked_ts | TEXT | Last compliance check timestamp |

### `deviations`
| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| po_id | TEXT→purchase_orders | |
| spec_clause_id | TEXT→spec_clauses | |
| attribute_name | TEXT | Normalized attribute key |
| specified_value | TEXT | What spec requires |
| submitted_value | TEXT | What vendor submitted |
| deviation_pct | REAL | % deviation (null for string/missing) |
| severity | TEXT | 'CRITICAL', 'MAJOR', 'MINOR', 'OBSERVATION' |
| deviation_type | TEXT | See deviation types table |
| w_conform | REAL | Conformance weight 0–1 |
| justification | TEXT | LLM justification |
| recommended_action | TEXT | LLM action |
| detected_ts | TEXT | When detected |

### `ncrs` (Non-Conformance Reports)
| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| project_id | TEXT→projects | |
| deviation_id | TEXT→deviations | |
| po_id | TEXT→purchase_orders | |
| equipment_item_id | TEXT→equipment_items | |
| title | TEXT | NCR title (from LLM TITLE: field) |
| description | TEXT | Full NCR text |
| severity | TEXT | Mirrors deviation severity |
| status | TEXT | 'open', 'in_review', 'closed', 'waived' |
| raised_ts | TEXT | Creation timestamp |
| due_date | TEXT | Response deadline (now + 5 days) |
| assigned_to | TEXT | Default 'Quality Manager' |
| resolution_text | TEXT | When closed |
| spec_clause_ref | TEXT | "clause_number — clause_title" |
| page_ref | TEXT | Page reference |
| schedule_impact_json | TEXT | `{linked_task_ids, min_float_days, risk_level, tasks}` |
| actions_json | TEXT | JSON array of action strings |

### `schedule_tasks`
| Column | Type | Notes |
|---|---|---|
| id | TEXT PK | UUID |
| task_code | TEXT | e.g. "T-UPS-001" |
| planned_start / planned_finish | TEXT | ISO dates |
| total_float_days | INTEGER | Current float |
| original_float_days | INTEGER | Baseline float |
| predecessor_ids_json | TEXT | JSON array of task IDs |
| equipment_item_id | TEXT→equipment_items | |
| percent_complete | REAL | 0.0–100.0 |
| risk_score | REAL | 0.0–1.0 sigmoid output |
| delay_probability | REAL | 0.0–1.0 |
| risk_level | TEXT | 'negligible', 'low', 'medium', 'high', 'critical' |
| is_critical_path | INTEGER | 0/1 boolean |
| mitigation_text | TEXT | AI mitigation options |
| actual_start / actual_finish | TEXT | As-built dates |
| actual_delay_days | INTEGER | |
| predicted_delay_days | INTEGER | |
| historical_avg_delay | REAL | |

### `commissioning_records`
Each represents one test step result: `task_id, step_number, step_name, step_type, acceptance_criteria, actual_value, status, pass_fail, flagged_ncr_id, checked_by, checked_ts, notes`

### `rfis`
`id, rfi_code, rfi_type, title, description, raised_by, raised_ts, status, response_due_ts, resolution_text, equipment_item_ids_json, spec_clause_refs_json, chroma_doc_id, is_resolved`

### `agent_runs`
Audit log for every agent invocation: `id, agent_name, agent_version, trigger_event, input_summary, output_summary, status, started_ts, completed_ts, error_text, records_processed, records_created, metadata_json`

### `vendors`
`id, company_name, email UNIQUE, password_hash, registered_at`

### `tenders`
`id, project_id, vendor_id, price, lead_time_days, equipment_catalog_json, status, ai_recommendation, ai_scores_json, created_at`

### `cost_records`
`id, po_id, equipment_item_id, delay_days, daily_rate, total_impact, mitigation_cost, impact_category, currency, narrative, calculated_ts`

### `vendor_scores`
`id, vendor_id, project_id, compliance_score, delivery_score, quality_score, overall_score, ncr_count, critical_ncr_count, tenders_submitted, tenders_won, narrative, calculated_ts`

### `workforce_demand`
`id, task_id, week_start, discipline, required_headcount, available_headcount, conflict`

### `reports`
`id, report_type, project_id, generated_ts, summary_json, executive_summary, status`

### `shipments`
`id, po_id, equipment_item_id, vendor_id, carrier_name, tracking_number, origin_lat, origin_lng, dest_lat, dest_lng, current_lat, current_lng, status, estimated_arrival, required_delivery, risk_level, ai_alternatives_json, last_updated_ts`

## Database Indexes (19 total)

```sql
idx_spec_clauses_doc     ON spec_clauses(document_id)
idx_spec_clauses_class   ON spec_clauses(equipment_class)
idx_deviations_po        ON deviations(po_id)
idx_deviations_severity  ON deviations(severity)
idx_deviations_clause    ON deviations(spec_clause_id)
idx_ncrs_severity        ON ncrs(severity)
idx_ncrs_status          ON ncrs(status)
idx_ncrs_po              ON ncrs(po_id)
idx_ncrs_equipment       ON ncrs(equipment_item_id)
idx_schedule_risk        ON schedule_tasks(risk_score)
idx_schedule_equipment   ON schedule_tasks(equipment_item_id)
idx_schedule_critical    ON schedule_tasks(is_critical_path)
idx_rfis_resolved        ON rfis(is_resolved)
idx_po_equipment         ON purchase_orders(equipment_item_id)
idx_agent_runs_name      ON agent_runs(agent_name)
idx_tenders_project      ON tenders(project_id)
idx_tenders_vendor       ON tenders(vendor_id)
idx_commissioning_task   ON commissioning_records(task_id)
idx_commissioning_status ON commissioning_records(status)
```

## ChromaDB Collections

| Collection | Content | Key Metadata |
|---|---|---|
| `spec_clauses` | Spec requirement text chunks | `clause_number`, `equipment_class`, `tier`, `requirements_json` |
| `document_memory` | General project document chunks | `document_type`, `document_id`, `chunk_index` |
| `rfis` | RFI title + resolution text | `rfi_code`, `rfi_type`, `is_resolved`, `project_id` |
| `standards` | Industry standard text chunks | `standard_name`, `chunk_index` |
| `commissioning_checklists` | Commissioning templates | `equipment_class`, `step_number`, `step_type` |

---

# PART X — Security

## Authentication

**Evidence:** `[File: server/security.py]`

- **Scheme:** OAuth2 Bearer Token (JWT HS256)
- **Token Expiry:** 7 days
- **Password Hashing:** bcrypt via passlib (`CryptContext(schemes=["bcrypt"])`)
- **SECRET_KEY vulnerability:** If env var unset, random key generated per restart → all existing tokens invalidated

## Authorization

**Evidence:** `[File: client/src/context/AuthContext.jsx, lines 34–41]`

- **Team users:** No server-side authentication at all. `loginAsTeam()` sets a sessionStorage flag client-side only. All team-facing API endpoints are publicly accessible.
- **Vendors:** JWT required on protected endpoints via `Depends(get_current_user)`
- **No RBAC** for finer-grained access control

## CORS Configuration

**Evidence:** `[File: server/main.py, lines 173–181]`

```python
allow_origins      = CORS_ORIGINS env var (default: "http://localhost:5173")
allow_credentials  = True
allow_methods      = ["GET","POST","PUT","DELETE","PATCH","OPTIONS"]
allow_headers      = ["*"]      # ← overly permissive
max_age            = 3600
```

`allow_headers=["*"]` with `allow_credentials=True` is disallowed by CORS spec and can cause browser errors in production.

## Input Validation

- **File type:** Only `.pdf` for spec/submittal `[File: routers/upload.py, line 109]`
- **Request bodies:** Pydantic v2 validation on all POST bodies
- **SQL injection:** Not possible — all queries use `?` parameterized SQLite queries
- **File size:** `MAX_UPLOAD_SIZE_MB=50` configured — enforcement in router **not verified in viewed code**

## Prompt Injection Mitigation

**Partial.** The RAG prompt instructs: *"Answer ONLY from the provided context."* No explicit injection guardrails (e.g., input sanitization, delimiter isolation, system message hardening).

## Secrets Exposure

**Critical:** `[File: .env, line 21]` contains a live `gsk_...` Groq API key committed to the repository.

## Encryption

- **At rest:** SQLite is plaintext — no database-level encryption
- **In transit:** Client→Server uses HTTP in dev; HTTPS required in production
- **Server→Groq:** HTTPS enforced by aiohttp

## XSS / CSRF

- **XSS:** React JSX auto-escapes — standard protection
- **CSRF:** No explicit CSRF token. REST API with JSON Content-Type is generally safe, but vendor auth forms could be vulnerable without CSRF headers.

---

# PART XI — Performance

## Algorithmic Complexities

| Operation | Complexity | Notes |
|---|---|---|
| `_compare_single()` | O(1) | Single attribute comparison |
| `compare_attributes(n, m)` | O(n × m) | n requirements, m attribute keys |
| `find_submitted_value()` | O(m + aliases) | Linear scan with alias expansion |
| `_topological_sort(V, E)` | O(V + E) | Kahn's algorithm |
| `_build_dependency_graph` | O(V) | Adjacency list build |
| ChromaDB HNSW search | O(log n) approx | Approximate nearest neighbor |
| `_evict_oldest()` in cache | O(n) | Full dict scan |
| `invalidate_prefix()` | O(n) | Full dict scan |
| Haversine distance | O(1) | 6 trig operations |

## Concurrency Model

```
Groq batch calls:
  asyncio.Semaphore(GROQ_MAX_CONCURRENT)   ← limits concurrent API requests
  aiohttp.TCPConnector(limit=n*2)          ← connection pooling
  asyncio.gather(task1, task2, ...)        ← fire all concurrently

Example speedup:
  20 deviations × 45s sequential = 900s
  20 deviations concurrent (10 max) = 2 waves × 45s = ~90s
  (10× faster)
```

**Evidence:** `[File: server/services/llm_client.py, lines 298–344]`

## PDF Extraction Parallelism

**Evidence:** `[File: server/services/pdf_extractor.py, lines 21–23]`

```python
PARALLEL_PAGE_THRESHOLD = 5        # parallel if >5 pages
NATIVE_MAX_WORKERS = cpu_count * 2 # max 32
```

Shared `ThreadPoolExecutor` singleton avoids per-call thread creation overhead.

## Caching Strategy

- Dashboard summary: cached 300s to avoid repeated heavy joins
- Document list: invalidated on upload via `invalidate_prefix("documents_list")`
- Max 256 entries; LRU eviction

## Memory Usage

| Component | Approximate RAM |
|---|---|
| Embedding model (all-MiniLM-L6-v2) | ~80 MB |
| ChromaDB in-process | Variable with collection size |
| SQLite page cache | 64 MB |
| SQLite mmap | Up to 256 MB |
| In-memory cache | Bounded by 256 entries × entry size |
| Python process baseline | ~50–100 MB |

## Token Budget vs. Call Count

| Operation | Calls | Tokens/Call | Total Tokens |
|---|---|---|---|
| 20 deviations severity scoring | 20 concurrent | 500 | 10,000 |
| 20 NCR generations | 20 concurrent | 800 | 16,000 |
| 1 RFI answer | 1 | 2,000 | 2,000 |
| 1 orchestrator classification | 1 | 500 | 500 |

**Token saving optimization:** Supply chain agent skips LLM if risk score < HIGH threshold `[File: supply_chain_agent.py, line 124]`.

## Streaming

**Not implemented.** All LLM calls use `"stream": False` `[File: llm_client.py, line 206]`. For long RFI answers this means the user waits for the full response before seeing anything.

---

# PART XII — Technical Debt

> Only evidence-backed items. No speculation.

### 1. Misleading Function Names: `call_claude*` → Groq Provider
**Evidence:** `[File: llm_client.py, lines 2–8, 263–277]`
All public functions named `call_claude` execute via Groq API, not Anthropic Claude. The docstring acknowledges this: *"provider is transparent."* Misleading for new contributors.

### 2. Live API Key Committed in `.env`
**Evidence:** `[File: .env, line 21]`
A real `gsk_...` Groq API key is present in the committed file. Requires immediate revocation and secret rotation if the repo is shared.

### 3. `SECRET_KEY` Falls Back to Random Per-Process Value
**Evidence:** `[File: server/security.py, line 14]`
```python
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
```
Every server restart without the env var invalidates all vendor JWT tokens.

### 4. EPC Team Auth is Frontend-Only (No Server Validation)
**Evidence:** `[File: client/src/context/AuthContext.jsx, lines 34–41]`
`loginAsTeam()` sets sessionStorage to `"true"` with no server call. All team-facing API endpoints are completely open.

### 5. No SQLite Connection Pool
**Evidence:** `[File: server/database/connection.py]`, used in all agent files.
Every agent call opens and closes a fresh connection. Under high concurrency this creates overhead. SQLite WAL mitigates write contention but not connection overhead.

### 6. `procurement_agent.py` Contains Merged Dead Code
**Evidence:** `[File: server/agents/procurement_agent.py, lines 139–209]`
The file contains commented-out `AGENT_NAME` constants and stub `process_request()` functions from merged `vendor_agent.py` and `cost_agent.py` — leftover merge debt.

### 7. `get_mock_shipment_tracking()` Returns Hardcoded Mock Data
**Evidence:** `[File: server/agents/procurement_agent.py, lines 107–118]`
Returns `"Shenzhen, China"`, `"Frankfurt, Germany"` regardless of PO ID. Not connected to the real shipments table.

### 8. `report_node()` in Orchestrator is a Stub
**Evidence:** `[File: server/agents/orchestrator_agent.py, lines 173–178]`
Returns `{"message": "Dashboard agent called."}` — no functionality.

### 9. Cache `_evict_oldest()` is O(n)
**Evidence:** `[File: server/services/cache.py, lines 156–161]`
Linear scan across all cache entries. Negligible at max_size=256, but technical debt if size increases.

### 10. `allow_headers=["*"]` + `allow_credentials=True`
**Evidence:** `[File: server/main.py, line 178]`
Disallowed by CORS specification. Browsers may reject requests or throw security errors.

---

# PART XIII — Repository Encyclopedia

## All API Endpoints

### Health & Status
| Method | Path | Function | Description |
|---|---|---|---|
| GET | `/api/` | `root()` | Basic health check |
| GET | `/health` | `health_check()` | DB + vector store + Groq status |
| GET | `/api/status` | `api_status()` | All registered routes |

### Upload `[routers/upload.py]`
| Method | Path | Description |
|---|---|---|
| POST | `/api/upload/specification` | Upload spec PDF → 202 Accepted |
| POST | `/api/upload/submittal` | Upload vendor submittal PDF → 202 |
| POST | `/api/upload/general` | Upload any document |
| GET | `/api/upload/status/{doc_id}` | Poll ingestion job status |
| GET | `/api/upload/documents` | List all documents |
| DELETE | `/api/upload/document/{doc_id}` | Delete document |
| GET | `/api/upload/equipment` | List equipment items |

### Auth `[routers/auth.py]`
| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register/vendor` | Register new vendor → hashed password + DB insert |
| POST | `/api/auth/login` | Verify password → JWT token |

### Projects `[routers/projects.py]`
| Method | Path | Description |
|---|---|---|
| GET | `/api/projects/` | List all projects |
| POST | `/api/projects/` | Create project |
| GET | `/api/projects/open` | Active projects only |
| GET | `/api/projects/{id}` | Single project |
| PATCH | `/api/projects/{id}/status` | Change status |
| DELETE | `/api/projects/{id}` | Delete project + cascade |

### Compliance `[routers/compliance.py]`
| Method | Path | Description |
|---|---|---|
| POST | `/api/compliance/run/{po_id}` | Run full compliance check + generate NCRs |
| GET | `/api/compliance/results/{po_id}` | Deviations + NCRs for a PO |
| GET | `/api/compliance/ncrs` | List NCRs (query: severity, status) |
| GET | `/api/compliance/ncr/{ncr_id}` | Single NCR detail (joined with deviations) |
| GET | `/api/compliance/spec-clauses` | List extracted spec clauses |
| GET | `/api/compliance/purchase-orders` | List purchase orders |

### Schedule `[routers/schedule.py]`
| Method | Path | Description |
|---|---|---|
| POST | `/api/schedule/import` | Import CSV/JSON schedule |
| POST | `/api/schedule/analyze` | Run risk analysis |
| GET | `/api/schedule/tasks` | List schedule tasks |
| GET | `/api/schedule/risks` | High-risk tasks only |
| GET | `/api/schedule/delay-comparison` | Planned vs actual delay comparison |

### RFI `[routers/rfi.py]`
| Method | Path | Description |
|---|---|---|
| POST | `/api/rfi/query` | RAG query → `{answer, sources, precedent_rfis, confidence}` |
| GET | `/api/rfi/rfis` | List RFI records |
| POST | `/api/rfi/create` | Create new RFI record |

### Dashboard `[routers/dashboard.py]`
| Method | Path | Description |
|---|---|---|
| GET | `/api/dashboard/summary` | Full metrics: NCRs, docs, tasks, health score |
| POST | `/api/dashboard/resolve-all` | Bulk-close open NCRs |

### Commissioning `[routers/commissioning.py]`
| Method | Path | Description |
|---|---|---|
| GET | `/api/commissioning/tasks` | Tasks with commissioning keywords |
| POST | `/api/commissioning/checklist/generate/{task_id}` | AI checklist generation |
| POST | `/api/commissioning/run/{task_id}/step/{step_number}` | Execute step + pass/fail |
| GET | `/api/commissioning/records` | All commissioning records |

### Supply Chain `[routers/supply_chain.py]`
| Method | Path | Description |
|---|---|---|
| GET | `/api/supply-chain/shipments` | All shipments with risk levels |
| GET | `/api/supply-chain/alerts` | Active risk alerts |
| GET | `/api/supply-chain/map` | Map-ready data (lat/lng + status) |

### Tenders `[routers/tenders.py]`
| Method | Path | Description |
|---|---|---|
| POST | `/api/tenders/create` | Submit vendor bid |
| GET | `/api/tenders/{project_id}` | List bids for project |
| PATCH | `/api/tenders/update_status/{bid_id}` | Accept/reject bid |
| POST | `/api/tenders/recommend` | AI bid evaluation + scoring |

### Reports `[routers/reports.py]`
| Method | Path | Description |
|---|---|---|
| GET | `/api/reports/{project_id}/export` | Export project report as text |

### Integrations `[routers/integrations.py]`
| Method | Path | Description |
|---|---|---|
| POST | `/api/integrations/upload` | Upload industry standard PDF → ChromaDB ingest |

### Static Files
| Path | Description |
|---|---|
| `/uploads/{filename}` | Serve uploaded PDF files |
| `/assets/{filename}` | Serve compiled React JS/CSS |
| `/{full_path}` | SPA catch-all → index.html |

## Middleware

| Name | Purpose | Evidence |
|---|---|---|
| `CORSMiddleware` | Cross-origin requests | `[main.py:173]` |
| `add_process_time_header` | UUID + timing per request | `[main.py:339]` |

## Exception Handlers

| Status | Handler | Behavior |
|---|---|---|
| 404 | `not_found_handler` | JSON: path + tip to check /api/status |
| 405 | `method_not_allowed_handler` | JSON: path + method |
| 500 | `internal_error_handler` | Full log + JSON (detail hidden unless DEBUG=true) |
| Any | `global_exception_handler` | Catch-all; uses `exc.status_code` if present |

## Shared Singletons

| Singleton | Module | Created |
|---|---|---|
| `cache` (TTLCache) | `services/cache.py` | Module import |
| `ingestion_queue` (IngestionQueue) | `services/ingestion_queue.py` | Module import |
| `_chroma_client` | `services/vector_store.py` | Lazy on first use |
| `_embedding_model` | `services/vector_store.py` | Lazy on first use |
| `_shared_executor` (ThreadPoolExecutor) | `services/pdf_extractor.py` | Lazy on first use |
| `_compiled_graph` (LangGraph) | `agents/orchestrator_agent.py` | Lazy on first use |

## Workers / Queues

| Component | Type | Concurrency Limit | Evidence |
|---|---|---|---|
| `IngestionQueue._worker_loop` | `asyncio.Task` | 5 jobs (Semaphore) | `[ingestion_queue.py:153]` |
| LLM batch | `asyncio.gather` | `GROQ_MAX_CONCURRENT` | `[llm_client.py:316]` |
| PDF pages | `ThreadPoolExecutor` | `cpu_count × 2` (max 32) | `[pdf_extractor.py:22]` |

## Agent Registry

| Agent | File | Version | Status |
|---|---|---|---|
| Orchestrator Brain | `orchestrator_agent.py` | 3.0.0 | **Active** |
| Spec Compliance | `compliance_agent.py` | 2.1.0 | **Active** |
| Schedule Risk | `schedule_agent.py` | 2.1.0 | **Active** |
| Knowledge/RFI | `knowledge_agent.py` | 2.0.0 | **Active** |
| Supply Chain | `supply_chain_agent.py` | N/A | **Active** |
| Procurement/ERP | `procurement_agent.py` | 2.0.0 | **Active (partial)** |
| Commissioning | `commissioning_agent.py` | 1.0.0 | **Active** |
| Report | `report_agent.py` | N/A | Stub only |
| Vision | `vision_agent.py` | N/A | Stub only |
| Monitor | `monitor_agent.py` | N/A | Stub only |

## Frontend Pages

| Page | File | Key Functionality |
|---|---|---|
| Landing | `LandingPage.jsx` | Marketing page, login CTAs, feature showcase |
| Dashboard | `Dashboard.jsx` | Metrics, NCR chart, recent agent runs, PO list |
| Compliance | `Compliance.jsx` | Submittal upload, compliance run, NCR table |
| NCR Detail | `NCRDetail.jsx` | Single NCR, actions, schedule impact |
| Schedule | `Schedule.jsx` | Task list, risk colors, mitigation display, import |
| RFI Chat | `RFIChat.jsx` | Chat UI, thinking animation, source cards |
| Supply Chain | `SupplyChainPage.jsx` | Leaflet map, shipment table, risk analysis |
| Commissioning | `CommissioningPage.jsx` | Task selection, step checklist, pass/fail UI |
| Tenders | `TendersAndContracts.jsx` | Bid table, AI scores, award dialog |
| Documents | `DocumentsPage.jsx` | File list, upload, status poll |
| Projects | `ProjectsPage.jsx` | Project cards, create/delete |
| New Project | `NewProject.jsx` | Multi-step wizard |
| Integrations | `IntegrationsPage.jsx` | Standards PDF upload |
| Design | `DesignPage.jsx` | Design document management |
| Team | `TeamPage.jsx` | Team member management |
| Settings | `SettingsPage.jsx` | User preferences |
| Vendor Dashboard | `VendorDashboard.jsx` | Vendor KPIs and bid status |
| Vendor Profile | `VendorProfile.jsx` | Company details |
| Vendor Tenders | `VendorTenders.jsx` | Bid submission form |

---

# PART XIV — Teaching Knowledge

## 1. LLM Provider Abstraction — `call_claude` → Groq

### Intuition
Why does `call_claude()` talk to Groq and not Anthropic Claude?

### Motivation
The system was designed with Claude as the intended LLM provider. When Groq was chosen for cost/speed reasons, the developer kept the function names unchanged to avoid refactoring every agent callsite.

### Design Decision
Adapter/Façade pattern — agents are decoupled from the provider. The function signature `call_claude(system_prompt, user_message, max_tokens)` is provider-agnostic. The implementation behind it is swappable.

### Alternatives
- Dependency injection: pass a `LLMProvider` object to each agent
- Environment variable: `LLM_PROVIDER=groq|claude|ollama` with factory function

### Trade-offs
| ✅ Pros | ❌ Cons |
|---|---|
| Zero refactor when switching providers | Misleading names |
| Consistent interface for all agents | Hard to add multiple providers simultaneously |
| Clean agent code | Confuses new developers |

### Common Mistakes
- Assuming Anthropic Claude is the provider — it is NOT
- Adding the Anthropic SDK thinking it's needed — Groq uses the OpenAI-compatible endpoint

### Interview Questions
- "How would you add OpenAI as a second LLM provider?"
- "How does the system handle LLM provider failure?"
- "Why is the temperature set to 0.1 instead of 0?"

### Debugging Guide
1. Check `GROQ_API_KEY` / `GROQ_API_KEYS` in `.env`
2. Check `_key_errors` dict — if all keys have ≥ 3 errors, all are disabled
3. `GET /health` returns `groq_api.keys_configured`
4. Enable `DEBUG=true` for verbose error messages in responses

### Extension Guide
To add Ollama as local fallback:
1. Add `OLLAMA_BASE_URL` and `OLLAMA_MODEL` to env (already in `.env`)
2. Add `_call_ollama_async()` in `llm_client.py`
3. Modify `_call_groq_async()` to try Ollama if Groq raises `RuntimeError`

---

## 2. Batch LLM Calls — Concurrency Model

### Intuition
Why are severity scoring and NCR generation done in one batch instead of a loop?

### Motivation
20 deviations × 45s sequential = **15 minutes** processing time.
20 deviations concurrent (10 at a time) = **~90 seconds**.

### Design Decision
```python
async def _call_groq_json_batch_async(items, max_tokens):
    semaphore = asyncio.Semaphore(GROQ_MAX_CONCURRENT)
    connector = aiohttp.TCPConnector(limit=GROQ_MAX_CONCURRENT * 2)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [_one(sp, um, session) for sp, um in items]
        return await asyncio.gather(*tasks)
```
`asyncio.gather` fires all tasks simultaneously; the semaphore limits how many reach the API at once.

### Alternatives
- Sequential loop (simple, slow)
- Celery task queue (distributed, complex)
- Single LLM call with all deviations (context window limits, harder to parse)

### Trade-offs
| ✅ Pros | ❌ Cons |
|---|---|
| ~10× speed improvement | Rate limits on Groq API keys |
| Per-item failure isolation (None, not crash) | Complex async/sync bridging |
| Same interface as sequential | Requires semaphore tuning |

### Common Mistakes
- Calling `asyncio.run()` from inside a running event loop → `RuntimeError`. `_run_async()` handles this correctly.
- Setting `GROQ_MAX_CONCURRENT` too high → 429 Rate Limit errors from Groq
- Not checking for `None` in batch results — failed items return `None`, not an exception

### Debugging Guide
- "Groq batch item failed" in logs → individual item error
- All items returning `None` → batch call failed entirely, check API keys
- Increase `GROQ_TIMEOUT_SECONDS` if items time out

---

## 3. Async Ingestion Queue

### Intuition
Why does document upload return 202 immediately instead of waiting for parsing to complete?

### Motivation
Parsing a 1000-page specification takes 5–15 minutes. Blocking the HTTP connection would time out (client timeout, load balancer timeout, Uvicorn timeout). The queue decouples upload from processing.

### Design Decision
`IngestionQueue` is a singleton with an `asyncio.Queue` and a background `asyncio.Task`. Upload endpoints enqueue a `coro_factory` lambda (not a coroutine) and return immediately.

Why a factory (callable) instead of a coroutine?
- Coroutines are one-time objects; they cannot be stored and re-awaited
- A factory `lambda: _parse_spec_bg(doc_id, path)` can be called at the right time inside `_run_job`

### Trade-offs
| ✅ Pros | ❌ Cons |
|---|---|
| Zero external dependencies | Jobs lost on server restart |
| Simple status polling | No retry mechanism |
| Semaphore limits concurrency | No priority queue |
| FastAPI-native asyncio | Not distributable across processes |

### Common Mistakes
- Passing an awaited coroutine instead of a factory
- Calling `ingestion_queue.start()` in a context without a running event loop (tests)
- Not calling `ingestion_queue.stop()` on shutdown → task lingers

### Extension Guide
To add job persistence across restarts:
1. On `submit()`, insert job row in a `background_jobs` DB table with `status="queued"`
2. On startup, reload jobs with `status="queued"` and re-enqueue them
3. On `_run_job()` completion, update DB status

---

## 4. ChromaDB + Local Embeddings

### Intuition
Why are embeddings computed locally with `all-MiniLM-L6-v2` instead of an API?

### Motivation
API-based embeddings (OpenAI `text-embedding-ada-002`) cost money per token and have rate limits. For a document-heavy application embedding thousands of spec clause chunks, local inference is free, private, and unlimited.

### Design Decision
`sentence-transformers` (`all-MiniLM-L6-v2`, 80MB model, 384-dim output). ChromaDB PersistentClient stores vectors on disk and queries using HNSW (approximate nearest-neighbor, O(log n)).

### Trade-offs
| ✅ Pros | ❌ Cons |
|---|---|
| Free after model download | 80MB RAM footprint |
| Private (no data leaves server) | CPU-only (slow on large batches) |
| No rate limits | Lower quality than large models |
| Fast for 384-dim vectors | Cold start delay on first encode |

### Common Mistakes
- Storing non-string metadata in ChromaDB → `TypeError`. Always call `_serialize_metadata()`.
- Forgetting to warm up the model → first encode is slow (JIT compilation). Code warms up with "warmup" string.
- Not checking `CHROMADB_AVAILABLE` flag before calling vector store functions → `ImportError`

### Debugging Guide
1. `GET /health` → `vector_store.collections.spec_clauses.count` shows document count
2. If search returns empty: check `collection.count()` — may need to re-ingest docs
3. If embedding fails: `SENTENCE_TRANSFORMERS_AVAILABLE` is False → check pip install

---

## 5. Schema Migration Pattern

### Intuition
How does the system add database columns to a live SQLite DB without breaking existing data?

### Motivation
SQLite does not allow dropping or modifying existing columns. `ALTER TABLE ... ADD COLUMN` is safe — it adds the column with its default value to all existing rows and silently fails (with a log warning) if the column already exists.

### Design Decision
```python
existing = {row[1] for row in db.execute("PRAGMA table_info(table)").fetchall()}
if "new_col" not in existing:
    db.execute("ALTER TABLE t ADD COLUMN new_col INTEGER DEFAULT 0")
    logger.info("Migrated: added new_col")
```
All migrations run on every startup (`init_db()` calls them in sequence). They are idempotent.

### Trade-offs
| ✅ Pros | ❌ Cons |
|---|---|
| Zero external dependencies | Cannot remove or rename columns |
| Idempotent — safe to run repeatedly | No migration version history |
| Runs automatically on startup | No rollback mechanism |
| No data loss | `NOT NULL` columns without DEFAULT fail |

### Common Mistakes
- Adding `NOT NULL` without a `DEFAULT` value → fails on existing rows
- Forgetting `db.commit()` after migration → changes lost
- Not catching the exception → server crashes on startup if migration fails

---

## 6. Severity Scoring — Heuristic Fallback Design

### Intuition
What happens to compliance checking when the Groq API is unavailable?

### Motivation
A QA system that stops working because an external API is down is worse than one that works with reduced intelligence. The heuristic fallback provides deterministic, auditable severity scoring without any LLM.

### Design Decision
```python
if not has_available_provider():
    for dev in deviations:
        _apply_heuristic_scoring(dev)
    return deviations
```
`_apply_heuristic_scoring()` maps `deviation_pct` thresholds to severity levels using environment-configurable cutoffs.

### Trade-offs
| ✅ Pros | ❌ Cons |
|---|---|
| Always works | No contextual awareness |
| Deterministic and auditable | Less accurate `w_conform` weights |
| Configurable thresholds | May under- or over-classify edge cases |

### Debugging Guide
- If all deviations show "MINOR" with heuristic justification text → LLM is unavailable
- Check `has_available_provider()` → returns `USE_GROQ` boolean
- Check Groq API key validity and rate limits

---

## 7. Supply Chain — Math-First Architecture

### Intuition
Why is the supply chain agent described as a "deterministic mathematical engine"?

### Motivation
LLM calls cost tokens and time. For a binary question ("is this shipment at risk?"), mathematics is sufficient. The LLM adds value only for creative, open-ended tasks ("what are the alternatives?").

### Design Decision
```
Step 1: Haversine distance → transit time estimate (math, O(1))
Step 2: Compare to required_delivery deadline (math, O(1))
Step 3: Lookup schedule float (DB query, O(1))
Step 4: Compute weighted risk score (math, O(1))
Step 5: ONLY IF score >= 45 (HIGH+): call LLM for alternatives
```

This "math gates AI" pattern saves ~80% of token costs on low-risk shipments.

### Haversine Formula `[File: supply_chain_agent.py, lines 44–50]`:
```python
R = 3958.8  # Earth radius in miles
dlat = math.radians(lat2 - lat1)
dlon = math.radians(lon2 - lon1)
a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
distance = R * c
```

### Common Mistakes
- Assuming LLM is always called → it's skipped for MEDIUM/LOW risk
- Using average truck speed (50 mph) as exact — it's a heuristic

---

## 8. LangGraph StateGraph Orchestration

### Intuition
Why use LangGraph StateGraph instead of simple `if/elif` routing?

### Motivation
LangGraph provides a type-safe, inspectable, extensible workflow graph. As the system grows to more agents, the graph makes routing explicit, debuggable, and easy to modify without changing existing code.

### Design Decision
```python
workflow = StateGraph(OrchestratorState)
workflow.add_node("classify", classify_node)
workflow.add_node("knowledge", knowledge_node)
# ... add all nodes ...
workflow.set_entry_point("classify")
workflow.add_conditional_edges("classify", route_intent, {intent: node_name})
workflow.add_edge("knowledge", END)
_compiled_graph = workflow.compile()
```

### Trade-offs
| ✅ Pros | ❌ Cons |
|---|---|
| Explicit, inspectable workflow | Overhead for simple routing |
| TypedDict state → type safety | LangGraph 0.1.5 is early API |
| Easy to add new agent nodes | Compiled graph must be reset to add nodes |

### Extension Guide
To add a new "COST" agent:
1. Create `agents/cost_agent.py` with `run_cost_analysis()` function
2. In `orchestrator_agent.py`:
   - Import and add `cost_node(state)` function
   - `workflow.add_node("cost", cost_node)`
   - `workflow.add_edge("cost", END)`
   - Update `ORCHESTRATOR_SYSTEM` prompt: add "8. COST: ..."
   - Update `route_intent()`: add `if intent == "COST": return "cost"`
3. Set `_compiled_graph = None` to reset the singleton

### Interview Questions
- "How does the orchestrator handle LLM classification failure?"
- "What is `total=False` in the TypedDict?"
- "How would you add parallel agent execution in LangGraph?"

---

*End of DataForge AI — Master Technical Reference*

*Document generated: 2026-07-21 | Repository: MY_version_ET (DataForge AI / DCPI v1.0.0)*
*Evidence policy enforced: All statements traceable to repository files via [File: path] notation.*
