# LLM Project Context

## 1. Project Overview

This repository implements DataForge AI, an AI-assisted project intelligence platform for EPC (Engineering, Procurement, and Construction) delivery in hyperscale data centre projects. The system is designed to help project teams review technical submittals, detect specification deviations, manage non-conformance reporting, evaluate schedule risk, and answer project questions through a retrieval-augmented assistant.

Primary users include:

- EPC project managers and engineering leads
- Quality/compliance teams
- Procurement and supply chain stakeholders
- Vendors submitting technical data
- Operations teams reviewing commissioning and schedule health

Core domain logic spans:

- Specification compliance validation
- Vendor submittal analysis
- NCR generation and tracking
- Schedule risk scoring and mitigation planning
- RFI knowledge retrieval and grounded answering
- Project health and dashboard summarization

## 2. System Architecture

The system follows a layered architecture:

```text
User / Project Team
    -> React + Vite frontend
        -> FastAPI REST API layer
            -> Domain agents (compliance, schedule, knowledge, orchestrator, commissioning, procurement)
                -> SQLite persistence layer
                -> ChromaDB vector store for semantic retrieval
                -> LLM providers (Groq primary, Ollama/fallback patterns)
```

### 2.1 Frontend Layer

The client is a single-page React application with animated page transitions and route-based views. It provides:

- project and dashboard views
- compliance and NCR workflows
- schedule analysis views
- an RFI chat experience
- vendor-facing views for bids and profile management

The frontend communicates with the backend through a centralized API client in [client/src/api/client.js](client/src/api/client.js).

### 2.2 API Layer

The backend is a FastAPI application initialized in [server/main.py](server/main.py). It registers feature routers under the /api namespace and hosts the main runtime lifecycle, CORS configuration, and startup initialization. The API layer is responsible for:

- accepting uploads and documents
- orchestrating business logic
- invoking agents and services
- returning structured JSON responses to the UI

### 2.3 Agentic Intelligence Layer

The intelligence layer is organized into domain-specific agents under [server/agents](server/agents):

- [server/agents/compliance_agent.py](server/agents/compliance_agent.py): evaluates vendor submittal attributes versus specification requirements and creates deviations/NCRs
- [server/agents/schedule_agent.py](server/agents/schedule_agent.py): scores schedule tasks using float, predecessor, procurement, and risk factors
- [server/agents/knowledge_agent.py](server/agents/knowledge_agent.py): performs retrieval-augmented answering over spec clauses, RFIs, and document memory
- [server/agents/orchestrator_agent.py](server/agents/orchestrator_agent.py): routes user requests to a specialist agent using a LangGraph-based workflow graph
- [server/agents/procurement_agent.py](server/agents/procurement_agent.py): handles procurement and supply chain reasoning patterns
- [server/agents/commissioning_agent.py](server/agents/commissioning_agent.py): generates commissioning checklists and task workflows

### 2.4 Data Layer

Persistence is centered on SQLite with schema initialization in [server/database/schema.py](server/database/schema.py). Specialized retrieval is handled in [server/services/vector_store.py](server/services/vector_store.py) using ChromaDB and sentence-transformers embeddings.

## 3. Tech Stack & Tooling

### 3.1 Languages and Frameworks

- Python 3.10+
- JavaScript/JSX
- React 18
- Vite
- Tailwind CSS
- FastAPI
- Pydantic
- Framer Motion

### 3.2 Persistence and Search

- SQLite (WAL mode enabled)
- ChromaDB for vector embeddings and semantic search
- sentence-transformers for embedding generation

### 3.3 AI and LLM Integration

- Groq as the primary LLM provider
- Ollama as a fallback pattern in the design and runtime logic
- LangGraph and LangChain-related dependencies for orchestration and graph workflows

### 3.4 Document and Parsing Tools

- PyMuPDF for PDF text extraction
- python-multipart for file uploads
- python-dotenv for environment configuration
- pytest for backend tests

## 4. Directory Structure & Key Files

### 4.1 Repository Layout

- [README.md](README.md): summary of the project and setup instructions
- [overview.md](overview.md): architecture-focused overview
- [server/](server/): backend application
- [client/](client/): frontend application
- [docs/](docs/): supporting documentation

### 4.2 Frontend Core Files

- [client/src/App.jsx](client/src/App.jsx): main app shell, route definitions, auth/workspace branching
- [client/src/api/client.js](client/src/api/client.js): centralized API client for all backend endpoints
- [client/src/context/AuthContext.jsx](client/src/context/AuthContext.jsx): authentication state and vendor/team login flow
- [client/src/context/WorkspaceContext.jsx](client/src/context/WorkspaceContext.jsx): project selection and workspace state
- [client/src/pages](client/src/pages): page-level UI for dashboard, compliance, schedule, RFI, commissioning, project creation, and vendor workflows
- [client/src/components](client/src/components): reusable cards, layouts, timelines, hero sections, and animated UI components

### 4.3 Backend Core Files

- [server/main.py](server/main.py): FastAPI app registration, startup lifecycle, router loading, environment validation
- [server/routers/upload.py](server/routers/upload.py): PDF upload, document persistence, async parsing queue submission
- [server/routers/compliance.py](server/routers/compliance.py): compliance execution and NCR query endpoints
- [server/routers/schedule.py](server/routers/schedule.py): schedule import, analysis, and delay-comparison endpoints
- [server/routers/rfi.py](server/routers/rfi.py): RFI query and RFI creation/indexing endpoints
- [server/routers/dashboard.py](server/routers/dashboard.py): dashboard summary and project reporting endpoints
- [server/agents/orchestrator_agent.py](server/agents/orchestrator_agent.py): LangGraph orchestrator routing logic
- [server/agents/compliance_agent.py](server/agents/compliance_agent.py): deviation detection and NCR generation logic
- [server/agents/schedule_agent.py](server/agents/schedule_agent.py): schedule risk scoring and mitigation generation
- [server/agents/knowledge_agent.py](server/agents/knowledge_agent.py): RAG-based knowledge answering
- [server/services/llm_client.py](server/services/llm_client.py): centralized LLM client wrapper with Groq batching and JSON parsing
- [server/services/vector_store.py](server/services/vector_store.py): ChromaDB indexing and semantic search implementation
- [server/services/spec_parser.py](server/services/spec_parser.py): parsing and clause extraction logic
- [server/services/pdf_extractor.py](server/services/pdf_extractor.py): PDF text extraction
- [server/database/schema.py](server/database/schema.py): SQLite schema definitions and indexes
- [server/models/schemas.py](server/models/schemas.py): request/response schemas

## 5. Core Data Flow & Workflows

### 5.1 Happy Path: Specification Upload and Compliance Processing

1. A user uploads a PDF specification through the client.
2. The frontend posts the file to /api/upload/specification.
3. The backend saves the file, creates a document record, and submits a background parsing job.
4. The parser extracts clauses and stores them in the SQLite database.
5. The system optionally indexes the clauses into ChromaDB for semantic retrieval.
6. When a vendor submittal is uploaded, a purchase order is created and its technical attributes are extracted.
7. The compliance agent compares PO attributes against extracted requirements, identifies deviations, and generates NCR records.
8. The UI displays compliance results, deviation severity, and NCR details.

### 5.2 Happy Path: RFI Query

1. A user submits a natural-language query in the RFI assistant.
2. The request reaches /api/rfi/query.
3. The orchestrator agent classifies the intent and routes the query to the knowledge agent.
4. The knowledge agent retrieves relevant spec clauses, precedent RFIs, and document memory from ChromaDB.
5. The LLM provider is called with the retrieved context and a strict answer policy.
6. The response is returned to the client with sources, precedent RFIs, and confidence.

### 5.3 Happy Path: Schedule Analysis

1. Schedule data is imported via CSV upload into the schedule_tasks table.
2. The analysis endpoint triggers the schedule agent.
3. The agent reads tasks, dependency lists, and open NCRs.
4. It computes risk scores using float, procurement delay, predecessor risk, and other heuristics.
5. Results are persisted back into schedule_tasks and exposed through the schedule API.

## 6. Data Models & Persistence

### 6.1 Core Database Entities

The SQLite schema includes the following major entities:

- projects: project metadata and delivery context
- documents: uploaded PDF documents and processing status
- spec_clauses: extracted specification clauses and requirements
- equipment_items: equipment catalog entries linked to clauses and tasks
- purchase_orders: vendor submittals and extracted technical attributes
- deviations: compliance mismatches between required and submitted attributes
- ncrs: non-conformance report records generated from deviations
- schedule_tasks: imported schedule activities with float and risk fields
- rfis: stored RFIs and resolution text
- agent_runs: execution traces and summaries for agent runs
- vendors, bids, cost_records, vendor_scores, workforce_demand, reports: additional planning and vendor-management entities

### 6.2 Relationships and Intent

The model is designed to connect:

- documents -> spec clauses
- equipment_items -> specification clauses and schedule tasks
- purchase_orders -> equipment_items and documents
- deviations -> purchase_orders and spec_clauses
- ncrs -> deviations, purchase_orders, equipment_items
- schedule_tasks -> equipment_items and predecessor dependencies
- rfis -> equipment items and specification clauses

### 6.3 Specialized Storage Mechanisms

- SQLite stores relational operational records and audit data.
- ChromaDB stores embedded chunks for semantic retrieval.
- The vector layer is used for spec clauses, RFIs, standards, and document memory chunks.
- JSON fields are used extensively for flexible metadata and interrelated lists.

## 7. Environment & Configuration Variables

The application expects environment variables such as:

- GROQ_API_KEY or GROQ_API_KEYS: LLM access configuration for Groq
- GROQ_MODEL: model selection for Groq inference
- GROQ_TIMEOUT_SECONDS: timeout for LLM requests
- GROQ_MAX_RETRIES: retry policy for LLM calls
- GROQ_MAX_CONCURRENT: concurrency for batch LLM requests
- CHROMA_PATH: persistent ChromaDB storage path
- EMBEDDING_MODEL: sentence-transformers model name
- CHROMA_MAX_RETRIES / CHROMA_RETRY_DELAY / CHROMA_BATCH_SIZE: vector store operational settings
- UPLOADS_PATH: file storage directory for uploaded documents
- CORS_ORIGINS: allowed frontend origins
- COMPLIANCE_CRITICAL_DEVIATION_PCT / COMPLIANCE_MAJOR_DEVIATION_PCT / COMPLIANCE_MINOR_DEVIATION_PCT: thresholds for deviation severity
- SCHEDULE_HIGH_RISK_THRESHOLD / SCHEDULE_MEDIUM_RISK_THRESHOLD / SCHEDULE_CRITICAL_NCR_DELAY / SCHEDULE_MAJOR_NCR_DELAY / SCHEDULE_MINOR_NCR_DELAY: schedule risk scoring settings
- RFI_MAX_SPEC_RESULTS / RFI_MAX_RFI_RESULTS / RFI_PRECEDENT_THRESHOLD / RFI_MAX_CONTEXT_CHARS / RFI_MAX_ANSWER_WORDS: knowledge retrieval and answer-generation controls

Do not place secrets directly in source control; provide them through environment variables or a local .env file.

## 8. Current State & Known Limitations

### 8.1 Implemented Areas

- Full frontend shell with multiple domain-specific pages
- FastAPI backend with feature routing and upload processing
- SQLite-backed data persistence with substantial schema coverage
- Compliance workflow with deviation/NCR generation
- Schedule risk analysis pipeline
- RFI query workflow with orchestration and vector retrieval
- LLM integration wrapper with batching and JSON parsing

### 8.2 Known Limitations and Risks

- The project appears to be a working prototype/demo-oriented platform rather than a fully hardened enterprise system.
- SQLite is suitable for rapid development, but it is not the preferred long-term persistence layer for high concurrency or large-scale multi-tenant deployments.
- Some agents rely on heuristic logic and LLM-assisted classification, so output quality depends on prompt design and provider availability.
- The orchestration layer is functional but still lightweight; it can be expanded into a more production-grade workflow engine.
- The repository contains several feature areas that look partially connected or still evolving, so some endpoints may be more mature than others.
- The current setup relies on local file storage and local vector persistence, which is appropriate for demos but may need externalization for production deployment.
