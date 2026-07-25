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

*Traces the actual user journeys through the DataForge AI platform as implemented in the React client and FastAPI backend.*

```mermaid
flowchart TD
    classDef auth fill:#e9d5ff,stroke:#a855f7,stroke-width:1px,color:#000
    classDef nav fill:#a7f3d0,stroke:#059669,stroke-width:1px,color:#000
    classDef upload fill:#fecaca,stroke:#dc2626,stroke-width:1px,color:#000
    classDef agent fill:#d8b4fe,stroke:#9333ea,stroke-width:2px,color:#000
    classDef ingest fill:#a5f3fc,stroke:#0891b2,stroke-width:1px,color:#000
    classDef output fill:#fef08a,stroke:#ca8a04,stroke-width:1px,color:#000
    classDef vendor fill:#fbcfe8,stroke:#db2777,stroke-width:1px,color:#000
    classDef data fill:#bae6fd,stroke:#0284c7,stroke-width:1px,color:#000

    %% ── Authentication ──
    Landing[Landing Page]:::auth --> Login[Login / Sign Up]:::auth
    Landing --> VendorReg[Vendor Registration]:::vendor
    Login --> Projects[Projects Page]:::nav
    VendorReg --> VendorDash[Vendor Dashboard]:::vendor

    %% ── Vendor Flow ──
    VendorDash --> VendorTenders[Submit Tenders - Price, Lead Time, Catalog]:::vendor
    VendorDash --> VendorProfile[Company Profile]:::vendor

    %% ── Project Setup ──
    Projects --> NewProject[Create Project - Name, Location, MW, Budget, Tier, PM]:::nav
    Projects --> SelectProject[Select Existing Project]:::nav
    NewProject --> Dashboard
    SelectProject --> Dashboard[Project Dashboard - KPIs, Agent Activity, Health Score]:::nav

    %% ── Core Workflows from Sidebar ──
    Dashboard --> Documents[Documents Page]:::upload
    Dashboard --> CompPage[Compliance Page]:::upload
    Dashboard --> SchedulePage[Schedule Page]:::upload
    Dashboard --> RFI[RFI Copilot Chat]:::agent
    Dashboard --> Tenders[Tenders and Contracts]:::upload
    Dashboard --> SupplyChain[Supply Chain - Live Map]:::output
    Dashboard --> Commissioning[Commissioning Page]:::upload
    Dashboard --> Design[Design - 3D Viewer]:::output
    Dashboard --> Integrations[Integrations - Standards Upload]:::ingest

    %% ── Document Upload & Ingestion ──
    Documents --> UploadSpec[Upload Specification PDF]:::upload
    Documents --> UploadSubmittal[Upload Vendor Submittal PDF]:::upload
    UploadSpec --> IngestQueue[Ingestion Queue - Max 5 Concurrent]:::ingest
    IngestQueue --> PDFExtract[PyMuPDF Text Extraction]:::ingest
    PDFExtract --> SpecParser[Two-Pass Clause Extraction - Regex then LLM]:::ingest
    SpecParser --> SQLite[(SQLite - spec_clauses table)]:::data
    SpecParser --> ChromaDB[(ChromaDB - Vector Embeddings)]:::data

    UploadSubmittal --> AttrExtract[LLM Attribute Extraction from Submittal]:::ingest
    AttrExtract --> PO[(SQLite - purchase_orders.technical_attributes_json)]:::data

    %% ── Compliance Workflow ──
    CompPage --> SelectDocs[Select Spec Doc + Submittal Doc]:::upload
    SelectDocs --> RunCheck[Run Compliance Check on PO]:::agent
    RunCheck --> CompAgent[Compliance Agent v2.1.0 - Batch Deviation Scoring]:::agent
    CompAgent --> Deviations[Deviations with Severity - CRITICAL / MAJOR / MINOR]:::output
    Deviations --> NCRGen[Auto-Generate NCR Reports via LLM]:::agent
    NCRGen --> NCRList[NCR List with Actions and Spec References]:::output

    %% ── Schedule Workflow ──
    SchedulePage --> ImportSchedule[Import Schedule CSV - 500+ Tasks]:::upload
    SchedulePage --> RunAnalysis[Run Risk Analysis]:::agent
    RunAnalysis --> SchedAgent[Schedule Agent v2.1.0 - Sigmoid Risk Model]:::agent
    SchedAgent --> RiskDash[Risk Dashboard - Critical Path, Float, Delay Probability]:::output
    SchedAgent --> Mitigation[AI Mitigation Plans - 3 Options per Task]:::output

    %% ── RFI Copilot ──
    RFI --> Orchestrator[Orchestrator Agent v3.0.0 - LangGraph Intent Classification]:::agent
    Orchestrator --> KnowledgeAgent[Knowledge Agent - RAG Search]:::agent
    KnowledgeAgent --> ChromaDB
    KnowledgeAgent --> Answer[Structured Answer with Citations and Precedents]:::output

    %% ── Tender Evaluation ──
    Tenders --> GetRec[Get AI Recommendation]:::agent
    GetRec --> ProcAgent[Procurement Agent v2.0.0 - Score Price, Compliance, Lead Time]:::agent
    ProcAgent --> Ranked[Ranked Vendor List with Justification]:::output
    Tenders --> AcceptReject[Accept / Reject Each Tender]:::nav

    %% ── Supply Chain ──
    SupplyChain --> ShipMap[Leaflet Map with GPS Markers and Routes]:::output
    SupplyChain --> AnalyzeShip[Analyze Shipment Risk]:::agent
    AnalyzeShip --> SCAgent[Supply Chain Agent - Haversine Distance + Critical Path Check]:::agent
    SCAgent --> Alternatives[AI Logistics Alternatives - Air Freight, Local Sourcing]:::output

    %% ── Commissioning ──
    Commissioning --> GenChecklist[Generate Checklist for Task]:::agent
    GenChecklist --> CommAgent[Commissioning Agent v1.0.0 - Equipment-Specific Steps]:::agent
    CommAgent --> Checklist[Test Checklist - Safety, Electrical, Performance, Sign-off]:::output
    Checklist --> EnterResults[Enter Actual Test Values]:::upload
    EnterResults --> Validate[AI Validates Against Acceptance Criteria]:::agent
    Validate --> AutoNCR[Auto-Create NCR on Failure]:::output

    %% ── Design & Integrations ──
    Design --> Upload2D[Upload 2D Floor Plan]:::upload
    Upload2D --> Viewer3D[Interactive 3D Viewer - React Three Fiber]:::output
    Integrations --> UploadStandard[Upload Industry Standard PDFs]:::upload
    UploadStandard --> IndexStandard[Chunk, Embed, Index to ChromaDB]:::ingest

    %% ── Email Webhook ──
    EmailWebhook[SendGrid Inbound Email Webhook]:::ingest --> IngestQueue
```

---

## 4. Layered Architecture (7 Layers)

*Precisely mapped to the actual DataForge AI implementation stack — each node references a real file, service, or component in the codebase.*

```mermaid
flowchart LR
    classDef layerBox fill:#e5e7eb,stroke:#9ca3af,stroke-width:1px,color:#000
    classDef l1 fill:#e9d5ff,stroke:#a855f7,color:#000
    classDef l2 fill:#fecaca,stroke:#dc2626,color:#000
    classDef l3 fill:#fef08a,stroke:#ca8a04,color:#000
    classDef l4 fill:#bbf7d0,stroke:#16a34a,color:#000
    classDef l5 fill:#fbcfe8,stroke:#db2777,color:#000
    classDef l6 fill:#bae6fd,stroke:#0284c7,color:#000
    classDef l7 fill:#e5e7eb,stroke:#4b5563,color:#000

    subgraph L1 ["Layer 1: React Frontend (Vite + Tailwind + Framer Motion)"]
        style L1 fill:#e5e7eb,stroke:#9ca3af
        L1A[LandingPage.jsx - Marketing + Auth]:::l1
        L1B[LoginScreen.jsx - JWT Auth + Vendor Register]:::l1
        L1C[ProjectsPage.jsx - Project List + Create]:::l3
        L1D[NewProject.jsx - Name, Location, MW, Budget, Tier, PM]:::l3
        L1E[Dashboard.jsx - KPIs, Service Charts, Agent Advisor]:::l4
        L1F[DocumentsPage.jsx - Upload Spec or Submittal PDF]:::l6
        L1G[Sidebar.jsx - 9 Team Links + 5 Global Links + 3 Vendor Links]:::l2

        L1A --> L1B --> L1C
        L1C --> L1D
        L1C --> L1E
        L1E --> L1F
    end

    subgraph L2 ["Layer 2: FastAPI Routers (13 Registered Routes)"]
        style L2 fill:#e5e7eb,stroke:#9ca3af
        L2A["/api/upload - Spec, Submittal, Schedule Upload"]:::l2
        L2B["/api/auth - Login, Register, Vendor Register"]:::l1
        L2C["/api/compliance - Run Check, Get NCRs"]:::l2
        L2D["/api/schedule - Tasks, Analyze, Import CSV"]:::l3
        L2E["/api/rfi - Query via Orchestrator"]:::l4
        L2F["/api/tenders - CRUD, AI Recommend"]:::l3
        L2G["/api/supply-chain - Shipments, Analyze Risk"]:::l2
        L2H["/api/webhooks - SendGrid Inbound Email"]:::l6
        L2I["/api/commissioning - Tasks, Generate, Validate"]:::l4
        L2J["/api/integrations - Upload Industry Standards"]:::l1

        L1F --> L2A
        L1B --> L2B
    end

    subgraph L3 ["Layer 3: Document Ingestion Pipeline"]
        style L3 fill:#e5e7eb,stroke:#9ca3af
        L3A[ingestion_queue.py - Async Job Queue, Max 5 Concurrent]:::l6
        L3B[pdf_extractor.py - PyMuPDF Native + OCR Fallback]:::l3
        L3C[spec_parser.py - Two-Pass: Regex Heuristic then LLM Batch]:::l2
        L3D[upload.py - LLM Submittal Attribute Extraction]:::l4
        L3E[vector_store.py - ChromaDB Indexing + Embedding]:::l1

        L2A --> L3A
        L2H --> L3A
        L3A --> L3B --> L3C
        L3C --> L3E
        L2A --> L3D
    end

    subgraph L4 ["Layer 4: AI Agent Layer (LangGraph Orchestrated)"]
        style L4 fill:#e5e7eb,stroke:#9ca3af
        L4A[orchestrator_agent.py - LangGraph StateGraph, Intent Classification]:::l4
        L4B[compliance_agent.py - PO vs Spec, Batch Deviation + NCR Gen]:::l2
        L4C[schedule_agent.py - Sigmoid Risk Model, Float + NCR + Predecessor]:::l6
        L4D[procurement_agent.py - Tender Scoring, Price + Compliance + Lead Time]:::l3
        L4E[supply_chain_agent.py - Haversine Distance, Delay Math, Alternatives]:::l2
        L4F[knowledge_agent.py - RAG: Specs + RFIs + Standards + Memory]:::l1
        L4G[commissioning_agent.py - Checklist Gen, Pass/Fail Validation]:::l4

        L2E --> L4A
        L4A --> L4B & L4C & L4D & L4E & L4F & L4G
        L2C --> L4B
        L2D --> L4C
        L2F --> L4D
        L2G --> L4E
        L2I --> L4G
    end

    subgraph L5 ["Layer 5: LLM + Embedding Services"]
        style L5 fill:#e5e7eb,stroke:#9ca3af
        L5A["llm_client.py - Groq API, Multi-Key Round Robin"]:::l5
        L5B["call_claude / call_claude_json - Single LLM Call"]:::l1
        L5C["call_claude_batch / call_claude_json_batch - Concurrent Batch"]:::l3
        L5D["vector_store.py - all-MiniLM-L6-v2 Embeddings"]:::l6
        L5E["cache.py - TTL Cache, 256 Keys, Lazy Eviction"]:::l1

        L4B & L4C & L4D & L4E & L4F --> L5A
        L5A --> L5B & L5C
        L4F --> L5D
        L3C --> L5A
    end

    subgraph L6 ["Layer 6: Data Persistence (SQLite + ChromaDB)"]
        style L6 fill:#e5e7eb,stroke:#9ca3af
        L6A["(SQLite WAL Mode - 17 Tables, Foreign Keys ON)"]:::l6
        L6B["(ChromaDB - spec_clauses, rfis, standards, memory)"]:::l1
        L6C["/uploads/ - Stored PDF Files"]:::l2
        L6D["schema.py - Auto-Migration on Startup"]:::l3

        L4B & L4C & L4D & L4E & L4G --> L6A
        L3E --> L6B
        L5D --> L6B
        L3B --> L6C
    end

    subgraph L7 ["Layer 7: External Systems + Standards"]
        style L7 fill:#e5e7eb,stroke:#9ca3af
        L7A[Groq Cloud API - llama-3.1-8b-instant Primary]:::l7
        L7B[SendGrid Inbound Parse - Email to Document Webhook]:::l7
        L7C[Industry Standards PDFs - Uptime, ASHRAE, TIA-942, BICSI]:::l7
        L7D["Future: SAP ERP, Primavera P6, Autodesk Forge (Integrations Page)"]:::l7

        L5A --> L7A
        L7B --> L2H
        L7C --> L2J
    end
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