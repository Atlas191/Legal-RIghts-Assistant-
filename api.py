"""FastAPI application layer for Legal Rights Assistant for Women (LRA).
Provides plain-language legal awareness and procedural guidance under Indian law.
Zero-retention privacy: never logs user query text, answers, or session narratives.
"""
from contextlib import asynccontextmanager
import logging
import os
import threading
import time
import uuid

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

import generate
import kb_utils
import lang
import pipeline
from pipeline import get_pipeline
from draft import build_draft
from schemas import Turn, DraftRequest, DraftResult
from api_schemas import (
    AskRequest,
    AskResponse,
    HealthResponse,
    ExampleItem,
    ExamplesResponse,
)

logger = logging.getLogger("api")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [api] %(message)s", datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _pipe():
    """Module-level accessor for pipeline singleton, easily replaced by tests."""
    return get_pipeline()


# Pre-compute KB chunks and sections once at startup
_kb_chunks_list = kb_utils.load_chunks()
_KB_CHUNKS = len(_kb_chunks_list)
_KB_SECTIONS = len({c.metadata["parent_id"] for c in _kb_chunks_list})


# --- In-Memory Session Management ---
SESSION_TTL_SECONDS = 30 * 60  # 30 minutes
MAX_SESSIONS = 500
MAX_TURNS_PER_SESSION = 10
TRUNCATE_ANSWER_LENGTH = 500

_sessions_lock = threading.Lock()
_sessions: dict[str, dict] = {}


def _purge_expired_sessions_locked(now: float) -> None:
    expired = [sid for sid, data in _sessions.items() if (now - data["last"]) > SESSION_TTL_SECONDS]
    for sid in expired:
        del _sessions[sid]


def purge_expired_sessions(now: float | None = None) -> None:
    if now is None:
        now = time.monotonic()
    with _sessions_lock:
        _purge_expired_sessions_locked(now)


def get_session_turns(session_id: str | None) -> list[Turn] | None:
    if not session_id:
        return None
    now = time.monotonic()
    with _sessions_lock:
        _purge_expired_sessions_locked(now)
        sdata = _sessions.get(session_id)
        if sdata is not None:
            sdata["last"] = now
            return list(sdata["turns"])
        return None


def save_session_turn(session_id: str, query: str, answer: str) -> None:
    now = time.monotonic()
    with _sessions_lock:
        _purge_expired_sessions_locked(now)
        if session_id not in _sessions and len(_sessions) >= MAX_SESSIONS:
            oldest_sid = min(_sessions.keys(), key=lambda sid: _sessions[sid]["last"])
            del _sessions[oldest_sid]

        truncated_answer = answer[:TRUNCATE_ANSWER_LENGTH] if answer else ""
        sdata = _sessions.setdefault(session_id, {"turns": [], "last": now})
        sdata["last"] = now
        sdata["turns"].append(Turn(role="user", text=query))
        sdata["turns"].append(Turn(role="assistant", text=truncated_answer))
        if len(sdata["turns"]) > MAX_TURNS_PER_SESSION:
            sdata["turns"] = sdata["turns"][-MAX_TURNS_PER_SESSION:]


def delete_session(session_id: str) -> bool:
    with _sessions_lock:
        if session_id in _sessions:
            del _sessions[session_id]
            return True
        return False


# --- Global Concurrency Guard ---
_ask_semaphore = threading.BoundedSemaphore(2)


# --- Lifespan ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Call get_pipeline() once at startup
    try:
        _pipe()
    except Exception:
        pass

    warm_ollama = os.environ.get("WARM_OLLAMA", "1").lower() in ("1", "true", "yes", "on")
    if warm_ollama:
        def _warm():
            t0 = time.time()
            try:
                generate._call_ollama([{"role": "user", "content": "hi"}])
                elapsed = time.time() - t0
                logger.info("warmup done in %.2f s", elapsed)
            except Exception:
                pass

        t = threading.Thread(target=_warm, daemon=True)
        t.start()
    else:
        logger.info("warmup skipped")
    yield


app = FastAPI(
    title="Legal Rights Assistant API",
    version="1.0",
    description=(
        "AI-powered legal awareness and procedural guidance platform for women in India. "
        "Answers are grounded strictly in retrieved statutory sources and official handbooks with automated verification. "
        "This service provides general legal information only and does not constitute formal legal advice."
    ),
    lifespan=lifespan,
    openapi_tags=[
        {"name": "chat", "description": "Interactive legal queries, conversation turns, and sessions"},
        {"name": "draft", "description": "Deterministic legal petition and complaint drafting"},
        {"name": "system", "description": "Service health, index statistics, and sample queries"},
    ],
)

# --- CORS ---
allowed_origins_env = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
)
allowed_origins = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request Logging Middleware ---
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    req_id = uuid.uuid4().hex[:8]
    purge_expired_sessions()
    t0 = time.time()
    try:
        response = await call_next(request)
    except Exception as exc:
        duration_ms = int((time.time() - t0) * 1000)
        err_cls = exc.__class__.__name__
        logger.error(
            "%s %s 500 %dms %s %s",
            request.method,
            request.url.path,
            duration_ms,
            req_id,
            err_cls,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Something went wrong. Please try again."},
            headers={"X-Request-ID": req_id},
        )

    duration_ms = int((time.time() - t0) * 1000)
    response.headers["X-Request-ID"] = req_id
    err_cls = getattr(request.state, "error_class", None)
    if err_cls:
        logger.error(
            "%s %s %d %dms %s %s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            req_id,
            err_cls,
        )
    else:
        logger.info(
            "%s %s %d %dms %s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            req_id,
        )
    return response


# --- Endpoints ---
def _check_ollama_reachable() -> bool:
    tags_url = generate.OLLAMA_URL.replace("/api/chat", "/api/tags")
    try:
        resp = requests.get(tags_url, timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
def health():
    return HealthResponse(
        status="ok",
        kb_sections=_KB_SECTIONS,
        kb_chunks=_KB_CHUNKS,
        ollama_reachable=_check_ollama_reachable(),
        answer_translation=lang.answer_translation_enabled(),
    )


EXAMPLES_LIST = [
    ExampleItem(label="Private photos shared", query="Someone shared my private photos without my consent", lang="en"),
    ExampleItem(label="Free legal aid", query="I can't afford a lawyer", lang="en"),
    ExampleItem(label="Dowry demands", query="My husband's family keeps demanding more dowry", lang="en"),
    ExampleItem(label="Maintenance", query="My husband is not paying maintenance", lang="en"),
    ExampleItem(label="Harassment at work", query="My boss keeps touching me at work", lang="en"),
    ExampleItem(label="Hindi example", query="मेरे पति मुझे मारते हैं और घर से निकाल दिया", lang="hi"),
]


@app.get("/api/examples", response_model=ExamplesResponse, tags=["chat"])
def examples():
    return ExamplesResponse(examples=EXAMPLES_LIST, disclaimer=pipeline.DISCLAIMER)


@app.post("/api/ask", response_model=AskResponse, tags=["chat"])
def ask_endpoint(req: AskRequest, request: Request):
    # Pick history: stored turns if session_id is given and known, else req.history
    stored_turns = get_session_turns(req.session_id)
    if stored_turns is not None:
        history = stored_turns
    else:
        history = req.history or None

    acquired = _ask_semaphore.acquire(timeout=30.0)
    if not acquired:
        raise HTTPException(
            status_code=503,
            detail="The assistant is busy, please try again in a moment.",
        )
    try:
        try:
            result = _pipe().ask(
                query=req.query,
                history=history,
                response_lang=req.response_lang,
            )
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
        except HTTPException:
            raise
        except Exception as e:
            request.state.error_class = type(e).__name__
            raise HTTPException(
                status_code=500,
                detail="Something went wrong. Please try again.",
            )
    finally:
        _ask_semaphore.release()

    effective_session_id = req.session_id or uuid.uuid4().hex
    if not result.off_topic:
        save_session_turn(effective_session_id, req.query, result.answer)

    return AskResponse(
        **result.model_dump(),
        session_id=effective_session_id,
    )


@app.delete("/api/session/{session_id}", tags=["chat"])
def delete_session_endpoint(session_id: str):
    return {"deleted": delete_session(session_id)}


@app.post("/api/draft", response_model=DraftResult, tags=["draft"])
def draft_endpoint(req: DraftRequest, request: Request):
    try:
        search_engine = getattr(_pipe(), "search", None)
        return build_draft(req, search=search_engine)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        request.state.error_class = type(e).__name__
        raise HTTPException(
            status_code=500,
            detail="Something went wrong. Please try again.",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)
