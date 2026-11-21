# Integration Guide — Legal Rights Assistant

This document tells the **API layer** developer how to plug the AI pipeline into a
FastAPI (or any Python) backend.

---

## 1. Schemas (`schemas.py`)

| Model           | Fields | Description |
|-----------------|--------|-------------|
| `Turn`          | `role: Literal["user", "assistant"]`, `text: str` | Conversation history turn |
| `Source`        | `id: str`, `heading: str`, `act: str`, `section: str`, `source_file: str`, `text: str = ""`, `formerly_ipc: str = ""` | Individual legal section |
| `Forum`         | `name: str`, `why: str`, `time_limit: str or None = None`, `kb_ref: str`, `category: Literal["safety", "institutional", "criminal", "legal_aid", "national", "other"] = "other"` | Recommended legal forum, helpline, or authority |
| `RoadmapAction` | `text: str`, `basis: Literal["kb", "general_guidance"]`, `kb_ref: str or None = None`, `time_limit: str or None = None` | Specific recommended action in the roadmap |
| `RoadmapStep`   | `step: int`, `kind: Literal["immediate", "institutional", "legal"]`, `title: str`, `actions: list[RoadmapAction]` | Sequential milestone in the assistance roadmap |
| `AskResult`     | `off_topic: bool`, `answer: str`, `verified: bool`, `fallback: bool`, `sources: list[Source]`, `disclaimer: str`, `resolved_query: str`, `cited_source_ids: list[str] = []`, `routing: list[Forum] = []`, `needs_info: list[str] = []`, `roadmap: list[RoadmapStep] = []`, `detected_lang: str = "en"`, `response_lang: str = "en"`, `answer_en: str or None = None`, `translation_verified: bool or None = None` | Pipeline output |
| `DraftRequest`  | `narrative: str`, `recipient: Literal["SHO", "ICC", "LCC", "Protection Officer"] or None = None`, `details: dict[str, str] = {}` | Complaint / petition drafting input request |
| `DraftField`    | `key: str`, `label: str`, `value: str`, `is_placeholder: bool`, `source: Literal["user_form", "user_text", "placeholder"]` | Structured field metadata for complaint template |
| `DraftResult`   | `recipient: str`, `recipient_title: str`, `subject: str`, `fields: list[DraftField]`, `body: str`, `missing_fields: list[str]`, `notes: list[str]`, `references: list[str]`, `disclaimer: str` | Complete draft complaint / petition with placeholders |

> [!IMPORTANT]
> `AskResult.disclaimer` is always returned — the frontend must display it.

### Citation Mapping (`[S#]`)
- In `answer`, legal assertions cite sources as `[S1]`, `[S2]`, etc.
- **Position-based mapping**: `[S#]` maps to `sources` by 1-based index (e.g. `[S1]` refers to `sources[0]`, `[S2]` refers to `sources[1]`).
- `cited_source_ids`: List of `Source.id` strings actually cited in `answer`.

### Forum Routing & Clarification Questions (`routing` & `needs_info`)
- `routing`: List of `Forum` objects ordered by category:
  1. Urgent safety (e.g. One Stop Centre / Women Helpline 181)
  2. Institutional (e.g. Internal Complaints Committee, Local Complaints Committee, Protection Officer / Magistrate under PWDVA)
  3. Criminal (e.g. Police station FIR, Superintendent of Police / Magistrate, National Cyber Crime Reporting Portal)
  4. Legal aid (e.g. District Legal Services Authority free legal aid)
  5. National Commission for Women (NCW)
- `needs_info`: List of specific clarification questions the UI should prompt the user with (for example, `"How many people work at your workplace?"` when workplace headcount is unknown, to differentiate between an ICC and an LCC).
- **Handling `needs_info` in UI**: When `needs_info` is non-empty, the UI should display the question(s) to the user. The user's answer is then sent as a standard `/ask` query **with the existing `history`**; the pipeline joins it to the prior message (e.g. `"my boss keeps touching me at work we are 40 people"`) and re-routes to the precise forum (e.g. resolving ICC vs LCC).
- Both fields default to empty lists (`[]`) on off-topic queries.

### Actionable Roadmap (`roadmap`)
- Structured sequential guidance renumbered `1..n` omitting empty stages:
  1. **Immediate steps** (`kind: "immediate"`): Emergency 112 guidance (if safety forum or danger words present) and evidence preservation (date/time logs, screenshots, medical reports, receipts).
  2. **Institutional pathway** (`kind: "institutional"`): Internal / Local Committees, Protection Officers, and clarification follow-ups.
  3. **Legal and judicial pathway** (`kind: "legal"`): Police FIR, SP/Magistrate escalations, Cybercrime Portal, DLSA free legal aid, and NCW.
- **Display Rule for `basis`**:
  - `basis == "kb"`: Backed directly by statutory or regulatory knowledge base chunks (`kb_ref`).
  - `basis == "general_guidance"`: Practical non-statutory steps (e.g. evidence preservation). **The UI must display these as non-statutory advice** (e.g. labeled as general practical guidance, not a legal requirement).
- `roadmap` is empty (`[]`) for off-topic queries or purely informational queries with no forums (such as maternity leave).

### Formal Draft Generation (`DraftResult`)
- Fixed-template formal complaint/petition letters addressed to SHO, ICC, LCC, or Protection Officers.
- **Allowed `DraftRequest.details` keys**:
  `letter_date`, `police_station`, `district`, `complainant_name`, `complainant_address`, `complainant_phone`, `respondent_name`, `respondent_designation`, `workplace_name`, `incident_date`, `incident_time`, `incident_place`, `witnesses`.
  - Values must be $\le 200$ characters. Whitespace and newlines are collapsed to single spaces. Keys outside this list are ignored.
- **UI Editing & Placeholders**: The UI **should let the user edit every `[bracketed]` item** and **must show `missing_fields`** (keys whose `is_placeholder == True`) as prompts or highlighted fields so the user knows what details remain to be filled before printing or submitting.
- **Form Refinement Lifecycle**: After the user fills in the placeholders, send the same narrative with the filled values in `"details"` to `POST /api/draft` again; the letter is regenerated from the fixed template with user values substituting the bracketed placeholders.
- `references`: Possibly relevant sections, retrieved from the knowledge base (up to 3 headings from `retrieve()`), or `[]` when no search is provided.
- `notes`: Verbatim statutory time limits (for ICC/LCC) or Zero FIR rights (for SHO under BNSS 2023), followed by `"Review every [bracketed] item before you send this letter."`. When workplace headcount is unknown and routing surfaces both ICC and LCC, a reminder note to address LCC if staff $<10$ is included.

#### Sample `POST /api/draft` Request
```json
{
  "narrative": "On 12 March 2026 at about 6 pm in the office cabin my manager touched me inappropriately.",
  "recipient": null,
  "details": {
    "complainant_name": "Priya Sharma",
    "workplace_name": "Acme Technologies"
  }
}
```

#### Sample `POST /api/draft` Response
```json
{
  "recipient": "ICC",
  "recipient_title": "The Presiding Officer, Internal Complaints Committee, Acme Technologies",
  "subject": "Complaint regarding sexual harassment at the workplace",
  "fields": [
    {
      "key": "letter_date",
      "label": "Date of Letter",
      "value": "[Date of Letter]",
      "is_placeholder": true,
      "source": "placeholder"
    },
    {
      "key": "complainant_name",
      "label": "Complainant Name",
      "value": "Priya Sharma",
      "is_placeholder": false,
      "source": "user_form"
    },
    {
      "key": "complainant_address",
      "label": "Complainant Address",
      "value": "[Your Address]",
      "is_placeholder": true,
      "source": "placeholder"
    },
    {
      "key": "complainant_phone",
      "label": "Complainant Phone",
      "value": "[Your Phone Number]",
      "is_placeholder": true,
      "source": "placeholder"
    },
    {
      "key": "respondent_name",
      "label": "Respondent Name",
      "value": "[Name of the Person]",
      "is_placeholder": true,
      "source": "placeholder"
    },
    {
      "key": "respondent_designation",
      "label": "Respondent Designation",
      "value": "manager",
      "is_placeholder": false,
      "source": "user_text"
    },
    {
      "key": "workplace_name",
      "label": "Workplace Name",
      "value": "Acme Technologies",
      "is_placeholder": false,
      "source": "user_form"
    },
    {
      "key": "incident_date",
      "label": "Date of Incident",
      "value": "12 March 2026",
      "is_placeholder": false,
      "source": "user_text"
    },
    {
      "key": "incident_time",
      "label": "Time of Incident",
      "value": "at about 6 pm",
      "is_placeholder": false,
      "source": "user_text"
    },
    {
      "key": "incident_place",
      "label": "Place of Incident",
      "value": "office cabin",
      "is_placeholder": false,
      "source": "user_text"
    },
    {
      "key": "witnesses",
      "label": "Witnesses",
      "value": "[Names of Witnesses, if any]",
      "is_placeholder": true,
      "source": "placeholder"
    }
  ],
  "body": "[Date of Letter]\n\nThe Presiding Officer, Internal Complaints Committee, Acme Technologies\n\nSubject: Complaint regarding sexual harassment at the workplace\n\nRespected Sir/Madam,\n\nI, Priya Sharma, am submitting this formal complaint regarding an incident that occurred against me.\n\nDetails of the incident:\n- Name of the person: [Name of the Person]\n- Designation or relationship: manager\n- Workplace: Acme Technologies\n- Date: 12 March 2026\n- Time: at about 6 pm\n- Place: office cabin\n- Witnesses: [Names of Witnesses, if any]\n\nDescription of the incident (in my own words):\nOn 12 March 2026 at about 6 pm in the office cabin my manager touched me inappropriately.\n\nI request you to take appropriate action as per law.\n\nYours faithfully,\nPriya Sharma\nAddress: [Your Address]\nPhone: [Your Phone Number]",
  "missing_fields": [
    "letter_date",
    "complainant_address",
    "complainant_phone",
    "respondent_name",
    "witnesses"
  ],
  "notes": [
    "3 months from the last incident, extendable by up to 3 months for reasons recorded in writing (verify)",
    "If your workplace has fewer than 10 employees, or the complaint is against the employer, address this letter to the Local Complaints Committee instead.",
    "Review every [bracketed] item before you send this letter."
  ],
  "references": [],
  "disclaimer": "This information is for guidance only and does not constitute formal legal advice. Laws and procedures may vary; consult a qualified advocate or your local Legal Services Authority for advice on your specific situation."
}
```

### Multilingual Support (Hindi & Hinglish)
- **Supported Languages**: English (`"en"`), Hindi in Devanagari script (`"hi"`), and Romanized Hindi (`"hinglish"`).
- **Default Behavior**: Hindi and Hinglish queries are understood and answered in English by default (`response_lang: "en"`).
- **Fixed Strings**: Refusal (`OFF_TOPIC`) and disclaimer (`DISCLAIMER`) messages in Hindi and Hinglish use verified, static fixed strings.
- **Experimental Answer Translation (`ANSWER_TRANSLATION=on`)**:
  - Translating the generated legal answer into Hindi or Hinglish is **opt-in and experimental** (enabled only when the environment variable `ANSWER_TRANSLATION` is set to `"on"`, `"1"`, or `"true"`).
  - Small local models produce unreliable Hindi in practice; automated verification checks citation markers (`[S#]`) and section numbers, but **cannot detect semantic distortions or incorrect legal meanings**.
  - Similarly, the generated English answer can also misread a source (verification validates citations and numeric sequences only), so the **statutory sources returned alongside the answer are always the authoritative and reliable part**.
- `AskRequest.response_lang`: `"auto"` (default), `"en"`, `"hi"`, or `"hinglish"`.
- **`AskResult` Language Fields**:
  - `detected_lang`: Detected language of the query (`"en"`, `"hi"`, or `"hinglish"`).
  - `response_lang`: Language the `answer` is actually returned in (remains `"en"` when `ANSWER_TRANSLATION=off`).
  - `answer_en`: English original answer (`str | None`), populated only when answer translation is opted in and succeeds.
  - `translation_verified`: `True` if translated answer passed verification, `False` if translation failed verification (reverting to English), or `None` when answer translation is disabled or the answer is in English.
- **Routing & Roadmap in English**: Forum recommendations (`routing`) and sequential milestones (`roadmap`) remain in English for institutional consistency.
- **UI "Show English original" toggle**: If answer translation is enabled, the UI should offer an intuitive toggle switch using `answer_en` so users can easily inspect the verified English source text alongside the Hindi or Hinglish translation.
- **Drafting Support**: Non-English narratives in `DraftRequest` are translated into English for recipient determination and routing, but the complainant's narrative is preserved verbatim in the body of the generated letter. Form fields without English equivalents remain placeholders.
- **Latency Impact**: Enabling answer translation introduces one extra LLM translation call (~5 to 15 s).

---

## 2. Response Status Flow

Always check `off_topic` **before** checking `fallback`:

```
if result.off_topic:
    # Query is out of domain (e.g. taxes, passport).
    # result.answer contains polite refusal & suggested topics.
    # result.sources == [], result.cited_source_ids == [], result.routing == [], result.needs_info == [], result.roadmap == []
elif result.fallback:
    # Query was on-topic, but LLM generation failed or failed verification.
    # result.answer contains fallback text with retrieved headings.
    # result.sources contains the retrieved sections.
else:
    # Success: verified plain-language answer citing retrieved sources.
```

---

## 3. Pipeline API

```python
from pipeline import get_pipeline
from schemas import Turn

pipe = get_pipeline()          # cached singleton; first call loads embeddings & ChromaDB (~3-5 s)
result = pipe.ask("my husband beats me")
# result is an AskResult instance
```

### Follow-ups & Lookup Queries

Pass the previous conversation turns as `history`:

```python
result = pipe.ask(
    "can they demand dowry money",
    history=[
        Turn(role="user", text="my husband beats me"),
        Turn(role="assistant", text="Here are relevant sections..."),
    ],
)
# result.resolved_query == "my husband beats me can they demand dowry money"
```

- **Follow-up join rule**: When `history` contains a previous user query and the current query has `< 8` words, it is joined with the previous query. Short answers or numbers (e.g. `"40"` or `"we are 40 people"`) sent in response to `needs_info` are automatically joined, refining retrieval and routing.
- **Statute lookups bypass follow-up**: Direct statutory references (e.g., `"498A"`, `"66E"`, `"Section 85"`, `"sec 12"`, `"BNS 85"`) are recognized via pattern matching and skip the join, ensuring specific lookups remain focused.
- **Stateless**: The pipeline stores no history. The API layer owns user sessions.

### Input Validation & Errors

| Condition | Behaviour |
|-----------|-----------|
| Empty / whitespace-only query | `ValueError("Query must not be empty.")` |
| Query > 1000 characters | `ValueError("Query must not exceed 1000 characters.")` |

---

## 4. FastAPI Example

Always use a **plain `def`** endpoint (not `async def`). `LegalPipeline.ask()` executes
CPU-bound search (embeddings, BM25) and blocking HTTP calls to Ollama. A plain `def` endpoint
runs in FastAPI's external threadpool, preventing blocking of the async event loop.

```python
from typing import Literal
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from schemas import Turn, AskResult, DraftRequest, DraftResult
from pipeline import get_pipeline
from draft import build_draft

@asynccontextmanager
async def lifespan(app: FastAPI):
    get_pipeline()          # warm up on startup
    yield

app = FastAPI(lifespan=lifespan)

class AskRequest(BaseModel):
    query: str
    history: list[Turn] = []
    response_lang: Literal["auto", "en", "hi", "hinglish"] = "auto"

@app.post("/api/ask", response_model=AskResult)
def ask(req: AskRequest):
    try:
        return get_pipeline().ask(req.query, req.history or None, response_lang=req.response_lang)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@app.post("/api/draft", response_model=DraftResult)
def create_draft(req: DraftRequest):
    try:
        # Reuses the warmed-up search instance from the pipeline singleton
        search_fn = get_pipeline().search
        return build_draft(req, search=search_fn)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
```

---

## 5. Verification Limits & Safeguards

The generation module applies strict automated verification (`verify_answer`):
1. **Citation requirement**: The answer must contain at least one `[S#]` citation.
2. **Citation range**: Any `[S#]` must be in range `1..len(sources)`.
3. **Statutory section check**: Every mention of `"Section <n>"` (case-insensitive) in the answer must appear in the retrieved sources (matched with non-alphanumeric boundary check, so e.g. `"Section 12"` will not falsely match `"Section 124"`).
4. **Regeneration on failure**: If verification fails, the model is re-prompted once with the allowed citation IDs and the failure reason. If it fails a second time, `fallback=True` is returned with raw retrieved headings.

---

## 6. Privacy Rule

> [!CAUTION]
> **Never log request bodies.** The pipeline already avoids logging query text,
> answers, and history. The API layer must follow the same rule — log only
> status codes, timings, and outcomes.

---

## 7. Performance Notes

| Step | Typical Latency |
|------|----------------|
| First `get_pipeline()` call | 3–5 s (loads embeddings + ChromaDB) |
| Retrieval (`retrieve()`) | 50–200 ms |
| LLM generation (Ollama, `llama3`) | 5–30 s (with `keep_alive: "30m"`, timeout 120s) |
| Translation (Hindi/Hinglish) | 5–15 s (adds ~1 extra LLM call) |

- The first call to Ollama may take slightly longer while the model weights are loaded into memory. With `"keep_alive": "30m"`, subsequent requests keep the model warm.
- Off-topic queries skip LLM generation entirely and return in < 200 ms.
