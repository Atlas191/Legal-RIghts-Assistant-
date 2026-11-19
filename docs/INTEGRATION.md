# Integration Guide — Legal Rights Assistant

This document tells the **API layer** developer how to plug the AI pipeline into a
FastAPI (or any Python) backend.

---

## 1. Schemas (`schemas.py`)

| Model           | Fields | Description |
|-----------------|--------|-------------|
| `Turn`          | `role: Literal["user", "assistant"]`, `text: str` | Conversation history turn |
| `Source`        | `id: str`, `heading: str`, `act: str`, `section: str`, `source_file: str`, `text: str = ""`, `formerly_ipc: str = ""` | Individual legal section |
| `Forum`         | `name: str`, `why: str`, `time_limit: str | None = None`, `kb_ref: str`, `category: Literal["safety", "institutional", "criminal", "legal_aid", "national", "other"] = "other"` | Recommended legal forum, helpline, or authority |
| `RoadmapAction` | `text: str`, `basis: Literal["kb", "general_guidance"]`, `kb_ref: str | None = None`, `time_limit: str | None = None` | Specific recommended action in the roadmap |
| `RoadmapStep`   | `step: int`, `kind: Literal["immediate", "institutional", "legal"]`, `title: str`, `actions: list[RoadmapAction]` | Sequential milestone in the assistance roadmap |
| `AskResult`     | `off_topic: bool`, `answer: str`, `verified: bool`, `fallback: bool`, `sources: list[Source]`, `disclaimer: str`, `resolved_query: str`, `cited_source_ids: list[str] = []`, `routing: list[Forum] = []`, `needs_info: list[str] = []`, `roadmap: list[RoadmapStep] = []` | Pipeline output |

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
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from schemas import Turn, AskResult
from pipeline import get_pipeline

@asynccontextmanager
async def lifespan(app: FastAPI):
    get_pipeline()          # warm up on startup
    yield

app = FastAPI(lifespan=lifespan)

class AskRequest(BaseModel):
    query: str
    history: list[Turn] = []

@app.post("/ask", response_model=AskResult)
def ask(req: AskRequest):
    try:
        return get_pipeline().ask(req.query, req.history or None)
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

- The first call to Ollama may take slightly longer while the model weights are loaded into memory. With `"keep_alive": "30m"`, subsequent requests keep the model warm.
- Off-topic queries skip LLM generation entirely and return in < 200 ms.
