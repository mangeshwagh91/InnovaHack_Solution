# DataForge AI - Data Centre Project Intelligence

DataForge AI is an AI-powered EPC (Engineering, Procurement, and Construction) project intelligence application, specifically tailored for Tier IV data centre construction projects. It aims to eliminate offline communication gaps by breaking down silos between documentation, schedules, and supply chains.

## 🚀 Key AI Agents & Features

- **Knowledge Ingestion Engine**: A high-speed, parallelized ingestion pipeline that processes massive 1000+ page technical PDF specifications. It uses chunking with sliding windows to safely load complex construction specs into a local ChromaDB instance.
- **Specification Parsing & Compliance Agent**: Automatically reads Vendor Submittals (Purchase Orders) and compares them mathematically against the baseline Technical Specifications. It automatically generates Non-Conformance Reports (NCRs) for any deviations.
- **Supply Chain Visibility & Risk Agent**: A deterministic mathematical engine that tracks live truck GPS coordinates, computes exact transit delays using Haversine distance, and cross-references the project schedule. If the delay threatens a zero-float critical path task, it uses Claude to instantly model procurement alternatives (e.g., Air Freight vs. Local Sourcing).
- **RFI Copilot**: An AI-powered RAG chat interface that lets engineers instantly query the entire corpus of uploaded project data.
- **Schedule Risk Analysis**: An agent that evaluates tasks based on float days, predecessor risks, and procurement delays to calculate risk scores and delay probabilities.

## 💻 Tech Stack

- **Client**: React 18, Vite, Tailwind CSS, Framer Motion, React-Leaflet, Lucide Icons.
- **Server**: FastAPI (Python), SQLite (WAL mode), ChromaDB.
- **AI/Intelligence**: Anthropic Claude API (Primary), Groq, Ollama. ThreadPoolExecutor for CPU-bound extraction.

## ⚙️ Running the Project

### Prerequisites
- Node.js and npm
- Python 3.10+

### Starting the Server
1. Navigate to the `server` directory.
2. Create a virtual environment: `python -m venv venv`
3. Activate: `.\venv\Scripts\activate` (Windows) or `source venv/bin/activate` (Mac/Linux)
4. Install dependencies: `pip install -r requirements.txt`
5. Start the server: `uvicorn main:app --host 0.0.0.0 --port 8000 --reload`
6. API available at `http://localhost:8000`.

### Starting the Client
1. Navigate to the `client` directory.
2. Install dependencies: `npm install`
3. Start the Vite server: `npm run dev`
4. Application available at `http://localhost:5173`.
