"""Language detection, translation, and glossary mapping module for Hindi and Hinglish support.
Privacy rule: never log query text, translations or answers (counts and timings only).
"""
from collections import Counter
import difflib
import functools
import logging
import os
import re
import time
from typing import Callable

from generate import _call_ollama, OLLAMA_MODEL

logger = logging.getLogger("lang")

TRANSLATE_MODEL = os.environ.get("TRANSLATE_MODEL", OLLAMA_MODEL)

# ---------------------------------------------------------------------------
# Roman-Hindi marker set for language detection
# Never include English words such as "me", "so", "do", "to", "is", "in", "it"
# ---------------------------------------------------------------------------
HINGLISH_MARKERS = {
    "mera", "meri", "mere", "mujhe", "mujhse", "mujhko", "hum", "humein",
    "pati", "patni", "biwi", "shauhar", "saas", "sasur", "sasural", "dahej",
    "maarta", "marta", "maarte", "peeta", "peetta", "pitai", "maarpeet",
    "nikal", "nikala", "nikaal", "nikale", "nikala", "ghar", "kaam", "naukri", "malik",
    "chhuta", "chhoota", "chhua", "chhoo", "pareshan", "peecha", "peechha",
    "dhamki", "nahi", "nahin", "hai", "hain", "hoon", "kya", "kyun", "kaise",
    "aur", "bhi", "kar", "karta", "karti", "karte", "karein", "karna", "raha",
    "rahi", "rahe", "diya", "di", "liya", "mana", "bina", "ijazat", "vakeel",
    "paise", "pas", "paas", "wajah", "se", "ko", "ka", "ki", "ke", "mein",
    "par", "wale", "wali", "tha", "thi", "baat", "unhe", "unko", "aapse",
    "shikayat", "hinsa", "utpeedan", "kripya", "tarah", "galat", "kisi", "baar",
}

# ---------------------------------------------------------------------------
# Seed glossary of terms mapping to English keywords
# ---------------------------------------------------------------------------
GLOSSARY = {
    # Husband / Wife / In-laws
    "pati": ["husband"],
    "shauhar": ["husband"],
    "पति": ["husband"],
    "patni": ["wife"],
    "biwi": ["wife"],
    "पत्नी": ["wife"],
    "saas": ["mother-in-law"],
    "सास": ["mother-in-law"],
    "sasur": ["father-in-law"],
    "ससुर": ["father-in-law"],
    "sasural": ["in-laws"],
    "ससुराल": ["in-laws"],
    # Dowry
    "dahej": ["dowry"],
    "दहेज": ["dowry"],
    # Physical violence / beating
    "maarta": ["beats", "violence"],
    "marta": ["beats", "violence"],
    "maarte": ["beats", "violence"],
    "peeta": ["beats", "violence"],
    "peetta": ["beats", "violence"],
    "pitai": ["beats", "violence"],
    "maarpeet": ["beats", "violence"],
    "मारता": ["beats", "violence"],
    "मारते": ["beats", "violence"],
    "पीटता": ["beats", "violence"],
    "पिटाई": ["beats", "violence"],
    "मारपीट": ["beats", "violence"],
    # Eviction from home
    "ghar se nikal": ["thrown out of house"],
    "ghar se nikaal": ["thrown out of house"],
    "घर से निकाल": ["thrown out of house"],
    # Domestic violence
    "gharelu hinsa": ["domestic violence"],
    "घरेलू हिंसा": ["domestic violence"],
    # Boss / Employer / Job
    "boss": ["boss", "employer"],
    "malik": ["boss", "employer"],
    "बॉस": ["boss", "employer"],
    "मालिक": ["boss", "employer"],
    "naukri": ["job"],
    "नौकरी": ["job"],
    # Inappropriate touching / harassment
    "chhuta": ["touches", "harassment"],
    "chhoota": ["touches", "harassment"],
    "chhua": ["touches", "harassment"],
    "chhoo": ["touches", "harassment"],
    "छूता": ["touches", "harassment"],
    "छेड़": ["touches", "harassment"],
    "छेड़छाड़": ["touches", "harassment"],
    "pareshan": ["harass"],
    "परेशान": ["harass"],
    # Stalking
    "peecha": ["stalking", "following"],
    "peechha": ["stalking", "following"],
    "पीछा": ["stalking", "following"],
    # Threats
    "dhamki": ["threat"],
    "धमकी": ["threat"],
    # Photos / Voyeurism
    "photo": ["photos"],
    "photos": ["photos"],
    "tasveer": ["photos"],
    "फोटो": ["photos"],
    "तस्वीर": ["photos"],
    "bina ijazat": ["without consent"],
    "bina meri ijazat": ["without consent"],
    "bina kisi ijazat": ["without consent"],
    "bina permission": ["without consent"],
    "bina meri permission": ["without consent"],
    "bina anumati": ["without consent"],
    "बिना अनुमति": ["without consent"],
    "बिना मेरी अनुमति": ["without consent"],
    # Police / FIR
    "police": ["police"],
    "पुलिस": ["police"],
    "thana": ["police station"],
    "थाना": ["police station"],
    "fir": ["FIR"],
    "एफआईआर": ["FIR"],
    "mana kar": ["refused"],
    "मना कर": ["refused"],
    # Legal aid / Lawyer
    "vakeel": ["lawyer"],
    "वकील": ["lawyer"],
    "paise nahi": ["cannot afford lawyer"],
    "पैसे नहीं": ["cannot afford lawyer"],
    "muft": ["free legal aid"],
    "मुफ्त": ["free legal aid"],
    # Pregnancy & Maternity
    "pregnancy": ["pregnant"],
    "pregnant": ["pregnant"],
    "garbh": ["pregnant"],
    "गर्भ": ["pregnant"],
    "maternity": ["maternity leave"],
    "मातृत्व": ["maternity leave"],
    "chhutti": ["leave"],
    "छुट्टी": ["leave"],
    # Sexual Harassment & Workplace
    "yaun utpeedan": ["sexual harassment"],
    "यौन उत्पीड़न": ["sexual harassment"],
    "karyasthal": ["workplace"],
    "कार्यस्थल": ["workplace"],
}

# ---------------------------------------------------------------------------
# Fixed Verbatim Strings
# ---------------------------------------------------------------------------
OFF_TOPIC = {
    "en": (
        "I'm a legal assistant for women's rights in India, so I can't help with that question. "
        "Try describing a situation about harassment at work, domestic violence, stalking, "
        "online abuse, dowry harassment, maternity rights, police procedure, or free legal aid."
    ),
    "hi": "यह सहायक भारत में महिलाओं के कानूनी अधिकारों से जुड़े प्रश्नों के लिए है, इसलिए इस प्रश्न में सहायता उपलब्ध नहीं है। आप कार्यस्थल पर उत्पीड़न, घरेलू हिंसा, पीछा करने, ऑनलाइन दुर्व्यवहार, दहेज उत्पीड़न, मातृत्व अधिकार, पुलिस प्रक्रिया या निःशुल्क कानूनी सहायता से जुड़ी अपनी स्थिति बता सकते हैं।",
    "hinglish": "Yeh assistant sirf Bharat mein mahilaon ke kanooni adhikaron se jude sawaalon ke liye hai, isliye is sawaal mein madad nahi ho sakti. Aap kaam par utpeedan, gharelu hinsa, peecha karna, online durvyavhar, dahej utpeedan, maternity adhikar, police prakriya ya muft kanooni sahayata ke baare mein apni sthiti bata sakte hain.",
}

DISCLAIMER = {
    "en": "General legal information only, not legal advice. In an emergency call 112.",
    "hi": "यह केवल सामान्य कानूनी जानकारी है, कानूनी सलाह नहीं। आपात स्थिति में 112 पर कॉल करें।",
    "hinglish": "Yeh sirf aam kanooni jaankari hai, kanooni salah nahi. Emergency mein 112 par call karein.",
}

UNAVAILABLE = {
    "en": "I could not process this language right now. Please try again in English.",
    "hi": "इस समय इस भाषा को समझने में दिक्कत हो रही है। कृपया अंग्रेज़ी में दोबारा लिखें।",
    "hinglish": "Is waqt is bhasha ko samajhne mein dikkat ho rahi hai. Kripya English mein dobara likhein.",
}


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def detect_language(text: str) -> str:
    """Detect language of input text: 'hi', 'hinglish', or 'en'.

    - 'hi' if Devanagari characters are >= 30% of the letters.
    - Else 'hinglish' if lowercase tokens contain at least 2 distinct words from Roman-Hindi marker set
      OR marker words are >= 30% of the tokens.
    - Else 'en'.
    """
    if not text or not text.strip():
        return "en"

    devanagari_chars = len(re.findall(r"[\u0900-\u097F]", text))
    letters = len(re.findall(r"[A-Za-z\u0900-\u097F]", text))

    if letters > 0 and (devanagari_chars / letters) >= 0.30:
        return "hi"

    tokens = [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w.isalpha()]
    if not tokens:
        return "en"

    distinct_markers = set(tokens) & HINGLISH_MARKERS
    marker_count = sum(1 for t in tokens if t in HINGLISH_MARKERS)

    if len(distinct_markers) >= 2 or (marker_count / len(tokens)) >= 0.30:
        return "hinglish"

    return "en"


def glossary_keywords(text: str) -> list[str]:
    """Extract unique English keywords matched in text via glossary mappings.

    Roman terms are matched on word boundaries; Devanagari terms via substring.
    Applies special eviction/termination rules for 'nikal'.
    """
    found: list[str] = []
    t_clean = text.strip()

    # Standard glossary term matching
    for term, kws in GLOSSARY.items():
        is_devanagari = bool(re.search(r"[\u0900-\u097F]", term))
        matched = False
        if is_devanagari:
            if term in t_clean:
                matched = True
        else:
            if re.search(rf"\b{re.escape(term)}\b", t_clean, re.I):
                matched = True

        if matched:
            found.extend(kws)

    # Special rule:
    # "nikal diya" or "nikala" with "ghar" -> thrown out of house;
    # without "ghar" and with naukri/job/kaam -> fired terminated from job.
    has_nikal = bool(
        re.search(r"\b(nikal\s+diya|nikala|nikaala|nikal|nikale)\b", t_clean, re.I)
        or re.search(r"(निकाल दिया|निकाला|निकाल)", t_clean)
    )
    if has_nikal:
        has_ghar = bool(
            re.search(r"\b(ghar|makaan|sasural)\b", t_clean, re.I)
            or re.search(r"(घर|ससुराल|मकान)", t_clean)
        )
        has_job = bool(
            re.search(r"\b(naukri|job|kaam|office)\b", t_clean, re.I)
            or re.search(r"(नौकरी|काम|जॉब)", t_clean)
        )
        if has_ghar:
            found.append("thrown out of house")
        elif has_job:
            found.extend(["fired", "terminated from job"])

    # Deduplicate while preserving order
    return list(dict.fromkeys(found))


def _strip_preamble(text: str) -> str:
    """Drop LLM conversational preamble and trailing notes.

    If the first line (case-insensitive) starts with 'here is', 'here's', 'translation',
    'english translation', 'sure', 'note:' or ends with ':' and there is more text after it,
    drop that first line; also drop a trailing line starting with 'note:' or '(note'.
    """
    if not text or not text.strip():
        return text

    lines = text.strip().splitlines()
    if not lines:
        return text

    first_line_clean = lines[0].strip().lower()
    prefixes = ("here is", "here's", "translation", "english translation", "sure", "note:")
    if (first_line_clean.startswith(prefixes) or first_line_clean.endswith(":")) and len(lines) > 1:
        if any(line.strip() for line in lines[1:]):
            lines = lines[1:]
            while lines and not lines[0].strip():
                lines.pop(0)

    while lines and lines[-1].strip().lower().startswith(("note:", "(note")):
        lines.pop()
        while lines and not lines[-1].strip():
            lines.pop()

    return "\n".join(lines).strip()


def translate_to_english(text: str, llm=None) -> str | None:
    """Translate a Hindi/Hinglish query into English.

    Accepts the result only if non-empty, contains no Devanagari, and is <= 3x original len + 50.
    """
    prompt = (
        "Translate to English. Keep names, numbers and abbreviations. "
        f"Do not add information or advice. Output only the translation.\n\n{text}"
    )
    messages = [{"role": "user", "content": prompt}]
    t0 = time.time()

    try:
        if llm is not None:
            try:
                raw = llm(prompt)
            except TypeError:
                raw = llm(messages)
            if isinstance(raw, tuple):
                raw = raw[0]
        else:
            raw, _ = _call_ollama(messages, model=TRANSLATE_MODEL)

        elapsed = time.time() - t0
        logger.info("translate_to_english call completed in %.2fs", elapsed)
    except Exception as e:
        logger.warning("translate_to_english failed in %.2fs (%s)", time.time() - t0, type(e).__name__)
        return None

    if not raw or not isinstance(raw, str):
        return None

    out = _strip_preamble(raw)
    out = out.strip('"\'')
    if not out:
        return None

    # Must contain no Devanagari
    if re.search(r"[\u0900-\u097F]", out):
        return None

    # Length constraint
    max_len = 3 * len(text) + 50
    if len(out) > max_len:
        return None

    return out


@functools.lru_cache(maxsize=128)
def translate_previous_turn(text: str) -> str | None:
    """Bounded in-memory cache for translating previous turn text in follow-up queries.

    Never logged or written to disk.
    """
    return translate_to_english(text)


translate_turn_to_english = translate_previous_turn
cached_translate_to_english = translate_previous_turn


def translate_answer(text_en: str, target: str, llm=None) -> str | None:
    """Translate an English verified legal answer into Hindi (Devanagari) or Hinglish."""
    if target == "hi":
        script_instruction = "Translate into Hindi in Devanagari script."
    elif target == "hinglish":
        script_instruction = "Translate into Hindi written in Roman letters (Hinglish)."
    else:
        return text_en

    prompt = (
        f"{script_instruction} "
        "Keep every [S1]-style marker exactly as is. Keep all numbers and section numbers. "
        "Keep law and authority names (ICC, LCC, POSH, PWDVA, BNS, BNSS, IT Act, NALSA, NCW, FIR, Zero FIR) in Latin script. "
        f"Add nothing, omit nothing. Output only the translation.\n\n{text_en}"
    )
    messages = [{"role": "user", "content": prompt}]
    t0 = time.time()

    try:
        if llm is not None:
            try:
                raw = llm(prompt)
            except TypeError:
                raw = llm(messages)
            if isinstance(raw, tuple):
                raw = raw[0]
        else:
            raw, _ = _call_ollama(messages, model=TRANSLATE_MODEL)

        elapsed = time.time() - t0
        logger.info("translate_answer call completed in %.2fs", elapsed)
    except Exception as e:
        logger.warning("translate_answer failed in %.2fs (%s)", time.time() - t0, type(e).__name__)
        return None

    if not raw or not isinstance(raw, str):
        return None

    out = _strip_preamble(raw)
    out = out.strip('"\'')
    return out if out else None


def answer_translation_enabled() -> bool:
    """Check if answer translation is opted in via environment variable ANSWER_TRANSLATION.

    Reads os.environ at call time so runtime updates take effect immediately.
    """
    return os.environ.get("ANSWER_TRANSLATION", "off").lower() in ("on", "1", "true")


def verify_translation(src_en: str, out: str, target: str) -> bool:
    """Verify translated answer preserves citations, numbers, and script integrity.

    - out is non-empty.
    - fails when output (lowercased, whitespace collapsed) equals src_en or SequenceMatcher ratio >= 0.9.
    - [S#] markers match exactly (same multiset).
    - every ASCII digit sequence in src_en appears in out.
    - no invented numbers: every ASCII digit sequence in out appears in src_en.
    - for 'hi' at least 30% of the letters are Devanagari.
    - for 'hinglish': no Devanagari, at least 10% HINGLISH_MARKERS tokens, and >= 5 distinct markers.
    """
    if not out or not out.strip():
        return False

    # Prevent echoed English
    src_en_normalised = " ".join(src_en.lower().split())
    out_normalised = " ".join(out.lower().split())
    if out_normalised == src_en_normalised:
        return False
    if difflib.SequenceMatcher(None, src_en_normalised, out_normalised).ratio() >= 0.9:
        return False

    # 1. Exact match of [S#] markers (multiset)
    src_markers = re.findall(r"\[S\d+\]", src_en)
    out_markers = re.findall(r"\[S\d+\]", out)
    if Counter(src_markers) != Counter(out_markers):
        return False

    # 2. Every ASCII digit sequence in src_en appears in out
    src_digits = re.findall(r"\d+", src_en)
    out_digits = re.findall(r"\d+", out)
    for d in src_digits:
        if d not in out:
            return False

    # No invented numbers: every ASCII digit sequence in out must appear in src_en
    src_digit_set = set(src_digits)
    for d in out_digits:
        if d not in src_digit_set:
            return False

    # 3. Script validation
    if target == "hi":
        letters = re.findall(r"[A-Za-z\u0900-\u097F]", out)
        if not letters:
            return False
        devanagari_count = len(re.findall(r"[\u0900-\u097F]", out))
        if (devanagari_count / len(letters)) < 0.30:
            return False
    elif target == "hinglish":
        if re.search(r"[\u0900-\u097F]", out):
            return False
        tokens = [w for w in re.findall(r"[a-zA-Z]+", out.lower())]
        if not tokens:
            return False
        distinct_markers = set(tokens) & HINGLISH_MARKERS
        marker_count = sum(1 for t in tokens if t in HINGLISH_MARKERS)
        if len(distinct_markers) < 5 or (marker_count / len(tokens)) < 0.10:
            return False

    return True
