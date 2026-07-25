# DataForge AI — Architecture & Agent Workflow

> **DCPI (Data Centre Project Intelligence)** — AI-powered EPC project intelligence
> for Tier IV data centre construction. This document describes the **actual implemented**
> architecture, agent workflows, data flows, and system topology as found in the codebase.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Technology Stack](#2-technology-stack)
3. [Functional Flowchart (Mind Map)](#3-functional-flowchart-mind-map)
4. [Layered Architecture (7 Layers)](#4-layered-architecture-7-layers)
5. [Agent Architecture](#5-agent-architecture)
6. [Orchestrator Agent — LangGraph State Machine](#6-orchestrator-agent--langgraph-state-machine)
7. [Agent Detail Cards](#7-agent-detail-cards)
8. [Data Model (Entity Relationship)](#8-data-model-entity-relationship)
9. [Document Ingestion Pipeline](#9-document-ingestion-pipeline)
10. [API Surface](#10-api-surface)
11. [Client Application Pages](#11-client-application-pages)
12. [Deployment Architecture](#12-deployment-architecture)
13. [Key Design Decisions](#13-key-design-decisions)

---

## 1. System Overview

DataForge AI is an end-to-end AI-powered platform for managing Tier IV data centre EPC projects. It breaks down silos between documentation, schedules, supply chains, and quality control by deploying a multi-agent AI system orchestrated via LangGraph.

**Core Capabilities:**
- Upload and parse 1000+ page technical specifications with clause-level extraction
- Automated compliance checking of vendor submittals against spec requirements
- AI-powered schedule risk analysis with critical path identification
- Live supply chain tracking with Haversine distance-based delay prediction
- RAG-powered RFI chat that searches specs, past RFIs, and industry standards
- Commissioning checklist generation with automated pass/fail validation
- Vendor tender evaluation and AI-scored procurement recommendations
- Email webhook ingestion — forward docs to a project-specific address for auto-processing

---

## 2. Technology Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 18, Vite, Tailwind CSS, Framer Motion, React Router v6 |
| **3D / Maps** | React Three Fiber, Three.js, React-Leaflet, Leaflet |
| **Backend** | FastAPI (Python 3.11+), Uvicorn, CORS middleware |
| **Database** | SQLite (WAL mode, 64 MB page cache, foreign keys ON) |
| **Vector Store** | ChromaDB (persistent, `all-MiniLM-L6-v2` embeddings via sentence-transformers) |
| **LLM Provider** | Groq API (primary, multi-key round-robin, concurrent batch calls) |
| **LLM Models** | `llama-3.1-8b-instant` (primary), `llama-3.2-3b-preview`, `mixtral-8x7b-32768` (fallbacks) |
| **Agent Framework** | LangGraph `StateGraph` for orchestrator routing |
| **PDF Extraction** | PyMuPDF (native), OCR fallback via pytesseract + pdf2image |
| **Auth** | JWT (python-jose), bcrypt password hashing (passlib) |
| **Containerisation** | Multi-stage Docker (Node 20 Alpine → Python 3.11 slim) |

---

## 3. Functional Flowchart (Mind Map)

*High-level user journey through the DataForge AI platform — from login to insights and reporting.*

```mermaid
flowchart TD
    classDef auth fill:#a7f3d0,stroke:#059669,stroke-width:2px,color:#000
    classDef dashboard fill:#d8b4fe,stroke:#9333ea,stroke-width:2px,color:#000
    classDef upload fill:#fecaca,stroke:#dc2626,stroke-width:1px,color:#000
    classDef engine fill:#c4b5fd,stroke:#7c3aed,stroke-width:2px,color:#000
    classDef viz fill:#a5f3fc,stroke:#0891b2,stroke-width:1px,color:#000
    classDef output fill:#e5e7eb,stroke:#6b7280,stroke-width:1px,color:#000
    classDef report fill:#d1d5db,stroke:#4b5563,stroke-width:1px,color:#000
    classDef vendor fill:#fbcfe8,stroke:#db2777,stroke-width:1px,color:#000

    %% ── Entry ──
    Login[User Login]:::auth
    Login --> Dashboard[Project Dashboard]:::dashboard
    Dashboard --> CreateProject[Create Project]:::dashboard

    %% ── Left Branch: Document Upload ──
    CreateProject --> UploadDocs[Upload Documents]:::upload
    UploadDocs --> UploadSpecs[Upload Specifications]:::upload
    UploadDocs --> UploadSubmittals[Upload Vendor Submittals]:::upload
    UploadSpecs --> AIParse[AI Parses & Extracts Clauses]:::upload
    UploadSubmittals --> AIParse
    AIParse --> ConfidenceScore[Confidence Score]:::upload

    %% ── Center: Core Workflows ──
    CreateProject --> SchedulePlan[Schedule & Planning]:::viz
    SchedulePlan --> ImportCSV[Import Schedule CSV]:::viz
    ImportCSV --> GanttView[Gantt View & Critical Path]:::viz
    GanttView --> AIRisk[AI Risk Analysis]:::viz

    CreateProject --> SupplyChain[Supply Chain]:::viz
    SupplyChain --> LiveMap[Live Map & Shipment Tracking]:::viz
    LiveMap --> AILogistics[AI Logistics Alternatives]:::viz

    %% ── Right Branch: Tenders & Vendors ──
    CreateProject --> Tenders[Tenders & Contracts]:::vendor
    Tenders --> VendorBids[Vendor Bid Submissions]:::vendor
    Tenders --> AIRecommend[AI Vendor Recommendations]:::vendor

    %% ── AI Agent Engine ──
    ConfidenceScore --> Engine[AI Agents Process & Analyze Data]:::engine
    AIRisk --> Engine
    AILogistics --> Engine
    AIRecommend --> Engine

    %% ── Outputs ──
    Engine --> Compliance[Compliance Dashboard & Deviations]:::output
    Engine --> RiskDash[Risk & Schedule Analysis]:::output
    Engine --> RFIChat[RFI Copilot Chat]:::output
    Engine --> NCRs[Auto-Generated NCRs]:::output

    %% ── Additional Workflows ──
    CreateProject --> Commissioning[Commissioning]:::viz
    Commissioning --> AIChecklist[AI Generates Test Checklists]:::viz
    AIChecklist --> PassFail[Pass / Fail Validation]:::viz

    CreateProject --> Design[Design & 3D Viewer]:::viz

    %% ── Reporting & Insights ──
    Compliance --> AIReports[AI-Generated Reports]:::report
    RiskDash --> AIReports
    RFIChat --> Exports[Report Export]:::report
    NCRs --> Exports

    AIReports --> GeneratePDF[Generate PDF or Excel]:::report
    Exports --> ShareTeam[Share with Team or Stakeholders]:::report

    %% ── Vendor Portal ──
    Login --> VendorPortal[Vendor Portal]:::vendor
    VendorPortal --> SubmitTenders[Submit Tenders & Catalogs]:::vendor
    VendorPortal --> VendorProfile[Company Profile]:::vendor
```

---

## 4. Layered Architecture (7 Layers)

*Simplified architecture showing how data flows through the DataForge AI platform — from user input to final reports.*

```mermaid
flowchart TD
    classDef l1 fill:#e9d5ff,stroke:#a855f7,color:#000
    classDef l2 fill:#fecaca,stroke:#dc2626,color:#000
    classDef l3 fill:#bbf7d0,stroke:#16a34a,color:#000
    classDef l4 fill:#fef08a,stroke:#ca8a04,color:#000
    classDef l5 fill:#bae6fd,stroke:#0284c7,color:#000
    classDef l6 fill:#fbcfe8,stroke:#db2777,color:#000
    classDef l7 fill:#e5e7eb,stroke:#4b5563,color:#000
    classDef db fill:#fed7aa,stroke:#ea580c,color:#000

    %% ── Layer 1: User Interface & Input ──
    subgraph L1 ["Layer 1: User Interface & Input"]
        style L1 fill:#f5f3ff,stroke:#a855f7
        L1A[User Login / Create Account]:::l1
        L1B[Create New Project\ne.g., Tier IV Data Centre]:::l1
        L1C[Upload Specifications]:::l1
        L1D[Upload Vendor Submittals]:::l1
        L1E[Import Schedule CSV]:::l1

        L1A --> L1B
        L1B --> L1C & L1D & L1E
    end

    %% ── Layer 2: Data Ingestion & Management ──
    subgraph L2 ["Layer 2: Data Ingestion & Management"]
        style L2 fill:#fef2f2,stroke:#dc2626
        L2A[PDF Extraction\nPyMuPDF + OCR Fallback]:::l2
        L2B[Two-Pass Clause Parser\nRegex then LLM]:::l2
        L2C[Submittal Attribute\nExtraction via LLM]:::l2
        L2D[Receive Completed Data\nand Update Database]:::l2
        L2E[Send Parsed Data\nto AI Layer]:::l2

        L2A --> L2B --> L2D
        L2A --> L2C --> L2D
        L2D --> L2E
    end

    %% ── Database Layer ──
    subgraph DB ["Production Database Layer"]
        style DB fill:#fff7ed,stroke:#ea580c
        DBA[(PostgreSQL\n17 Tables, Production)]:::db
        DBB[(Pinecone / Weaviate\nVector Embeddings)]:::db
        DBC[(Redis\nCache & Session Store)]:::db
        DBD[(AWS S3 / Cloud Storage\nPDF & Document Files)]:::db
    end

    %% ── Layer 3: AI/ML Agent Layer ──
    subgraph L3 ["Layer 3: AI/ML Agent Layer"]
        style L3 fill:#f0fdf4,stroke:#16a34a
        L3A[Compliance Agent\nDeviation Scoring]:::l3
        L3B[Schedule Agent\nSigmoid Risk Model]:::l3
        L3C[Knowledge Agent\nRAG Search]:::l3
        L3D[Procurement Agent\nTender Scoring]:::l3
        L3E[Supply Chain Agent\nGPS + Haversine Distance]:::l3
        L3F[Commissioning Agent\nChecklist Generation]:::l3
        L3G[Attach Confidence Score]:::l3
    end

    %% ── Layer 4: Core Processing Engine ──
    subgraph L4 ["Layer 4: Core Processing Engine"]
        style L4 fill:#fefce8,stroke:#ca8a04
        L4A[FastAPI Backend\nOrchestrator Routing]:::l4
        L4B[Batch LLM Calls\nGroq Multi-Key]:::l4
        L4C[Compliance Check\nPO vs Spec Comparison]:::l4
        L4D[Risk Analysis\nCritical Path + Float]:::l4

        L4A --> L4B
        L4B --> L4C & L4D
    end

    %% ── Layer 5: Visualization & Insights ──
    subgraph L5 ["Layer 5: Visualization & Insights"]
        style L5 fill:#eff6ff,stroke:#0284c7
        L5A[Compliance Dashboard\nDeviations & NCRs]:::l5
        L5B[Schedule Risk View\nGantt & Critical Path]:::l5
        L5C[RFI Copilot Chat\nAI Answers with Citations]:::l5
        L5D[Supply Chain Map\nLive GPS Tracking & Alerts]:::l5
        L5E[Display Results\nand Insights]:::l5

        L5A & L5B & L5C & L5D --> L5E
    end

    %% ── Layer 6: Reporting & Export ──
    subgraph L6 ["Layer 6: Reporting & Export"]
        style L6 fill:#fdf2f8,stroke:#db2777
        L6A[Compile Full\nProject Report]:::l6
        L6B[Generate\nPDF Report]:::l6
        L6C[Generate Detailed\nExcel Sheet]:::l6
        L6D[Email Report\nto Stakeholders]:::l6
        L6E[User: View,\nDownload, Share]:::l6

        L6A --> L6B & L6C
        L6B & L6C --> L6D & L6E
    end

    %% ── Layer 7: External Systems & Services ──
    subgraph L7 ["Layer 7: External Systems & Services"]
        style L7 fill:#f3f4f6,stroke:#4b5563
        L7A[Groq Cloud API\nLLM Inference]:::l7
        L7B[SendGrid Email Service\nInbound Parse + Notifications]:::l7
        L7C[GPS Tracking API\nReal-Time Shipment Coordinates]:::l7
        L7D[Industry Standards\nUptime, ASHRAE, TIA-942]:::l7
        L7E[Future: SAP ERP,\nPrimavera P6, Autodesk]:::l7
    end

    %% ── Cross-Layer Data Flow ──
    L1C & L1D & L1E --> L2A
    L2E --> DBA & DBB
    L2E --> L3A & L3B & L3C & L3D & L3E & L3F
    L3A & L3B & L3C & L3D & L3E & L3F --> L3G
    L3G --> L4A
    DBA & DBB --> L3C
    DBC --> L4A
    L2A --> DBD
    L4C & L4D --> L5A & L5B & L5C & L5D
    L5E --> L6A
    L4B --> L7A
    L7B --> L2A
    L7B --> L6D
    L7C --> L3E
    L7C --> L5D
    L7D --> DBB
```

---

## 5. Agent Architecture

The system implements **7 specialized agents** coordinated by a central **Orchestrator** built on LangGraph's `StateGraph`:

```mermaid
flowchart TD
    classDef orchestrator fill:#6366f1,stroke:#4f46e5,stroke-width:2px,color:#fff
    classDef agent fill:#10b981,stroke:#059669,stroke-width:1px,color:#fff
    classDef service fill:#f59e0b,stroke:#d97706,stroke-width:1px,color:#000
    classDef data fill:#3b82f6,stroke:#2563eb,stroke-width:1px,color:#fff

    USER([User Query via RFI Chat]) --> ORCH

    ORCH[Orchestrator Brain v3.0.0<br/>LangGraph StateGraph]:::orchestrator

    ORCH -->|KNOWLEDGE| KA[Knowledge Agent v2.0.0<br/>RAG - Spec Search + RFI Memory]:::agent
    ORCH -->|PROCUREMENT| PA[Procurement Agent v2.0.0<br/>Tender Scoring + Shipment Tracking]:::agent
    ORCH -->|QUALITY| CA[Compliance Agent v2.1.0<br/>Batch Deviation Scoring + NCR Gen]:::agent
    ORCH -->|SCHEDULE| SA[Schedule Agent v2.1.0<br/>Sigmoid Risk Model + Mitigation]:::agent
    ORCH -->|COMMISSIONING| CMA[Commissioning Agent v1.0.0<br/>Checklist Gen + Pass/Fail Validation]:::agent
    ORCH -->|REPORT| RA[Report Agent v0.1.0<br/>Scaffolded - Pending Implementation]:::agent

    KA --> VS[(ChromaDB<br/>Vector Store)]:::data
    KA --> DB[(SQLite DB)]:::data
    CA --> DB
    CA --> VS
    SA --> DB
    PA --> DB
    CMA --> DB

    KA --> LLM[Groq LLM Client<br/>Multi-Key Batch]:::service
    CA --> LLM
    SA --> LLM
    PA --> LLM
    CMA --> LLM

    SCA[Supply Chain Agent<br/>Haversine + LLM Mitigation]:::agent --> DB
    SCA --> LLM
```

### Agent Summary Table

| Agent | Version | File | Key Function | LLM Usage |
|---|---|---|---|---|
| **Orchestrator Brain** | 3.0.0 | `orchestrator_agent.py` | Intent classification → route to specialist | `call_claude_json` for intent classification |
| **Knowledge & Document** | 2.0.0 | `knowledge_agent.py` | RAG search across specs, RFIs, standards, doc memory | `call_claude` for answer synthesis |
| **Compliance & Quality** | 2.1.0 | `compliance_agent.py` | PO vs spec comparison, deviation scoring, NCR generation | `call_claude_json_batch` (severity) + `call_claude_batch` (NCR text) |
| **Schedule & Risk** | 2.1.0 | `schedule_agent.py` | Float/NCR/predecessor/weather risk scoring, mitigation | `call_claude_batch` for mitigation plans |
| **Procurement & ERP** | 2.0.0 | `procurement_agent.py` | Tender analysis, bid scoring, shipment tracking | `call_claude_json` for bid recommendations |
| **Supply Chain** | — | `supply_chain_agent.py` | Haversine distance, delay math, logistics alternatives | `call_claude` for alternative strategies |
| **Commissioning Copilot** | 1.0.0 | `commissioning_agent.py` | Checklist generation from specs, test result validation | `call_claude_json` for dynamic checklist |
| **Report / Dashboard** | 0.1.0 | `report_agent.py` | Scaffolded — returns mock data | None (not yet implemented) |

---

## 6. Orchestrator Agent — LangGraph State Machine

The orchestrator is a compiled `StateGraph` that classifies user intent and routes to the correct specialist node. Each node runs synchronously and returns to `END`.

```mermaid
stateDiagram-v2
    [*] --> classify
    classify --> knowledge: KNOWLEDGE / GENERAL
    classify --> procurement: PROCUREMENT
    classify --> quality: QUALITY
    classify --> schedule: SCHEDULE
    classify --> commissioning: COMMISSIONING
    classify --> report: REPORT

    knowledge --> [*]
    procurement --> [*]
    quality --> [*]
    schedule --> [*]
    commissioning --> [*]
    report --> [*]
```

**State Shape (`OrchestratorState`):**

| Field | Type | Description |
|---|---|---|
| `query` | `str` | User's natural language query |
| `context` | `Dict` | Additional context (project_id, po_id, etc.) |
| `intent` | `str` | Classified intent (KNOWLEDGE, PROCUREMENT, etc.) |
| `extracted_parameters` | `Dict` | LLM-extracted params (po_id, task_id, event_details) |
| `agent_response` | `Dict` | Response payload from the specialist agent |
| `agent_run_id` | `str` | UUID for audit trail in `agent_runs` table |

**Fallback Behaviour:** When no LLM provider is available, the orchestrator uses keyword-based intent classification (e.g., "tender" → PROCUREMENT, "schedule" → SCHEDULE).

---

## 7. Agent Detail Cards

### 7.1 Compliance Agent (v2.1.0)

The most complex agent. Performs a full spec compliance check for a given Purchase Order:

```
Input: po_id (Purchase Order ID)
    │
    ▼
┌───────────────────────────────────┐
│ 1. Load PO technical attributes   │
│    from purchase_orders table     │
│ 2. Normalize attribute keys via   │
│    ATTR_ALIASES (80+ mappings)    │
└───────────────┬───────────────────┘
                │
                ▼
┌───────────────────────────────────┐
│ 3. Load spec clauses:            │
│    Priority: ChromaDB vector     │
│    search → SQLite fallback      │
│ 4. Extract requirements_json     │
│    from each clause              │
└───────────────┬───────────────────┘
                │
                ▼
┌───────────────────────────────────┐
│ 5. compare_attributes()          │
│    - MIN / MAX / EXACT tolerance │
│    - String mismatch detection   │
│    - MISSING mandatory checks    │
│    - Deviation % calculation     │
└───────────────┬───────────────────┘
                │
                ▼
┌───────────────────────────────────┐
│ 6. BATCH severity scoring        │
│    All deviations → one LLM call │
│    Fallback: heuristic thresholds│
│    (>15% CRITICAL, >10% MAJOR,   │
│     >5% MINOR, else OBSERVATION) │
└───────────────┬───────────────────┘
                │
                ▼
┌───────────────────────────────────┐
│ 7. BATCH NCR generation          │
│    CRITICAL + MAJOR + MINOR devs │
│    → concurrent LLM call for NCR │
│    text (TITLE/DESC/IMPACT/ACTS) │
│ 8. Save NCRs + schedule impact   │
│ 9. Update PO compliance_status   │
└───────────────────────────────────┘
```

**Severity Thresholds (configurable via env):**
- `CRITICAL`: ≥ 15% deviation
- `MAJOR`: ≥ 10% deviation
- `MINOR`: ≥ 5% deviation
- `OBSERVATION`: < 5% deviation

---

### 7.2 Schedule Agent (v2.1.0)

Multi-factor risk scoring using a sigmoid probability model:

**Risk Factors:**
1. **Float Erosion** — tasks with ≤ 0 float days score highest
2. **NCR Procurement Impact** — linked NCRs add delay (CRITICAL=14d, MAJOR=7d, MINOR=2d)
3. **Predecessor Chain** — cascade risk from upstream delays
4. **Historical Average Delay** — exponential weighting on past performance
5. **Weather / External** — mock weather data integration

**Sigmoid Delay Probability:**
```
P(delay) = 1 / (1 + e^(-k * (risk_score - θ)))
where k=7.0, θ=0.45
```

**Risk Levels:**
- `>= 0.70` → HIGH (triggers AI mitigation generation)
- `>= 0.50` → MEDIUM
- `< 0.50` → LOW / NEGLIGIBLE

**Mitigation:** For high-risk tasks, generates 3 options (conservative → aggressive) via batch LLM call.

---

### 7.3 Supply Chain Agent

Deterministic mathematical engine with LLM-powered mitigation:

1. **Haversine Distance** — calculates remaining miles from current GPS to destination
2. **Delay Calculation** — `remaining_distance / 50mph` vs hours until required delivery
3. **Critical Path Cross-Reference** — checks if linked schedule task has zero float
4. **Risk Score** (0–100) with weighted components:
   - Delay severity: +15 to +40 points
   - Critical path: +20 to +35 points
5. **LLM Trigger** — only calls LLM when risk ≥ 45 (HIGH/CRITICAL)
6. **Output** — alternative logistics strategies (air freight, local sourcing, etc.)

---

### 7.4 Knowledge Agent (v2.0.0)

RAG-powered query engine with multi-source retrieval:

**Search Sources:**
1. `spec_clauses` collection (ChromaDB) — project specifications
2. `rfis` collection (ChromaDB) — past RFI resolutions
3. `industry_standards` collection — Uptime Institute, ASHRAE, TIA-942
4. `document_memory` collection — ingested PDF memory

**Pipeline:** Query → embed → vector search (top-k) → rank sources → synthesize answer via LLM with citations

---

### 7.5 Commissioning Agent (v1.0.0)

Generates equipment-specific testing checklists:

**Step Templates (built-in):** UPS (10 steps), PDU (7 steps), COOLING (multi-step), GENERATOR, SWITCHGEAR

**Workflow:**
1. Identify commissioning tasks from `schedule_tasks` via keyword matching
2. Look up equipment class from linked `equipment_items`
3. Generate checklist from built-in templates + LLM-enhanced criteria from specs
4. Validate test results against acceptance criteria
5. Auto-create NCRs for failed steps

---

## 8. Data Model (Entity Relationship)

```mermaid
erDiagram
    projects ||--o{ documents : has
    projects ||--o{ equipment_items : contains
    projects ||--o{ schedule_tasks : schedules
    projects ||--o{ rfis : tracks
    projects ||--o{ agent_runs : logs
    projects ||--o{ tenders : receives

    documents ||--o{ spec_clauses : parsed_into

    equipment_items ||--o{ purchase_orders : procured_via
    equipment_items ||--o{ schedule_tasks : linked_to

    purchase_orders ||--o{ deviations : checked_for
    purchase_orders ||--o{ ncrs : generates

    deviations ||--|| ncrs : triggers

    schedule_tasks ||--o{ commissioning_records : tested_by
    schedule_tasks ||--o{ workforce_demand : requires

    vendors ||--o{ tenders : submits
    vendors ||--o{ vendor_scores : rated_by
    vendors ||--o{ shipments : ships_via

    purchase_orders ||--o{ shipments : tracked_by
    purchase_orders ||--o{ cost_records : impacts

    projects {
        text id PK
        text name
        real size_mw
        text deadline
        real budget
        text status
        text location
        text tier
        text pm
    }

    documents {
        text id PK
        text project_id FK
        text filename
        text doc_type
        text status
        int page_count
    }

    spec_clauses {
        text id PK
        text document_id FK
        text clause_number
        text equipment_class
        text requirements_json
        real confidence_score
    }

    equipment_items {
        text id PK
        text project_id FK
        text item_code
        text equipment_class
        text criticality
        real compliance_score
    }

    purchase_orders {
        text id PK
        text project_id FK
        text po_number
        text vendor_name
        text technical_attributes_json
        text compliance_status
        real conformance_score
    }

    deviations {
        text id PK
        text po_id FK
        text attribute_name
        text specified_value
        text submitted_value
        real deviation_pct
        text severity
        real w_conform
    }

    ncrs {
        text id PK
        text project_id FK
        text deviation_id FK
        text po_id FK
        text title
        text severity
        text status
        text actions_json
        text schedule_impact_json
    }

    schedule_tasks {
        text id PK
        text project_id FK
        text task_code
        int total_float_days
        real risk_score
        real delay_probability
        int is_critical_path
        text mitigation_text
    }

    vendors {
        text id PK
        text company_name
        text email
        text password_hash
    }

    tenders {
        text id PK
        text project_id FK
        text vendor_id FK
        real price
        int lead_time_days
        text ai_recommendation
        text ai_scores_json
    }

    shipments {
        text id PK
        text carrier_name
        text tracking_number
        real current_lat
        real current_lng
        text status
        text risk_level
        text ai_alternatives_json
    }

    commissioning_records {
        text id PK
        text task_id FK
        int step_number
        text acceptance_criteria
        text actual_value
        text pass_fail
    }

    agent_runs {
        text id PK
        text project_id FK
        text agent_name
        text status
        text started_ts
        int records_processed
    }
```

**Total Tables:** 17 (projects, documents, spec_clauses, equipment_items, purchase_orders, deviations, ncrs, schedule_tasks, commissioning_records, rfis, agent_runs, vendors, tenders, cost_records, vendor_scores, workforce_demand, reports, shipments)

---

## 9. Document Ingestion Pipeline

```mermaid
flowchart LR
    classDef upload fill:#dbeafe,stroke:#3b82f6,color:#000
    classDef process fill:#fef3c7,stroke:#f59e0b,color:#000
    classDef store fill:#d1fae5,stroke:#10b981,color:#000
    classDef ai fill:#ede9fe,stroke:#8b5cf6,color:#000

    UPLOAD[PDF Upload<br/>or Email Webhook]:::upload
    QUEUE[Ingestion Queue<br/>Max 5 concurrent]:::process
    EXTRACT[PDF Extractor<br/>PyMuPDF / OCR]:::process
    PARSE[Spec Parser<br/>Two-Pass Extraction]:::ai
    STORE_SQL[SQLite<br/>spec_clauses table]:::store
    STORE_VEC[ChromaDB<br/>Vector Embeddings]:::store

    UPLOAD --> QUEUE --> EXTRACT --> PARSE
    PARSE --> STORE_SQL
    PARSE --> STORE_VEC
```

**Two-Pass Extraction:**
1. **Fast Heuristic Pass** — regex-based clause boundary detection, equipment class identification
2. **LLM Pass** — only for ambiguous clauses, extracts structured `requirements_json` with attributes, values, tolerances, and mandatory flags

**Ingestion Queue Features:**
- In-memory job tracking (queued → processing → done | failed)
- Max concurrent jobs: 5 (configurable via `INGEST_MAX_CONCURRENT`)
- DB status column updated for frontend polling
- Background async worker thread

---

## 10. API Surface

All endpoints are registered under `/api/` with the following router structure:

| Router | Prefix | Key Endpoints | Agent(s) Triggered |
|---|---|---|---|
| **Upload** | `/api/upload` | `POST /spec`, `POST /submittal`, `POST /schedule` | Spec Parser, Ingestion Queue |
| **Auth** | `/api/auth` | `POST /login`, `POST /register`, `POST /vendor/register` | — |
| **Projects** | `/api/projects` | `GET /`, `POST /`, `GET /{id}` | — |
| **Tenders** | `/api/tenders` | `GET /`, `POST /`, `POST /recommend` | Procurement Agent |
| **Compliance** | `/api/compliance` | `POST /check/{po_id}`, `GET /ncrs`, `GET /ncrs/{id}` | Compliance Agent |
| **Schedule** | `/api/schedule` | `GET /tasks`, `POST /analyze`, `POST /upload` | Schedule Agent |
| **RFI** | `/api/rfi` | `POST /query`, `GET /history` | Orchestrator → Knowledge Agent |
| **Dashboard** | `/api/dashboard` | `GET /summary`, `GET /metrics` | — (aggregation queries) |
| **Commissioning** | `/api/commissioning` | `GET /tasks`, `POST /generate/{task_id}`, `POST /validate` | Commissioning Agent |
| **Supply Chain** | `/api/supply-chain` | `GET /shipments`, `POST /analyze/{id}` | Supply Chain Agent |
| **Webhooks** | `/api/webhooks` | `POST /inbound-email` | Ingestion Queue (auto-parse) |
| **Design** | `/api/design` | `POST /analyze-floorplan` | — |
| **Integrations** | `/api/integrations` | `POST /upload-standard`, `GET /standards` | Vector Store indexing |
| **Health** | `/api/`, `/health`, `/api/status` | Health check, route listing | — |

---

## 11. Client Application Pages

| Page | Route | Description |
|---|---|---|
| Landing Page | `/` (unauthenticated) | Marketing / product overview |
| Login / Signup | `/login`, `/signup` | JWT authentication + vendor registration |
| Projects | `/projects` | Project list with create/select |
| New Project | `/projects/new` | Create project (name, location, MW, budget, tier) |
| Dashboard | `/dashboard` | KPI cards, charts, recent agent activity |
| Documents | `/documents` | Upload specs/submittals, view parsed clauses |
| Compliance | `/compliance` | Run compliance checks, view deviations |
| NCR Detail | `/ncr/:ncrId` | Individual NCR with actions and spec references |
| Schedule | `/schedule` | Gantt-style view, risk analysis, critical path |
| RFI Chat | `/rfi` | AI chat interface with citations |
| Tenders | `/tenders` | Vendor bid comparison, AI recommendations |
| Supply Chain | `/supply-chain` | Live map with shipment tracking |
| Commissioning | `/commissioning` | Test checklists, pass/fail entry |
| Design | `/design` | 2D → 3D floor plan viewer |
| Integrations | `/integrations` | Upload industry standards (Uptime, ASHRAE) |
| Settings | `/settings` | App configuration |
| Team | `/team` | Team member management |

**Vendor Portal (separate routes for `user.type === "vendor"`):**
- `/` → Vendor Dashboard
- `/vendor/tenders` → Submit and track tenders
- `/vendor/profile` → Company profile

---

## 12. Deployment Architecture

```mermaid
flowchart TB
    classDef container fill:#dbeafe,stroke:#3b82f6,color:#000
    classDef volume fill:#fef3c7,stroke:#f59e0b,color:#000
    classDef external fill:#fee2e2,stroke:#ef4444,color:#000

    subgraph Docker["Docker Container (python:3.11-slim)"]
        style Docker fill:#f8fafc,stroke:#94a3b8
        FRONTEND[React SPA<br/>Served from /client/dist]:::container
        BACKEND[FastAPI + Uvicorn<br/>Port 8000]:::container
        FRONTEND --> BACKEND
    end

    subgraph Persistence["/app/data (Docker Volume)"]
        style Persistence fill:#fffbeb,stroke:#f59e0b
        SQLITE[(dcpi.db<br/>SQLite WAL)]:::volume
        CHROMA[(chroma_db/<br/>ChromaDB)]:::volume
        UPLOADS[(uploads/<br/>PDF files)]:::volume
    end

    BACKEND --> SQLITE
    BACKEND --> CHROMA
    BACKEND --> UPLOADS

    GROQ[Groq Cloud API<br/>LLM Inference]:::external
    SENDGRID[SendGrid<br/>Inbound Parse]:::external

    BACKEND --> GROQ
    SENDGRID --> BACKEND
```

**Build Stages:**
1. `frontend-builder` (Node 20 Alpine) — `npm ci && npm run build`
2. Final image (Python 3.11 slim) — installs pip deps, copies server + compiled frontend
3. Single container serves both API and SPA via catch-all route

---

## 13. Key Design Decisions

| Decision | Rationale |
|---|---|
| **Groq over OpenAI/Anthropic** | Fastest inference speed for batch operations; multi-key rotation avoids rate limits |
| **SQLite WAL mode** | Single-file deployment, concurrent read/write, 64 MB page cache for performance |
| **ChromaDB (local)** | Zero-infra vector store that persists to disk; `all-MiniLM-L6-v2` for fast embeddings |
| **Batch LLM calls** | Compliance agent sends all deviations in one batch instead of N sequential calls |
| **Heuristic fallbacks** | Every agent works without an LLM — keyword classification, threshold-based scoring |
| **LangGraph orchestrator** | Compiled `StateGraph` with conditional edges for deterministic routing |
| **Two-pass PDF parsing** | Fast regex heuristics first, LLM only for ambiguous clauses — saves tokens |
| **Attribute aliasing** | 80+ alias mappings normalize vendor attribute names to canonical keys |
| **JWT auth** | Stateless auth with separate vendor/engineer roles |
| **In-memory ingestion queue** | Lightweight async job tracking; max 5 concurrent to avoid LLM throttling |
| **Docker single container** | Simplified deployment — API serves React SPA via catch-all route |
    