"""Legal Rights Assistant pipeline — stateless orchestrator.
Loads retrieval once, resolves follow-ups, calls generate, returns structured AskResult.
Never logs query text, answers, or history. Logs only timing and outcome."""
import logging
import re
import time

from schemas import Turn, Source, Forum, RoadmapAction, RoadmapStep, AskResult
from retrieval import load_search, retrieve
from generate import answer as generate_answer
from routing import route
from roadmap import build_roadmap
from lang import (
    detect_language,
    translate_to_english,
    translate_answer,
    verify_translation,
    glossary_keywords,
    OFF_TOPIC,
    DISCLAIMER as LANG_DISCLAIMER,
    UNAVAILABLE,
)

logger = logging.getLogger("pipeline")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [pipeline] %(message)s", datefmt="%H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

DISCLAIMER = LANG_DISCLAIMER["en"]
FOLLOW_UP_TOKEN_LIMIT = 8  # queries shorter than this + prior turn → resolved as follow-up

OFF_TOPIC_ANSWER = OFF_TOPIC["en"]


class LegalPipeline:
    """Stateless pipeline: the caller (API layer) owns sessions and history."""

    def __init__(self):
        logger.info("Loading search engine (one-time heavy step)...")
        t0 = time.time()
        self._search = load_search()
        logger.info("Search engine loaded in %.2fs", time.time() - t0)

    @property
    def search(self):
        """Public access to the underlying search function."""
        return self._search

    def ask(
        self,
        query: str,
        history: list[Turn] | None = None,
        response_lang: str = "auto",
    ) -> AskResult:
        """Answer a user query. Stateless — caller provides history if needed."""
        if response_lang not in ("auto", "en", "hi", "hinglish"):
            raise ValueError(f"Invalid response_lang: {response_lang}")

        # --- Input validation ---
        q = query.strip()
        if not q:
            raise ValueError("Query must not be empty.")
        if len(q) > 1000:
            raise ValueError("Query must not exceed 1000 characters.")

        # --- Language detection ---
        detected_lang = detect_language(q)
        resp_lang = detected_lang if response_lang == "auto" else response_lang
        logger.info("Language detected: %s (target response_lang: %s)", detected_lang, resp_lang)

        # Lookup detection stays on original query text
        is_lookup = bool(
            re.fullmatch(r"(?i)\s*((section|sec|ipc|bns|bnss|s\.?)\s*)?\d{1,3}[a-z]{1,2}\s*", q)
            or re.fullmatch(r"(?i)\s*(section|sec|ipc|bns|bnss|s\.?)\s*\d{1,3}[a-z]{0,2}\s*", q)
        )

        # --- Translate to English if query is not English ---
        if detected_lang != "en":
            trans = translate_to_english(q)
            q_en = trans if trans else ""
            kws = glossary_keywords(q)
            if kws:
                q_en = (q_en + " " + " ".join(kws)).strip()
            if not q_en:
                logger.info("Query translation failed with no glossary keywords; returning unavailable.")
                return AskResult(
                    off_topic=False,
                    answer=UNAVAILABLE[resp_lang],
                    verified=False,
                    fallback=True,
                    sources=[],
                    disclaimer=LANG_DISCLAIMER[resp_lang],
                    resolved_query=q,
                    cited_source_ids=[],
                    routing=[],
                    needs_info=[],
                    roadmap=[],
                    detected_lang=detected_lang,
                    response_lang=resp_lang,
                    answer_en=None,
                    translation_verified=None,
                )
        else:
            q_en = q

        # --- Follow-up resolution ---
        resolved_query = q_en
        if not is_lookup and history:
            prev_user_turns = [t for t in history if t.role == "user"]
            if prev_user_turns and len(q.split()) < FOLLOW_UP_TOKEN_LIMIT:
                prev_text = prev_user_turns[-1].text.strip()
                prev_lang = detect_language(prev_text)
                if prev_lang != "en":
                    prev_trans = translate_to_english(prev_text)
                    prev_en = prev_trans if prev_trans else ""
                    prev_kws = glossary_keywords(prev_text)
                    if prev_kws:
                        prev_en = (prev_en + " " + " ".join(prev_kws)).strip()
                    if not prev_en:
                        prev_en = prev_text
                else:
                    prev_en = prev_text
                resolved_query = prev_en + " " + q_en

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
                answer=OFF_TOPIC[resp_lang],
                verified=False,
                fallback=True,
                sources=[],
                disclaimer=LANG_DISCLAIMER[resp_lang],
                resolved_query=resolved_query,
                cited_source_ids=[],
                routing=[],
                needs_info=[],
                roadmap=[],
                detected_lang=detected_lang,
                response_lang=resp_lang,
                answer_en=None,
                translation_verified=None,
            )

        # --- Forum Routing ---
        routing_forums, needs_info = route(resolved_query, ret["results"])
        logger.info(
            "Routing completed (forums=%d, needs_info=%d)",
            len(routing_forums), len(needs_info),
        )

        # --- Roadmap Construction ---
        roadmap = build_roadmap(resolved_query, ret["results"], routing_forums, needs_info)
        logger.info("Roadmap generated (steps=%d)", len(roadmap))

        # --- Generation ---
        t1 = time.time()
        gen = generate_answer(resolved_query, ret)
        gen_ms = (time.time() - t1) * 1000
        logger.info(
            "Generation completed in %.0fms (verified=%s, fallback=%s)",
            gen_ms, gen["verified"], gen["fallback"],
        )

        # --- Answer Translation & Verification ---
        answer_text = gen["answer"]
        answer_en: str | None = None
        translation_verified: bool | None = None
        actual_resp_lang = "en"

        if gen["verified"] and not gen["fallback"] and resp_lang != "en":
            translated = translate_answer(gen["answer"], resp_lang)
            if translated and verify_translation(gen["answer"], translated, resp_lang):
                answer_text = translated
                answer_en = gen["answer"]
                translation_verified = True
                actual_resp_lang = resp_lang
                logger.info("Answer translated and verified for %s", resp_lang)
            else:
                answer_text = gen["answer"]
                answer_en = None
                translation_verified = False
                actual_resp_lang = "en"
                logger.warning("Answer translation failed or unverified; keeping English.")
        else:
            answer_text = gen["answer"]
            answer_en = None
            translation_verified = None
            actual_resp_lang = "en"

        disclaimer_text = LANG_DISCLAIMER.get(actual_resp_lang, LANG_DISCLAIMER["en"])

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
            answer=answer_text,
            verified=gen["verified"],
            fallback=gen["fallback"],
            sources=sources,
            disclaimer=disclaimer_text,
            resolved_query=resolved_query,
            cited_source_ids=gen["citations"],
            routing=routing_forums,
            needs_info=needs_info,
            roadmap=roadmap,
            detected_lang=detected_lang,
            response_lang=actual_resp_lang,
            answer_en=answer_en,
            translation_verified=translation_verified,
        )


# ---- Module-level singleton ----
_pipeline: LegalPipeline | None = None


def get_pipeline() -> LegalPipeline:
    """Return a cached LegalPipeline instance. Thread-safe enough for FastAPI lifespan."""
    global _pipeline
    if _pipeline is None:
        _pipeline = LegalPipeline()
    return _pipeline
