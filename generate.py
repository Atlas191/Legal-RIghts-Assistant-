"""LLM generation module using local Ollama.
Answers legal questions using only retrieved sources, with citation verification and fallback."""
import logging
import re
import time
import requests

OLLAMA_MODEL = "llama3"
OLLAMA_URL = "http://localhost:11434/api/chat"

logger = logging.getLogger("generate")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [generate] %(message)s", datefmt="%H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

SYSTEM_PROMPT = (
    "You are a legal assistant helping women understand their rights under Indian law.\n"
    "Rules you must strictly follow:\n"
    "1. Answer ONLY from the provided numbered sources. Do not use outside knowledge or assumptions.\n"
    "2. Use plain, calm, and empathetic language suitable for a non-lawyer.\n"
    "3. Structure your response in short, clear paragraphs.\n"
    "4. Put the source citation [S#] (e.g. [S1], [S2]) immediately after each legal claim or fact stated.\n"
    "5. If the sources do not cover something, explicitly say so.\n"
    "6. Never invent section numbers, deadlines, penalties, or authorities not present in the sources.\n"
    "7. Do not include any legal disclaimer (the application adds it automatically)."
)


def verify_answer(answer_text, n_sources, source_texts):
    """Verify that an answer text cites sources correctly and does not invent section numbers.

    Returns (bool, str): (is_verified, failure_reason)
    """
    if not answer_text or not answer_text.strip():
        return False, "Answer text is empty."

    # a) Fails if there is no [S#] citation at all
    citations = re.findall(r"\[S(\d+)\]", answer_text)
    if not citations:
        return False, "No [S#] citations found in answer."

    # b) Fails if any [S#] has a number outside 1..n_sources
    if n_sources < 1:
        return False, "No sources available for citation."
    for c in citations:
        idx = int(c)
        if idx < 1 or idx > n_sources:
            return False, f"Citation [S{idx}] is outside allowed range 1..{n_sources}."

    # c) Fails if answer mentions 'Section <number><optional letter>' not in sources
    combined_sources = []
    for s in source_texts:
        if isinstance(s, dict):
            combined_sources.append(f"{s.get('heading', '')}\n{s.get('text', '')}")
        elif isinstance(s, str):
            combined_sources.append(s)
        else:
            combined_sources.append(str(s))
    all_sources_text = "\n".join(combined_sources)

    section_mentions = re.findall(r"\bSection\s+\d+[A-Za-z]?\b", answer_text, re.I)
    for sec in section_mentions:
        if not re.search(re.escape(sec) + r"(?![0-9A-Za-z])", all_sources_text, re.I):
            return False, f"Mentioned '{sec}' does not appear in any source."

    return True, ""


def _extract_citations(answer_text, results):
    """Extract list of parent IDs cited in answer_text."""
    c_indices = sorted(list(set(int(x) for x in re.findall(r"\[S(\d+)\]", answer_text))))
    return [results[i - 1]["id"] for i in c_indices if 1 <= i <= len(results)]


def _call_ollama(messages):
    """Call Ollama chat API. Log only timing and outcome, never prompt or response content."""
    t0 = time.time()
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "messages": messages,
                "options": {"temperature": 0},
                "stream": False,
                "keep_alive": "30m",
            },
            timeout=120,
        )
        elapsed = time.time() - t0
        if resp.status_code != 200:
            logger.warning("Ollama HTTP request failed in %.2fs (status %d)", elapsed, resp.status_code)
            return None, elapsed
        data = resp.json()
        content = data.get("message", {}).get("content", "")
        logger.info("Ollama HTTP call completed in %.2fs (status 200)", elapsed)
        return content, elapsed
    except requests.exceptions.RequestException as e:
        elapsed = time.time() - t0
        logger.warning("Ollama request failed in %.2fs (%s)", elapsed, type(e).__name__)
        return None, elapsed


def answer(query, retrieval_result):
    """Generate and verify an answer from retrieval results.

    Returns:
        dict: {"answer": str, "citations": [ids], "verified": bool, "fallback": bool}
    """
    # If retrieval is off-topic or empty, do not call the LLM
    if retrieval_result.get("off_topic") or not retrieval_result.get("results"):
        logger.info("Query flagged as off-topic or empty results; returning out-of-scope fallback.")
        return {
            "answer": "This situation appears to be outside the scope of women's legal rights in India covered by this assistant.",
            "citations": [],
            "verified": False,
            "fallback": True,
        }

    results = retrieval_result["results"]
    n_sources = len(results)

    # Build context as numbered sources: "[S1] <heading> (<act>)\n<text>"
    context_blocks = []
    source_texts = []
    for i, r in enumerate(results, 1):
        block = f"[S{i}] {r['heading']} ({r['act']})\n{r['text']}"
        context_blocks.append(block)
        source_texts.append(block)
    context_str = "\n\n".join(context_blocks)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"User Situation:\n{query}\n\nSources:\n{context_str}\n\nPlease explain the applicable rights and steps using only the sources above.",
        },
    ]

    # First generation attempt
    content, elapsed = _call_ollama(messages)
    if content is None:
        logger.info("Ollama unavailable on attempt 1; returning fallback response.")
        heading_list = "\n".join(f"- {r['heading']} ({r['act']})" for r in results)
        return {
            "answer": (
                "The AI generation service is currently unavailable. "
                "Here are the relevant legal sections retrieved for your situation:\n" + heading_list
            ),
            "citations": [r["id"] for r in results],
            "verified": False,
            "fallback": True,
        }

    ok, reason = verify_answer(content, n_sources, source_texts)
    if ok:
        citations = _extract_citations(content, results)
        logger.info("Generation outcome: verified on attempt 1 (timing: %.2fs)", elapsed)
        return {
            "answer": content,
            "citations": citations,
            "verified": True,
            "fallback": False,
        }

    # Verification failed: regenerate once with reminder
    logger.warning("Verification failed on attempt 1 (%s); attempting regeneration.", reason)
    allowed_ids = ", ".join(f"[S{i}]" for i in range(1, n_sources + 1))
    reminder = (
        f"Your previous response failed verification: {reason}\n"
        f"Allowed source IDs: {allowed_ids}.\n"
        "Reminder: Answer only using facts in the sources, put [S#] after each claim, "
        "use only the allowed IDs, and never invent any Section numbers. Please regenerate."
    )
    messages.append({"role": "assistant", "content": content})
    messages.append({"role": "user", "content": reminder})

    content2, elapsed2 = _call_ollama(messages)
    if content2 is not None:
        ok2, reason2 = verify_answer(content2, n_sources, source_texts)
        if ok2:
            citations = _extract_citations(content2, results)
            logger.info("Generation outcome: verified on attempt 2 (timing: %.2fs)", elapsed2)
            return {
                "answer": content2,
                "citations": citations,
                "verified": True,
                "fallback": False,
            }
        logger.warning("Verification failed on attempt 2 (%s); returning fallback.", reason2)
    else:
        logger.warning("Ollama unavailable on attempt 2; returning fallback.")

    # Second verification failed or Ollama error: return fallback with retrieved headings
    logger.info("Generation outcome: fallback due to verification failure.")
    heading_list = "\n".join(f"- {r['heading']} ({r['act']})" for r in results)
    return {
        "answer": (
            "Unable to verify the generated legal explanation. "
            "Here are the relevant legal sections retrieved for your situation:\n" + heading_list
        ),
        "citations": [r["id"] for r in results],
        "verified": False,
        "fallback": True,
    }
