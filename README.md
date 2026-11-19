# Legal Rights Assistant for Women (LRA) ⚖️

> **An AI-powered legal awareness and structured assistance platform providing Indian women with plain-language legal guidance, statutory mapping, and procedural navigation under Indian criminal and civil law.**

---

## 📌 Project Overview & Objectives

Navigating legal remedies in India can be daunting for non-lawyers, especially during times of crisis. Women facing harassment, domestic violence, digital abuse, or workplace discrimination often struggle to identify:
1. Which specific laws and sections protect them.
2. How the transition from the old **Indian Penal Code (IPC)** to the newly enacted **Bharatiya Nyaya Sanhita, 2023 (BNS)** affects their complaint.
3. The exact competent authorities, timelines, and relief measures available.

**Legal Rights Assistant for Women (LRA)** bridges the gap between everyday natural-language incident descriptions and formal statutory provisions. It delivers reliable, grounded, and empathetic legal information while strictly preventing hallucinations and out-of-scope misuse.

### 🌐 UN Sustainable Development Goals (SDG) Alignment
- **SDG 5 (Gender Equality)**:
  - **Target 5.1**: End all forms of discrimination against all women and girls everywhere.
  - **Target 5.2**: Eliminate all forms of violence against all women and girls in public and private spheres.
- **SDG 16 (Peace, Justice and Strong Institutions)**:
  - **Target 16.3**: Promote the rule of law at the national and international levels and ensure equal access to justice for all.

---

## 🏛️ Knowledge Base & Legal Scope

The system retrieves exclusively from 11 authoritative, metadata-tagged legal documents located in `./knowledge_base/`:

| Source File | Statute / Mandate | Key Provisions Covered |
|---|---|---|
| `bns_2023.md` | **Bharatiya Nyaya Sanhita, 2023 (BNS)** | Chapter V offences against women and children: Rape (s.63–64), Outraging modesty (s.74), Sexual harassment (s.75), Voyeurism (s.77), Stalking (s.78), Dowry death (s.80), Cruelty by husband/in-laws (s.85–86 replacing IPC 498A), Acid attack (s.124). |
| `bnss_2023.md` | **Bharatiya Nagarik Suraksha Sanhita, 2023 (BNSS)** | Criminal procedure for women: Mandatory FIR & Zero FIR (s.173), Remedies if police refuse FIR (s.173(4)), Magistrate statements by woman magistrate (s.183), Medical examination (s.184), Victim compensation & free treatment (s.396), In-camera trial (s.366). |
| `pwdva_2005.md` | **Protection of Women from Domestic Violence Act, 2005 (PWDVA)** | Definitions of domestic violence (s.3), Application to Magistrate (s.12), Residence orders (s.17 & 19), Protection orders (s.18), Monetary relief (s.20). |
| `posh_handbook.md` | **POSH Act 2013 & MWCD Handbook** | Aggrieved woman definition, workplace scope, Internal Committee (IC) vs Local Committee (LC), 3-month filing timeline, employer obligations. |
| `posh_act_supplement.md` | **POSH Act, 2013 (Act Provisions Supplement)** | Statutory gaps filled: 3-month complaint timeline extension criteria (s.9), mandatory ICC establishment thresholds (s.4), no monetary settlement in conciliation (s.10). |
| `dowry_prohibition_1961.md` | **Dowry Prohibition Act, 1961** | Definition of dowry (s.2), penalties for giving/taking/demanding dowry (s.3–4), dowry agreement void (s.5), transfer of dowry to the woman or her heirs (s.6). |
| `nalsa_charter.md` | **Legal Services Authorities Act, 1987 & NALSA** | Free legal aid entitlement for all women under Section 12(c), legal aid clinics, DLSA/SLSA application procedure, and free legal services helpline (15100). |
| `helplines_and_portals.md` | **Emergency Helplines & Portals Directory** | Centralized directory: National Emergency (112), Women Helpline (1091/181), Cybercrime portal (cybercrime.gov.in / 1930), National Legal Aid (15100), SHe-Box portal. |
| `it_act_2000.md` | **Information Technology Act, 2000 (IT Act)** | Violation of privacy & hidden cameras (s.66E), Obscene electronic transmissions (s.67), Sexually explicit acts online / revenge porn (s.67A), Child sexual abuse material (s.67B). |
| `maternity_benefit_act.md` | **Maternity Benefit Act, 1961 (2017 Amendment)** | 26-week maternity leave entitlement, work from home provisions, protection against unlawful dismissal during pregnancy. |
| `ncw_charter.md` | **National Commission for Women (NCW) Charter** | Citizen charter 2026–2027: Mandates, statutory inquiry powers, and grievance redressal mechanisms. |

---

## ⚙️ Architecture & Technical Pipeline

```
 User Situation Query (e.g. "my boss keeps touching me at work")
                         │
                         ▼
        ┌──────────────────────────────────┐
        │       kb_utils.tokenize()        │
        └────────────────┬─────────────────┘
                         │
        ┌────────────────┴─────────────────┐
        ▼                                  ▼
┌──────────────────┐             ┌──────────────────┐
│ Dense Retrieval  │             │ Sparse Retrieval │
│ bge-small-en-v1.5│             │    BM25Okapi     │
│   (ChromaDB)     │             │  (Child Chunks)  │
└────────┬─────────┘             └────────┬─────────┘
         │                                │
         └────────────────┬───────────────┘
                          ▼
        ┌──────────────────────────────────┐
        │  Multi-Tier Off-Topic Guardrail  │
        │  • Hard & soft semantic cutoffs  │
        │  • Minimum BM25 keyword overlap  │
        │  • Token-length leak prevention  │
        └────────────────┬─────────────────┘
                         │ (If On-Topic)
                         ▼
        ┌──────────────────────────────────┐
        │ Reciprocal Rank Fusion (RRF 60)  │
        │  Child Chunks ──► Parent Section │
        └────────────────┬─────────────────┘
                         │
                         ▼
             Top Relevant Legal Sections
                         │
                         ├─────────────────────────────────────────┐
                         ▼ (Default Mode)                          ▼ (--llm Mode)
                 Structured Sections                      Local Ollama (llama3)
                     CLI Display                                   │
                                                                   ▼
                                                          verify_answer() Guard
                                                          • Exact [S#] citations
                                                          • Anti-hallucination check
                                                                   │
                                                                   ▼
                                                          Verified Plain-Language
                                                          Legal Guidance + Sources
```

### 1. Section-Aware Parent-Child Chunking (`kb_utils.py`)
- Each statutory section or handbook clause is ingested as a distinct **parent section**.
- Parent sections are parsed and subdivided into dense child chunks (`chunk_size=700`, `chunk_overlap=100`), with repeated headings and metadata keywords to retain contextual anchors.
- Robust parsing with strict key allowlists ensures legal text and statutory definitions are never dropped.

### 2. Hybrid Retrieval with Reciprocal Rank Fusion (`retrieval.py`)
- **Dense Semantic Embeddings**: Utilizes `BAAI/bge-small-en-v1.5` running locally via HuggingFace and ChromaDB for semantic understanding of colloquial phrasing.
- **Sparse Lexical Search**: Uses `BM25Okapi` with domain-specific stopword filtering for exact matching of statutory section codes (`498A`, `BNS 75`, `Section 12`).
- **Reciprocal Rank Fusion (RRF)**: Merges dense and sparse rankings ($k=60$) over child chunks, then aggregates evidence back to the parent section for full legal context.

### 3. Multi-Tier Relevance & Off-Topic Guardrails
Prevents arbitrary or unrelated queries from retrieving legal text:
- **Tier 1 (Semantic Distance Cutoff)**: Rejects queries when dense semantic distance exceeds calibrated bounds (`best_dist > 0.75` and `max_bm25 < 5.0`).
- **Tier 2 (Keyword Leakage Shield)**: For multi-token queries with high semantic distance (`best_dist > 0.90`), rejects queries even if incidental common tokens match (preventing queries like *"how can i apply for a new passport or renew my driving licence online"* from matching bigamy or licensing clauses).
- **Lookup Exception**: Short 1–2 token queries (e.g. `"498A"`) are treated as direct section lookups and bypass length restrictions.

### 4. Local LLM Generation & Verification (`generate.py`)
- **Zero Cloud / Privacy-Preserving**: Runs completely locally via **Ollama** (`llama3` / `llama3.2`) with `temperature=0` and 60-second timeouts. No sensitive user queries are ever transmitted to third-party APIs.
- **Privacy-Strict Logging**: Never logs user queries or generated answers; only logs execution timings and outcome statuses.
- **Anti-Hallucination Verification (`verify_answer`)**:
  - Validates that every statement cites a valid source tag `[S#]`.
  - Enforces that citation indices fall within the active range `1..n_sources`.
  - Scans for any mention of `"Section <number><letter>"` and confirms it exists verbatim in the retrieved statutory text.
  - Automatically triggers a one-step self-correction regeneration with exact violation reminders before safely falling back to retrieved section headers.

---

## 📁 Repository Structure

```
Legal_Assistant/
├── knowledge_base/               # Curated, metadata-tagged statutory markdown files (11 files)
│   ├── bns_2023.md               # Bharatiya Nyaya Sanhita, 2023 (Offences against women)
│   ├── bnss_2023.md              # Bharatiya Nagarik Suraksha Sanhita, 2023 (FIR & criminal procedure)
│   ├── dowry_prohibition_1961.md # Dowry Prohibition Act, 1961
│   ├── helplines_and_portals.md  # Helplines, emergency numbers and portals directory
│   ├── it_act_2000.md            # IT Act 2000 (Cyber offences, voyeurism, privacy)
│   ├── maternity_benefit_act.md  # Maternity Benefit Act, 1961
│   ├── nalsa_charter.md          # Legal Services Authorities Act, 1987 (Free legal aid)
│   ├── ncw_charter.md            # National Commission for Women Citizen's Charter
│   ├── posh_act_supplement.md    # POSH Act, 2013 statutory provisions supplement
│   ├── posh_handbook.md          # Sexual Harassment of Women at Workplace (POSH) Handbook
│   └── pwdva_2005.md             # Protection of Women from Domestic Violence Act, 2005
├── tests/
│   ├── run_golden.py             # 28-case regression test suite for retrieval & gates
│   └── test_generate.py          # Unit tests for citation verification logic
├── demo.py                       # Interactive CLI application (with optional --llm mode)
├── generate.py                   # Local Ollama generation, verification, and fallback
├── ingest.py                     # Indexing script: parses KB and builds ChromaDB
├── kb_utils.py                   # Parent-child chunking, front-matter parser, tokenizer
├── retrieval.py                  # Hybrid dense + BM25 search engine with RRF
├── requirements.txt              # Project dependencies
└── README.md                     # Project documentation
```

---

## 🚀 Getting Started

### Prerequisites
- macOS or Linux
- Python 3.11+
- [Ollama](https://ollama.com/) (for `--llm` answer generation)

### 1. Installation
Clone the repository and set up a virtual environment:

```bash
git clone https://github.com/Atlas191/Legal-RIghts-Assistant-.git
cd Legal-RIghts-Assistant-

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Build the Vector Index
Run `ingest.py` to parse all knowledge base files and generate the local ChromaDB database:

```bash
python ingest.py
```
*Expected output: `135 sections -> 165 child chunks` indexed into `./chroma_db`.*

### 3. Setup Ollama (for LLM generation)
Make sure Ollama is running and pull the model:

```bash
ollama pull llama3.2
ollama cp llama3.2 llama3
```

---

## 💻 Running the Assistant

### Mode A: Fast Hybrid Retrieval (Default)
Runs hybrid retrieval and displays relevant statutory sections with sources and disclaimers:

```bash
python demo.py
```

**Example:**
```text
👤 Your situation: 498A

================================================================================================
RELEVANT LEGAL SECTIONS FOUND: 1
================================================================================================

[1] Section 85 — Husband or relative of husband subjecting woman to cruelty
    Law    : Bharatiya Nyaya Sanhita, 2023 (BNS)
    Formerly IPC: 498A
    Source : BNS.pdf (Gazette of India Extraordinary, 102 pages)
    --------------------------------------------------------------------------------------------
    Whoever, being the husband or a relative of the husband of a woman, subjects her to cruelty:
    imprisonment up to three years and fine.
```

### Mode B: Retrieval + Verified Plain-Language Answer (`--llm`)
Pass the `--llm` flag to generate a plain-language explanation cited from retrieved sections:

```bash
python demo.py --llm
```

**Example:**
```text
👤 Your situation: my boss keeps touching me at work

================================================================================================
LEGAL ASSISTANT ANSWER:
================================================================================================
Based on the provided provisions, you are protected under the law:

Your rights under the POSH Act:
According to the Handbook [S1], unwelcome physical contact by a supervisor constitutes sexual
harassment and creates an unlawful hostile work environment.

Defining sexual harassment under criminal law:
The Bharatiya Nyaya Sanhita [S3] defines sexual harassment under Section 75, covering physical
contact with unwelcome sexual overtures or demands for sexual favours.
...

================================================================================================
RELEVANT LEGAL SECTIONS FOUND: 3
================================================================================================
[1] Handbook 2.7 — Scenario: supervisor touching and colleagues' gossip (POSH Act)
[2] Handbook 2.7 — Scenario: boss's advances then humiliation after rejection (POSH Act)
[3] Section 75 — Sexual harassment (BNS 2023)
```

---

## 🧪 Evaluation & Testing

Automated test suites ensure retrieval accuracy and anti-hallucination compliance:

### 1. Retrieval & Gate Regression Suite (`run_golden.py`)
Evaluates 28 representative legal scenarios and off-topic adversarial queries:
```bash
python tests/run_golden.py
```
```text
  [PASS] '498A'                                           -> matches Section 85
  [PASS] 'capital of india'                               -> refused (off-topic)
  [PASS] 'how can i apply for a new passport...'          -> refused (off-topic)
  [PASS] 'how do i file my income tax return'             -> refused (off-topic)
  [PASS] 'my boss keeps touching me at work'              -> matches POSH
  [PASS] 'my husband beats me and threw me out'           -> matches PWDVA
  [PASS] 'someone is sending me obscene messages online'  -> matches IT Act
  [PASS] 'can my employer fire me for being pregnant'     -> matches Maternity Benefit
  [PASS] 'a man keeps following me and calling me'        -> matches Section 78 (Stalking)
  [PASS] 'someone shared my private photos without consent' -> matches 66E
  [PASS] 'what can the National Commission for Women do'  -> matches NCW / Helplines
  [PASS] 'how long do I have to file a complaint at work' -> matches POSH
  [PASS] 'police refused to register my FIR'              -> matches Bharatiya Nagarik Suraksha
  [PASS] "I can't afford a lawyer"                        -> matches Legal Services
  [PASS] 'what number do I call for help'                 -> matches Helplines
  [PASS] 'my complaint is more than three months old...'  -> matches POSH
  [FAIL] 'how to open a bank account'                     -> dist=0.81, bm25=8.3 (leaked via PWDVA/NALSA bank/apply clauses)
  [PASS] 'what is the best way to invest in mutual funds' -> refused (off-topic)
  [FAIL] 'how to apply for a pan card online'             -> dist=0.72, bm25=7.7 (leaked via NALSA/SHe-Box portal)
  [PASS] "my husband's family keeps demanding more dowry" -> matches Dowry
  [PASS] 'he threatens to post my photos if I leave him'  -> matches Criminal intimidation
  [PASS] 'my manager asks for sexual favours in return...'-> matches Sexual harassment
  [PASS] 'my employer did not give me maternity leave'    -> matches Maternity
  [PASS] 'someone is stalking me on instagram'            -> matches Stalking
  [PASS] 'how do I report a cyber crime'                  -> matches cybercrime
  [PASS] 'my husband is not paying maintenance'           -> matches Maintenance
  [PASS] 'can I get free legal help for domestic violence'-> matches Legal Services
  [PASS] 'I was thrown out of my in-laws house'           -> matches Domestic Violence

26/28 passed.
```

### 2. Citation Verification Unit Tests (`test_generate.py`)
Validates that `verify_answer()` correctly accepts grounded answers and rejects hallucinated section numbers or invalid citations:
```bash
python tests/test_generate.py
```
```text
  [PASS] valid cited answer passes
  [PASS] no citations fails
  [PASS] [S9] with 3 sources fails
  [PASS] an answer citing "Section 999" not in sources fails
  [PASS] "Section 85" present in a source passes

5/5 passed.
```

---

## ⚖️ Disclaimer

*This application is an educational prototype developed as a college capstone project. It provides general legal information and statutory mapping based on official gazette notifications and government handbooks, not personalized legal advice. In situations involving immediate danger or domestic emergencies, please dial the national emergency response number **112** or the Women Helpline **1091**.*
