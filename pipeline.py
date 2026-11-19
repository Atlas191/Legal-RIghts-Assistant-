"""Legal Rights Assistant pipeline — stateless orchestrator.
Loads retrieval once, resolves follow-ups, calls generate, returns structured AskResult.
Never logs query text, answers, or history. Logs only timing and outcome."""
import logging
import re
import time

from schemas import Turn, Source, Forum, AskResult
from retrieval import load_search, retrieve
from generate import answer as generate_answer
from routing import route

logger = logging.getLogger("pipeline")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [pipeline] %(message)s", datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

DISCLAIMER = "General legal information only, not legal advice. In an emergency call 112."
FOLLOW_UP_TOKEN_LIMIT = 8  # queries shorter than this + prior turn → resolved as follow-up

OFF_TOPIC_ANSWER = (
    "I'm a legal assistant for women's rights in India, so I can't help with that question. "
    "Try describing a situation about harassment at work, domestic violence, stalking, "
    "online abuse, dowry harassment, maternity rights, police procedure, or free legal aid."
)


class LegalPipeline:
    """Stateless pipeline: the caller (API layer) owns sessions and history."""

    def __init__(self):
        logger.info("Loading search engine (one-time heavy step)...")
        t0 = time.time()
        self._search = load_search()
        logger.info("Search engine loaded in %.2fs", time.time() - t0)

    def ask(self, query: str, history: list[Turn] | None = None) -> AskResult:
        """Answer a user query. Stateless — caller provides history if needed."""
        # --- Input validation ---
        q = query.strip()
        if not q:
            raise ValueError("Query must not be empty.")
        if len(q) > 1000:
            raise ValueError("Query must not exceed 1000 characters.")

        # --- Follow-up resolution ---
        resolved_query = q
        is_lookup = bool(
            re.fullmatch(r"(?i)\s*((section|sec|ipc|bns|bnss|s\.?)\s*)?\d{1,3}[a-z]{1,2}\s*", q)
            or re.fullmatch(r"(?i)\s*(section|sec|ipc|bns|bnss|s\.?)\s*\d{1,3}[a-z]{0,2}\s*", q)
        )
        if not is_lookup and history:
            prev_user_turns = [t for t in history if t.role == "user"]
            if prev_user_turns and len(q.split()) < FOLLOW_UP_TOKEN_LIMIT:
                resolved_query = prev_user_turns[-1].text + " " + q

        # --- Retrieval ---
        t0 = time.time()
        ret = retrieve(self._search, resolved_query)
        retrieval_ms = (time.time() - t0) * 1000
        logger.info("Retrieval completed in %.0fms (off_topic=%s)", retrieval_ms, ret["off_topic"])

        # --- Off-topic: return immediately, no LLM call ---
        if ret["off_topic"]:
            logger.info("Outcome: off-topic")
            return AskResult(
                off_topic=True,
                answer=OFF_TOPIC_ANSWER,
                verified=False,
                fallback=True,
                sources=[],
                disclaimer=DISCLAIMER,
                resolved_query=resolved_query,
                cited_source_ids=[],
                routing=[],
                needs_info=[],
            )

        # --- Forum Routing ---
        routing_forums, needs_info = route(resolved_query, ret["results"])
        logger.info(
            "Routing completed (forums=%d, needs_info=%d)",
            len(routing_forums), len(needs_info),
        )

        # --- Generation ---
        t1 = time.time()
        gen = generate_answer(resolved_query, ret)
        gen_ms = (time.time() - t1) * 1000
        logger.info(
            "Generation completed in %.0fms (verified=%s, fallback=%s)",
            gen_ms, gen["verified"], gen["fallback"],
        )

        # Map results to Source objects
        sources = [
            Source(
                id=r["id"],
                heading=r["heading"],
                act=r["act"],
                section=r["section"],
                source_file=r["source_file"],
                text=r["text"],
                formerly_ipc=r["formerly_ipc"],
            )
            for r in ret["results"]
        ]

        return AskResult(
            off_topic=False,
            answer=gen["answer"],
            verified=gen["verified"],
            fallback=gen["fallback"],
            sources=sources,
            disclaimer=DISCLAIMER,
            resolved_query=resolved_query,
            cited_source_ids=gen["citations"],
            routing=routing_forums,
            needs_info=needs_info,
        )


# ---- Module-level singleton ----
_pipeline: LegalPipeline | None = None


def get_pipeline() -> LegalPipeline:
    """Return a cached LegalPipeline instance. Thread-safe enough for FastAPI lifespan."""
    global _pipeline
    if _pipeline is None:
        _pipeline = LegalPipeline()
    return _pipeline
