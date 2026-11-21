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
    "7. Do not include any legal disclaimer (the application adds it automatically).\n"
    "8. Say exactly who is directed to do what. If a source says the court can direct the respondent to do something, say the court can direct him; never turn an order against the respondent into something the woman must do.\n"
    "9. Use 'can' or 'may' for what a court or authority is able to do. Never promise an outcome: do not write that the woman 'will be protected', 'will be provided' or that 'the court will' do something.\n"
    "10. Do not give advice that is not in the sources (for example 'consult a lawyer' or 'contact a helpline'); next steps are added separately by the application.\n"
    "11. Attribute each provision only to the source that contains it. Do not say a section defines or provides something unless that source says so.\n"
    "12. Sources marked ILLUSTRATIVE EXAMPLE describe other women. Never say or imply that their facts (people, places, objects, jobs) happened to the user. Use them only to explain how the law treats similar conduct.\n"
    "13. Do not tell the user to report to her supervisor, boss, HR, management or a lawyer, and do not write numbered steps. If a source names a committee or authority, you may name it.\n"
    "14. If a source does not clearly apply to the user's situation, do not mention it."
)


ADVICE_PHRASES = [
    "consult a lawyer",
    "contact a lawyer",
    "seek legal advice",
    "reach out to",
    "hr department",
    "human resources",
    "report to your supervisor",
    "report the incidents to your supervisor",
    "helpline",
]


def build_context(results):
    """Build context string as numbered sources.

    For any result whose heading contains 'Scenario', write its block as:
    "[S#] (ILLUSTRATIVE EXAMPLE about a different woman, not the user's facts) <heading> (<act>)\n<text>".
    Numbering is unchanged; other blocks are unchanged.
    """
    context_blocks = []
    for i, r in enumerate(results, 1):
        heading = r.get("heading", "")
        act = r.get("act", "")
        text = r.get("text", "")
        if "Scenario" in heading:
            block = f"[S{i}] (ILLUSTRATIVE EXAMPLE about a different woman, not the user's facts) {heading} ({act})\n{text}"
        else:
            block = f"[S{i}] {heading} ({act})\n{text}"
        context_blocks.append(block)
    return "\n\n".join(context_blocks)


def verify_answer(answer_text, n_sources, source_texts, query=""):
    """Verify that an answer text cites sources correctly and does not invent section numbers or advice.

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

    # Combine sources and extract individual headings/texts
    combined_sources = []
    source_items = []
    for s in source_texts:
        if isinstance(s, dict):
            heading = s.get("heading", "")
            text = s.get("text", "")
            combined_sources.append(f"{heading}\n{text}")
            source_items.append((heading, text, s))
        elif isinstance(s, str):
            combined_sources.append(s)
            lines = s.split("\n", 1)
            heading = lines[0]
            text = lines[1] if len(lines) > 1 else ""
            source_items.append((heading, text, s))
        else:
            s_str = str(s)
            combined_sources.append(s_str)
            lines = s_str.split("\n", 1)
            heading = lines[0]
            text = lines[1] if len(lines) > 1 else ""
            source_items.append((heading, text, s_str))
    all_sources_text = "\n".join(combined_sources)
    all_sources_lower = all_sources_text.lower()
    answer_lower = answer_text.lower()

    # c) Fails if answer mentions 'Section <number><optional letter>' not in sources
    section_mentions = re.findall(r"\bSection\s+\d+[A-Za-z]?\b", answer_text, re.I)
    for sec in section_mentions:
        if not re.search(re.escape(sec) + r"(?![0-9A-Za-z])", all_sources_text, re.I):
            return False, f"Mentioned '{sec}' does not appear in any source."

    # 1. Advice phrases: if lowercase answer contains advice phrase not in any source text
    for phrase in ADVICE_PHRASES:
        if phrase in answer_lower and phrase not in all_sources_lower:
            return False, f"Contains advice not in the sources: '{phrase}'."

    # 2. Definition attribution: for each match of
    #    r"(?:defined?|defines|definition)\s+(?:in|under|by)\s+(?:the\s+)?Section\s+(\d+[A-Za-z]?)"
    #    find source whose heading contains that "Section <n>" (word boundary); if heading does not
    #    contain "defin" -> fail
    def_matches = re.finditer(
        r"(?i)(?:defined?|defines|definition)\s+(?:in|under|by)\s+(?:the\s+)?Section\s+(\d+[A-Za-z]?)",
        answer_text,
    )
    for m in def_matches:
        sec_n = m.group(1)
        found_heading = None
        for heading, _, _ in source_items:
            if re.search(r"\bSection\s+" + re.escape(sec_n) + r"\b", heading, re.I):
                found_heading = heading
                break
        if not found_heading or "defin" not in found_heading.lower():
            return False, f"Section {sec_n} does not define anything in the sources."

    # 3. Scenario leakage: for each source marked ILLUSTRATIVE EXAMPLE, take its lowercase words of
    #    6 or more letters that appear in no non-scenario source and not in query; if answer contains any
    #    -> fail "Answer uses details from an illustrative example."
    scenario_sources = []
    non_scenario_texts = []
    for heading, text, raw in source_items:
        raw_str = raw if isinstance(raw, str) else f"{heading}\n{text}"
        if "ILLUSTRATIVE EXAMPLE" in raw_str or "Scenario" in heading:
            scenario_sources.append((heading, text, raw_str))
        else:
            non_scenario_texts.append(f"{heading}\n{text}")

    if scenario_sources:
        non_scenario_combined = "\n".join(non_scenario_texts).lower()
        non_scenario_words = set(re.findall(r"\b[a-z]{6,}\b", non_scenario_combined))
        query_words = set(re.findall(r"\b[a-z]{6,}\b", query.lower())) if query else set()

        for heading, text, raw_str in scenario_sources:
            clean_sc = re.sub(r"(?i)\(ILLUSTRATIVE EXAMPLE[^)]*\)", "", raw_str)
            sc_words = set(re.findall(r"\b[a-z]{6,}\b", clean_sc.lower()))
            sc_words.discard("scenario")
            leak_candidates = {w for w in sc_words if w not in non_scenario_words and w not in query_words}
            answer_words = set(re.findall(r"\b[a-z]{6,}\b", answer_lower))
            if leak_candidates & answer_words:
                return False, "Answer uses details from an illustrative example."

    return True, ""


def _extract_citations(answer_text, results):
    """Extract list of parent IDs cited in answer_text."""
    c_indices = sorted(list(set(int(x) for x in re.findall(r"\[S(\d+)\]", answer_text))))
    return [results[i - 1]["id"] for i in c_indices if 1 <= i <= len(results)]


def _call_ollama(messages, model=None):
    """Call Ollama chat API. Log only timing and outcome, never prompt or response content."""
    t0 = time.time()
    use_model = model or OLLAMA_MODEL
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={
                "model": use_model,
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

    # Build context as numbered sources using build_context
    context_str = build_context(results)
    source_texts = []
    for i, r in enumerate(results, 1):
        heading = r.get("heading", "")
        act = r.get("act", "")
        text = r.get("text", "")
        if "Scenario" in heading:
            block = f"[S{i}] (ILLUSTRATIVE EXAMPLE about a different woman, not the user's facts) {heading} ({act})\n{text}"
        else:
            block = f"[S{i}] {heading} ({act})\n{text}"
        source_texts.append(block)

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

    ok, reason = verify_answer(content, n_sources, source_texts, query=query)
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
        ok2, reason2 = verify_answer(content2, n_sources, source_texts, query=query)
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
