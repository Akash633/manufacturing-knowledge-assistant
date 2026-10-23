# Revision-Aware Multimodal AI Assistant for Traceable Shop Floor Operations

> **SYNTHETIC DEMONSTRATION DATA. NOT VALID FOR REAL MACHINE OPERATION.**  
> *All operational parameters, machine limits, and procedures in this project are strictly synthetic demonstrations designed for software evaluation and engineering education.*

An intelligent, grounded manufacturing knowledge assistant tailored for CNC machining centers (fictional target: **DEMO-CNC-01**). The system answers shop-floor inquiries using authorized technical documentation, retrieves supporting evidence via Hybrid Search (BM25 + Dense Vectors + Reciprocal Rank Fusion), tracks document revisions, flags contradictory instructions, validates citations against real retrieved passages, and deterministically abstains when evidence is missing or safety-critical.

---

## Key Features

1. **Document Management & Ingestion**
   - Ingests **PDF** (via PyMuPDF) and **DOCX** (via python-docx) documents.
   - Extracts page-by-page text preserving document numbers, revision tags, sections, tables, and page numbers.
   - Calculates cryptographic SHA-256 checksums for audit traceability.
   - Validates file formats and file size limits (25 MB max).

2. **Deterministic Revision Governance**
   - Supports 7 explicit statuses: `Approved`, `Draft`, `Pending Review`, `Superseded`, `Withdrawn`, `Expired`, `Not Yet Effective`.
   - Explicit approval status and effective date windows determine operational authority.
   - Upload timestamps never confer authority.
   - LLMs are strictly prohibited from deciding which document revision is authoritative.

3. **Hybrid Retrieval (BM25 + Dense Vectors + RRF)**
   - **BM25 Keyword Engine**: Tokenizer configured for industrial codes (e.g., `DEMO-CNC-01`, `ISO-VG-68`, `±0.005mm`).
   - **Dense Vector Search**: Powered by Sentence-Transformers with a deterministic 128-dimensional dense hashing fallback for offline/air-gapped industrial edge devices.
   - **Reciprocal Rank Fusion (RRF)**: Merges ranked candidate lists ($k=60$) with full rank and score explainability.

4. **Grounded AI Answering & Verifiable Citations**
   - Retrieves evidence before answering.
   - All citations reference actual retrieved passages and are validated against chunk IDs.
   - Deterministic abstention triggered on:
     - `INSUFFICIENT_EVIDENCE`: No matching approved documentation.
     - `DOCUMENT_CONFLICT`: Contradictory instructions across applicable approved documents.
     - `SUPERSEDED_ONLY`: Only superseded/expired revisions found.
     - `SAFETY_ESCALATION`: Query addresses high-risk operations (e.g., interlock bypass).
     - `OUT_OF_SCOPE`: Query targets equipment outside machine scope.
   - Works 100% offline in deterministic demo mode without requiring an external API key.

5. **Multimodal Document Support**
   - Extracts and links embedded schematics and diagram snapshots to document and page numbers.
   - Provides OCR extraction metadata and clearly distinguishes text recognition from native visual understanding.

6. **Safety & Expert Review Queue**
   - Deterministic safety rule engine flags hazardous queries (interlock bypass, electrical cabinet access without LOTO, spindle overspeed, coolant shutoff).
   - Mandatory human escalation cannot be bypassed by model confidence scores.
   - Generates draft shop-floor work instructions based exclusively on approved evidence, remaining unpublished until an authorized specialist signs off.

7. **Empirical Evaluation Dashboard**
   - Evaluates Recall@1, Recall@3, Recall@5, Citation validity precision, Abstention accuracy, Conflict detection rate, and Latency.
   - Real benchmark runs compare baseline BM25 vs Proposed Hybrid RRF retrieval.

---

## Architecture

```
                    +---------------------------------------------+
                    |           React + TypeScript Dashboard      |
                    | (Overview, Assistant, Library, Conflicts...) |
                    +---------------------------------------------+
                                           | HTTP REST
                                           v
+---------------------------------------------------------------------------------+
|                               FastAPI Backend                                   |
|                                                                                 |
|  +------------------+    +-------------------+    +--------------------------+  |
|  | Ingestion Engine |    | Governance Engine |    |   Safety Rule Engine     |  |
|  | (PyMuPDF, DOCX)  |    | (Authority Rules, |    | (OSHA LOTO, Interlocks,  |  |
|  | (SHA256, Chunks) |    |  Conflict Detect) |    |  Spindle RPM Overrides)  |  |
|  +------------------+    +-------------------+    +--------------------------+  |
|           |                        |                           |                |
|           v                        v                           v                |
|  +--------------------------------------------------------------------------+  |
|  |                       Hybrid Retrieval Coordinator                       |  |
|  |     [BM25 Keyword Search]  +  [Dense Embeddings]  ==>  [RRF Fusion]       |  |
|  +--------------------------------------------------------------------------+  |
|                                    |                                            |
|                                    v                                            |
|  +--------------------------------------------------------------------------+  |
|  |               Grounded QA Generator & Citation Validator                 |  |
|  |         (Deterministic Extractive Synthesizer / Modular LLM API)         |  |
|  +--------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------+
                                     |
                                     v
                        SQLite Database (mfg_assistant.db)
```

---

## Quickstart (Windows PowerShell)

### Prerequisites
- Python 3.10+ (Tested on Python 3.14)
- Node.js v18+ and npm
- Windows PowerShell

### 1. Opening in Visual Studio Code
Open your terminal and navigate to the project directory:
```powershell
cd i:\projects\manufacturing-knowledge-assistant
code .
```

### 2. Setting Up Backend Dependencies
Install the required Python packages:
```powershell
python -m pip install -r backend/requirements.txt
```

### 3. Seeding Demonstration Data
Generate the synthetic PDF/DOCX corpus and populate the SQLite database:
```powershell
python scripts/generate_synthetic_corpus.py
python scripts/seed_demo_data.py
```

### 4. Running the Applications

#### Option A: Using PowerShell Scripts
In terminal 1 (Backend):
```powershell
.\start_backend.ps1
```
In terminal 2 (Frontend):
```powershell
.\start_frontend.ps1
```

#### Option B: Manual Commands
Terminal 1 (Backend on port 8000):
```powershell
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Terminal 2 (Frontend on port 5173):
```powershell
cd frontend
npm install
npm run dev
```

Visit the dashboard in your web browser: **`http://localhost:5173`**  
Access the interactive FastAPI Swagger API documentation: **`http://127.0.0.1:8000/docs`**

---

## Running Automated Tests

Run the full pytest suite:
```powershell
python -m pytest backend/app/tests -v
```

All 15 automated unit and integration tests will execute:
- Document parsing and checksum validation (`test_ingestion.py`)
- BM25, Dense Vector, and RRF rank fusion (`test_retrieval.py`)
- Revision authority evaluation and conflict detection (`test_governance.py`)
- Grounded Q&A, citation validation, and abstention (`test_qa.py`)
- Deterministic safety escalation and LOTO enforcement (`test_safety.py`)

---

## Synthetic Demonstration Corpus (`DEMO-CNC-01`)

The repository includes a curated collection of operational files in `data/synthetic_corpus/`:
1. `SOP-CNC-001_RevA_SUPERSEDED.pdf`: Old SOP with 15-minute warmup and 5% coolant. (Status: `Superseded`).
2. `SOP-CNC-001_RevB_APPROVED.pdf`: Active approved SOP with dual-stage 10-minute warmup, 8-10% coolant, and catalog feed rates. (Status: `Approved`).
3. `MR-2024-08_RevA_APPROVED.docx`: Preventive maintenance report with X/Y/Z backlash limits (max 0.008 mm) and ISO VG 68 way lube oil. (Status: `Approved`).
4. `QA-CNC-2024-03_RevA_APPROVED.pdf`: Quality alert restricting face milling Titanium Grade 5 feed rate to 1,200 mm/min (conflicts with general catalog 1,500 mm/min). (Status: `Approved`).

---

## Technical Transparency & Limitations
- **Multimodal Transparency**: The multimodal module extracts raster images and page previews, linking them to document IDs and page numbers, and supports optical character recognition (OCR). The system **does not** claim end-to-end spatial visual understanding; visual schematics are flagged for human operator verification.
- **Deterministic Demo Mode**: By default, the application runs entirely offline using deterministic rule-based synthesis and extractive grounding, ensuring zero API costs and zero external data leaks.
