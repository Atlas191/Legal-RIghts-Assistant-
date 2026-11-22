# Legal Rights Assistant for Women (LRA) ⚖️

> **An AI-powered legal awareness and structured assistance platform providing Indian women with plain-language legal guidance, statutory mapping, and procedural navigation under Indian criminal and civil law.**

---

## 📌 Project Overview & Scope

Navigating legal remedies in India can be daunting for non-lawyers, especially during times of crisis. Women facing harassment, domestic violence, digital abuse, or workplace discrimination often struggle to identify:
1. Which specific laws and sections protect them.
2. How the transition from the old **Indian Penal Code (IPC)** to the newly enacted **Bharatiya Nyaya Sanhita, 2023 (BNS)** affects their complaint.
3. The exact competent authorities, timelines, and relief measures available.

The system indexes **11 knowledge base files** located in `./knowledge_base/`:
- `bns_2023.md`: Bharatiya Nyaya Sanhita, 2023 (Offences against women: Rape, Voyeurism, Stalking, Cruelty, Dowry death, Acid attack).
- `bnss_2023.md`: Bharatiya Nagarik Suraksha Sanhita, 2023 (FIR procedure, Zero FIR, refusal remedies, in-camera statements, victim compensation).
- `pwdva_2005.md`: Protection of Women from Domestic Violence Act, 2005 (Domestic violence definitions, Protection Officers, residence and protection orders).
- `posh_handbook.md`: MWCD Handbook on POSH Act, 2013 (Workplace harassment scenarios, Internal Committee vs Local Committee scope).
- `posh_act_supplement.md`: POSH Act, 2013 statutory supplement (Section 4 ICC establishment thresholds, Section 9 3-month timelines, conciliation limits).
- `dowry_prohibition_1961.md`: Dowry Prohibition Act, 1961 (Penalties for giving, taking, or demanding dowry).
- `nalsa_charter.md`: Legal Services Authorities Act, 1987 & NALSA charter (Free legal aid entitlement for all women under Section 12(c)).
- `helplines_and_portals.md`: Central emergency directory (112, 181, 1091, 1930 cybercrime, 15100 NALSA).
- `it_act_2000.md`: Information Technology Act, 2000 (Section 66E privacy violation, Section 67/67A publishing explicit material without consent).
- `maternity_benefit_act.md`: Maternity Benefit Act, 1961 & 2017 Amendment (26 weeks leave, work from home, unlawful dismissal protection).
- `ncw_charter.md`: National Commission for Women Citizen's Charter (Inquiry mandates and grievance redressal).

When indexed via `python scripts/ingest.py`, these 11 files produce **135 sections** which are chunked into **165 child chunks** stored in `./chroma_db`.

---

## 📁 Project Structure

```
Legal-Rights-Assistant/
├── lra/                      # Core application package
│   ├── __init__.py
│   ├── api.py               # FastAPI application, middleware, and route handlers
│   ├── api_schemas.py       # Pydantic v2 schemas for API requests and responses
│   ├── schemas.py           # Core domain schemas (Turn, Source, Forum, AskResult, etc.)
│   ├── pipeline.py          # Pipeline coordinator & stateless orchestrator
│   ├── rag/                 # RAG retrieval and generation subsystem
│   │   ├── __init__.py
│   │   ├── kb_utils.py      # Front-matter parser, tokenizer, and document chunker
│   │   ├── retrieval.py     # Hybrid dense (ChromaDB) + BM25Okapi retrieval engine
│   │   └── generate.py      # Local Ollama generation with verify_answer guardrails
│   ├── guidance/            # Procedural routing, roadmap, and draft generation
│   │   ├── __init__.py
│   │   ├── routing.py       # Deterministic forum and helpline routing rules
│   │   ├── roadmap.py       # Ordered 3-tier actionable roadmap builder
│   │   └── draft.py         # Deterministic legal petition and complaint drafting
│   └── language/            # Multilingual support subsystem
│       ├── __init__.py
│       └── lang.py          # Script detection, Hinglish markers, and translation verification
├── scripts/                 # CLI entry points and administrative scripts
│   ├── ingest.py            # Knowledge base indexing script
│   └── demo.py              # Interactive terminal query demo
├── tests/                   # Automated test suites
│   ├── unit/                # Unit tests for individual subsystems
│   │   ├── test_api.py
│   │   ├── test_draft.py
│   │   ├── test_generate.py
│   │   ├── test_lang.py
│   │   ├── test_pipeline.py
│   │   ├── test_roadmap.py
│   │   └── test_routing.py
│   └── eval/                # Evaluation and regression suites
│       ├── run_golden.py
│       ├── check_hindi.py
│       └── smoke_demo.py
├── knowledge_base/          # Statutory provisions and official handbooks (11 markdown files)
├── docs/                    # Technical and integration documentation
│   └── INTEGRATION.md
├── chroma_db/               # Local ChromaDB persistent vector index
├── requirements.txt         # Project dependencies
└── README.md
```

---

## ⚙️ Architecture

The application is structured into modular Python components:

- **`lra/schemas.py`**: Defines the shared, immutable data contracts using Pydantic models. It standardizes conversation turns (`Turn`), retrieved statutory sources (`Source`), forum authorities (`Forum`), procedural milestones (`RoadmapStep`, `RoadmapAction`), request/response payloads (`AskRequest`, `AskResult`), and structured complaints (`DraftRequest`, `DraftField`, `DraftResult`).
- **`lra/rag/kb_utils.py`**: Handles parsing and chunking of the 11 statutory markdown files. It extracts YAML front-matter metadata (law, act, chapter, keywords, formerly IPC) into parent sections, splits long provisions into overlapping child chunks (chunk size 700 characters, overlap 100 characters), tokenizes text for lexical search, and appends statutory metadata lines (`Formerly IPC: <val>`) to ensure penal cross-references are searchable.
- **`scripts/ingest.py`**: The one-time indexing pipeline. It parses the knowledge base files with `kb_utils`, generates dense semantic vector embeddings using local `BAAI/bge-small-en-v1.5` via HuggingFace, and populates the local ChromaDB vector store (`./chroma_db`) with 135 parent sections and 165 child chunks.
- **`lra/rag/retrieval.py`**: Executes hybrid search combining dense semantic embeddings (ChromaDB) and sparse lexical search (`BM25Okapi`). Rankings over child chunks are merged using Reciprocal Rank Fusion (RRF $k=60$) aggregated to parent sections, and results pass through multi-tier distance and token-length guardrails with regex exemptions for direct statute lookups (e.g. `498A`, `BNS 78`).
- **`lra/guidance/routing.py`**: Evaluates the user query and retrieved legal sources to identify competent forums and authorities categorized into safety (`181`, `112`), institutional (`ICC`, `LCC`, `PWDVA Protection Officer`), criminal (`Police/FIR`, `SP/Magistrate`, `cybercrime`), legal aid (`DLSA`), and national (`NCW`). It applies deterministic rules (e.g. workplace headcount $\ge 10$ routes to ICC, $<10$ routes to LCC) and flags clarification questions when headcount is unknown.
- **`lra/guidance/roadmap.py`**: Synthesizes an ordered, three-tier procedural roadmap (Immediate steps, Institutional remedies, and Formal legal action). Each step specifies basis-tagged actions (`kb` vs `general_guidance`) linked to relevant statutory source IDs and statutory time limits (e.g. POSH 3-month filing window).
- **`lra/guidance/draft.py`**: Implements deterministic, offline generation of formal complaint letters addressed to SHO, ICC, LCC, or Protection Officers. It extracts incident dates, times, places, designations, and names from the narrative without logging user text, populates user-provided form fields, and leaves missing fields as standardized bracketed placeholders.
- **`lra/language/lang.py`**: Manages multilingual understanding across English, Devanagari Hindi, and Romanized Hindi (Hinglish). It enriches non-English queries with statutory glossary keywords for retrieval, provides static verified refusal and disclaimer strings, and manages opt-in answer translation with strict structural verification (`[S#]` multiset equality, number preservation, echo detection, and Hinglish marker density).
- **`lra/rag/generate.py`**: Interfaces with the local Ollama LLM (`llama3`), building prompt contexts where scenarios are explicitly marked as illustrative examples. Generated explanations must pass `verify_answer`, which enforces citation presence (`[S#]`), active source ranges, section-mention support (via explicit section, subclause, or table cell matching), blocking of common advice phrases, and scenario detail leakage prevention before permitting answer return.
- **`lra/pipeline.py`**: Coordinates the entire workflow via `LegalPipeline`. It manages language detection, translation, follow-up conversation joins, hybrid retrieval, forum routing, procedural roadmaps, and verified generation into a single unified `AskResult`.

---

## 🔒 Privacy & Zero Data Retention

- **Zero Third-Party APIs**: All embeddings (`BAAI/bge-small-en-v1.5`) and LLM generations (`Ollama llama3`) execute 100% locally on the host machine. No user text, incident details, or generated answers are ever transmitted across external networks.
- **No Query Logging or Storage**: The application enforces a strict zero-retention policy. System logging across `pipeline`, `generate`, `retrieval`, and `draft` records only numeric counts, timing measurements in milliseconds, and outcome flags (e.g. `off_topic=False`, `verified=True`). User queries, draft narratives, extracted personal details, and generated text are never written to log files or persisted to disk.

---

## ⚠️ Known Limitations

- two off-topic queries still leak ("how to open a bank account", "how to apply for a pan card online")
- only citation markers and section numbers are verified, not meaning; the advice check blocks a short list of common phrases only, so a written answer can still be incomplete, overstated or add details
- retrieval can miss the best source (for example POSH quid pro quo for "manager asks for sexual favours in return for a promotion"); the sources shown under each answer are the reliable part
- small local models mistranslate some Hinglish queries; Hindi answer translation is off by default
- routing and roadmap text are English-only
- knowledge-base chunks marked "verify" were written from general knowledge and must be checked against India Code
- general information only, not legal advice

---

## 🚀 How to Run

### 1. Prerequisites & Installation
Ensure Python 3.11–3.13 and [Ollama](https://ollama.com/) are installed on macOS or Linux:

```bash
git clone https://github.com/Atlas191/Legal-RIghts-Assistant-.git
cd Legal-RIghts-Assistant-

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Pull the Ollama Model
Start the Ollama daemon and pull the generation model:
```bash
ollama pull llama3
```

### 3. Build the Vector Index
Run `scripts/ingest.py` to index the 11 knowledge base files into ChromaDB:
```bash
python scripts/ingest.py
```
*Output: `135 sections -> 165 child chunks` indexed into `./chroma_db`.*

### 4. Interactive CLI Application
Run the interactive console demo:
```bash
python scripts/demo.py
```
To run with local LLM answer generation:
```bash
python scripts/demo.py --llm
```

### 5. FastAPI Web Service (API)
Start the production FastAPI application:
```bash
uvicorn lra.api:app --host 127.0.0.1 --port 8000
```
Access interactive Swagger UI documentation at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

#### Endpoint Overview
| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health status, indexed KB counts, Ollama connectivity, translation status |
| `GET` | `/api/examples` | Curated sample queries across English and Hindi with system disclaimer |
| `POST` | `/api/ask` | Primary conversational legal query endpoint with routing and roadmaps |
| `POST` | `/api/draft` | Deterministic formal complaint drafting with entity extraction |
| `DELETE` | `/api/session/{session_id}` | Clears active in-memory conversation session history |

#### Environment Variables
- `ALLOWED_ORIGINS`: Comma-separated CORS origins (default: `"http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"`).
- `WARM_OLLAMA`: Pre-warms Ollama model in background daemon thread on startup (default: `"1"`). Set to `"0"` to disable.
- `ANSWER_TRANSLATION`: Opt-in experimental translation of answers into Hindi/Hinglish (default: `"off"`). Set to `"on"`, `"1"`, or `"true"` to enable.

---

## 🧪 Evaluation & Test Results

The project is verified by automated test suites:

| Test Suite | File | Count | Status | Description |
|---|---|---|---|---|
| **Language & Translation** | `tests/unit/test_lang.py` | **14 / 14** | PASS | Script detection, Hinglish marker density, echo rejection, opt-in flag. |
| **Draft Generation** | `tests/unit/test_draft.py` | **17 / 17** | PASS | SHO/ICC/LCC templates, placeholder validation, entity extraction. |
| **Roadmap Generation** | `tests/unit/test_roadmap.py` | **8 / 8** | PASS | Three-tier procedural roadmap, basis tagging, time limits. |
| **Legal Forum Routing** | `tests/unit/test_routing.py` | **15 / 15** | PASS | Category routing, headcount-based ICC/LCC rules, clarification questions. |
| **Pipeline Integration** | `tests/unit/test_pipeline.py` | **9 / 9** | PASS | Stateless orchestration, follow-up joins, statute bypass, privacy logging. |
| **Answer Verification** | `tests/unit/test_generate.py` | **13 / 13** | PASS | Core citation validation, section checking, advice & leakage rejection. |
| **FastAPI Layer** | `tests/unit/test_api.py` | **13 / 13** | PASS | Endpoints, session TTL, CORS, privacy logging, 503 semaphore, OpenAPI. |
| **Golden Regression** | `tests/eval/run_golden.py` | **31 / 33 (2 known failures: bank account, pan card)** | 2 known | 31 passed, 2 known off-topic leaks (`bank account`, `pan card`). |
| **Smoke Demo (End-to-End)**| `tests/eval/smoke_demo.py` | **8 / 8** | PASS | Live Ollama evaluation table, follow-up resolution, draft generation. |

Run all unit tests:
```bash
python tests/unit/test_lang.py
python tests/unit/test_draft.py
python tests/unit/test_roadmap.py
python tests/unit/test_routing.py
python tests/unit/test_pipeline.py
python tests/unit/test_generate.py
python tests/unit/test_api.py
python tests/eval/run_golden.py
```

Run the end-to-end smoke demo against local Ollama:
```bash
python tests/eval/smoke_demo.py
```

---

## ⚖️ Legal Notice

*This software is an educational prototype developed for academic and informational purposes. It does not provide legal advice, legal representation, or individualized counseling. For official statutory text, consult the Gazette of India and India Code. For immediate assistance in danger or distress, contact **112** (All-India Emergency) or **181** / **1091** (Women Helpline).*
