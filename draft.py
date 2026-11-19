"""Complaint and petition drafting module.
Generates structured legal drafts for SHO, ICC, LCC, and Protection Officers.
Pure deterministic offline extraction with optional LLM assistance.
Privacy rule: do not log narrative, extracted values or letter body; log only timing and counts.
"""
import json
import logging
import re
import time
from typing import Callable

from schemas import DraftRequest, DraftField, DraftResult
from routing import route, ICC_TIME_LIMIT, LCC_TIME_LIMIT
from retrieval import retrieve
from pipeline import DISCLAIMER

logger = logging.getLogger("draft")

# ---------------------------------------------------------------------------
# Constants and Specifications
# ---------------------------------------------------------------------------

SUBJECTS = {
    "SHO": "Complaint and request to register an FIR",
    "ICC": "Complaint regarding sexual harassment at the workplace",
    "LCC": "Complaint regarding sexual harassment at the workplace",
    "Protection Officer": "Application for protection and relief under the Protection of Women from Domestic Violence Act",
}

FIELD_SPECS = [
    ("letter_date", "Date of Letter", "[Date of Letter]"),
    ("police_station", "Police Station", "[Name of Police Station]"),  # SHO only
    ("district", "District", "[District]"),  # LCC and Protection Officer only
    ("complainant_name", "Complainant Name", "[Your Name]"),
    ("complainant_address", "Complainant Address", "[Your Address]"),
    ("complainant_phone", "Complainant Phone", "[Your Phone Number]"),
    ("respondent_name", "Respondent Name", "[Name of the Person]"),
    ("respondent_designation", "Respondent Designation", "[Their Designation or Relationship to You]"),
    ("workplace_name", "Workplace Name", "[Name of Workplace]"),  # ICC/LCC only
    ("incident_date", "Date of Incident", "[Date of Incident]"),
    ("incident_time", "Time of Incident", "[Time of Incident]"),
    ("incident_place", "Place of Incident", "[Place of Incident]"),
    ("witnesses", "Witnesses", "[Names of Witnesses, if any]"),
]

ALLOWED_DETAIL_KEYS = {k for k, _, _ in FIELD_SPECS}

MONTH_NAMES = (
    "january|february|march|april|may|june|july|august|september|october|november|december"
)

DATE_REGEXES = [
    # dd/mm/yyyy or dd-mm-yyyy (e.g. 12/03/2026, 12-03-2026)
    re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{4}\b"),
    # 12 March 2026, 12th March 2026, 12 March, 2026
    re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTH_NAMES})\s*,?\s*\d{{4}}\b", re.I),
    # March 12, 2026 or March 12 2026
    re.compile(rf"\b(?:{MONTH_NAMES})\s+\d{{1,2}}(?:st|nd|rd|th)?\s*,?\s*\d{{4}}\b", re.I),
    # 12 March, 12th March, 12th of March
    re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:{MONTH_NAMES})\b", re.I),
    # March 12, March 12th
    re.compile(rf"\b(?:{MONTH_NAMES})\s+\d{{1,2}}(?:st|nd|rd|th)?\b", re.I),
    # yesterday, today, last night (kept verbatim, never converted into a calendar date)
    re.compile(r"\b(yesterday|today|last\s+night)\b", re.I),
]

TIME_REGEXES = [
    # "at about 6", "at about 6 pm", "at around 6:30 pm"
    re.compile(r"\b(?:at\s+(?:about|around))\s+\d{1,2}(?::\d{2})?(?:\s*(?:am|pm|a\.m\.|p\.m\.))?\b", re.I),
    # "6:30 PM", "6 pm", "6am"
    re.compile(r"\b\d{1,2}(?::\d{2})\s*(?:am|pm|a\.m\.|p\.m\.)\b", re.I),
    re.compile(r"\b\d{1,2}\s*(?:am|pm|a\.m\.|p\.m\.)\b", re.I),
    # "in the evening", "in the morning", "in the afternoon", "at night"
    re.compile(r"\b(?:in\s+the\s+(?:morning|afternoon|evening)|at\s+night)\b", re.I),
    # "morning", "evening", "night"
    re.compile(r"\b(morning|evening|night)\b", re.I),
]

PLACE_STOP_WORDS = {
    "my", "me", "i", "he", "she", "they", "we", "when", "while", "where", "who",
    "and", "but", "on", "at", "during", "after", "before", "then", "because", "so",
    "was", "were", "is", "started", "tried", "asked", "said", "called", "came",
    "made", "touched", "grabbed", "hit", "beat", "kept",
}

SKIP_FIRST_WORDS = {
    "morning", "afternoon", "evening", "night", "time", "end", "beginning", "middle", "day"
}

DESIGNATION_RE = re.compile(
    r"\b(boss|manager|supervisor|colleague|owner|employer|husband|"
    r"brother-in-law|father-in-law|mother-in-law|landlord|neighbour|neighbor|teacher|stranger)\b",
    re.I,
)

HONORIFIC_NAME_RE = re.compile(
    r"\b(?:Mr|Mrs|Ms|Miss|Dr|Shri|Smt)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?"
)


# ---------------------------------------------------------------------------
# Offline Extractors
# ---------------------------------------------------------------------------

def extract_date(text: str) -> str | None:
    for reg in DATE_REGEXES:
        m = reg.search(text)
        if m:
            return m.group(0).strip()
    return None


def extract_time(text: str) -> str | None:
    for reg in TIME_REGEXES:
        m = reg.search(text)
        if m:
            return m.group(0).strip()
    return None


def extract_place(text: str) -> str | None:
    """Extract place after ' at the | in the | at my | in my '.

    Takes words one by one, stopping at the first punctuation (, . ; \n) or
    stop word. Capped at 4 words. Returns None if no word remains.
    Skips a match if its first collected word is a temporal or transitional word
    (morning, afternoon, evening, night, time, end, beginning, middle, day).
    """
    pattern = re.compile(r"\b(?:at|in)\s+(?:the|my)\s+", re.I)
    for m in pattern.finditer(text):
        remainder = text[m.end():]
        collected = []
        for tok in re.finditer(r"([^\s,.;\n]+)|([,.;\n])", remainder):
            if tok.group(2):
                break
            word = tok.group(1).strip(" \"'()")
            if not word:
                continue
            if word.lower() in PLACE_STOP_WORDS:
                break
            collected.append(word)
            if len(collected) == 4:
                break
        if collected:
            if collected[0].lower() in SKIP_FIRST_WORDS:
                continue
            return " ".join(collected)
    return None


def extract_designation(text: str) -> str | None:
    m = DESIGNATION_RE.search(text)
    if m:
        return m.group(0).strip()
    return None


def extract_respondent_name(text: str) -> str | None:
    m = HONORIFIC_NAME_RE.search(text)
    if m:
        return m.group(0).strip()
    return None


def extract_via_llm(narrative: str, llm_callable: Callable) -> dict[str, str]:
    """Ask LLM for fields and keep ONLY values that are substrings of the narrative."""
    prompt = (
        "Extract the following fields from the incident narrative as JSON.\n"
        "Keys: complainant_name, complainant_address, complainant_phone, "
        "respondent_name, respondent_designation, workplace_name, "
        "incident_date, incident_time, incident_place, witnesses.\n"
        "Only extract values that are explicitly mentioned in the text. "
        "Do not invent or assume any names or facts.\n"
        f"Narrative:\n{narrative}\n"
        "JSON:"
    )
    try:
        try:
            res = llm_callable(prompt, temperature=0)
        except TypeError:
            res = llm_callable(prompt)
        if isinstance(res, str):
            text = res.strip()
            if text.startswith("```"):
                text = re.sub(r"^```[a-z]*\n?", "", text)
                text = re.sub(r"\n?```$", "", text)
            data = json.loads(text)
        elif isinstance(res, dict):
            data = res
        else:
            data = {}
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}

    norm_narrative = " ".join(narrative.lower().split())
    valid_extracted = {}
    for k, v in data.items():
        if isinstance(v, str) and v.strip():
            norm_val = " ".join(v.lower().split())
            if norm_val and norm_val in norm_narrative:
                valid_extracted[k] = v.strip()
    return valid_extracted


# ---------------------------------------------------------------------------
# Main Builder
# ---------------------------------------------------------------------------

def build_draft(req: DraftRequest, search=None, llm=None) -> DraftResult:
    """Build a formal legal draft letter based on user narrative and optional form details."""
    t0 = time.perf_counter()

    # 1. Validate narrative
    narrative = req.narrative.strip() if req.narrative else ""
    if not (1 <= len(narrative) <= 4000):
        raise ValueError(
            f"Narrative must be between 1 and 4000 characters (got {len(narrative)})."
        )

    # 5. Validate and sanitize details
    sanitized_details: dict[str, str] = {}
    if req.details:
        for k, v in req.details.items():
            if k not in ALLOWED_DETAIL_KEYS:
                continue
            collapsed = " ".join(str(v).split()).strip()
            if len(collapsed) > 200:
                raise ValueError(
                    f"Detail value for '{k}' exceeds 200 characters (got {len(collapsed)})."
                )
            sanitized_details[k] = collapsed

    # Retrieval (when search is given)
    results = []
    if search is not None:
        try:
            ret_data = retrieve(search, narrative)
            results = ret_data.get("results", [])
        except Exception:
            results = []

    # Recipient determination
    chosen_by_routing = False
    has_both_icc_and_lcc = False

    if req.recipient:
        recipient = req.recipient
    else:
        chosen_by_routing = True
        forums, _ = route(narrative, results)
        names = [f.name for f in forums]
        has_icc = any(n.startswith("Internal Complaints Committee") for n in names)
        has_lcc = any(n.startswith("Local Complaints Committee") for n in names)
        has_both_icc_and_lcc = has_icc and has_lcc

        recipient = None
        for f in forums:
            if f.name.startswith("Internal Complaints Committee"):
                recipient = "ICC"
                break
            elif f.name.startswith("Local Complaints Committee"):
                recipient = "LCC"
                break
            elif f.name.startswith("Protection Officer"):
                recipient = "Protection Officer"
                break
            elif f.name.startswith("Police station"):
                recipient = "SHO"
                break
        if not recipient:
            recipient = "SHO"

    # Extract offline
    extracted_offline = {}
    d = extract_date(narrative)
    if d:
        extracted_offline["incident_date"] = d
    t = extract_time(narrative)
    if t:
        extracted_offline["incident_time"] = t
    p = extract_place(narrative)
    if p:
        extracted_offline["incident_place"] = p
    des = extract_designation(narrative)
    if des:
        extracted_offline["respondent_designation"] = des

    # LLM extraction (optional, never overrides offline/form)
    extracted_llm = {}
    if llm is not None:
        extracted_llm = extract_via_llm(narrative, llm)

    # Honorific regex for respondent_name (if not filled from details or LLM)
    if not sanitized_details.get("respondent_name") and not extracted_llm.get("respondent_name"):
        r_name_match = extract_respondent_name(narrative)
        if r_name_match:
            extracted_offline["respondent_name"] = r_name_match

    # Construct fields
    fields = []
    fields_by_key = {}

    for key, label, placeholder in FIELD_SPECS:
        if key == "police_station" and recipient != "SHO":
            continue
        if key == "district" and recipient not in ("LCC", "Protection Officer"):
            continue
        if key == "workplace_name" and recipient not in ("ICC", "LCC"):
            continue

        form_val = sanitized_details.get(key, "").strip() if sanitized_details.get(key) else ""
        if form_val:
            field = DraftField(
                key=key,
                label=label,
                value=form_val,
                is_placeholder=False,
                source="user_form",
            )
        elif key in extracted_offline and extracted_offline[key]:
            field = DraftField(
                key=key,
                label=label,
                value=extracted_offline[key],
                is_placeholder=False,
                source="user_text",
            )
        elif key in extracted_llm and extracted_llm[key]:
            field = DraftField(
                key=key,
                label=label,
                value=extracted_llm[key],
                is_placeholder=False,
                source="user_text",
            )
        else:
            field = DraftField(
                key=key,
                label=label,
                value=placeholder,
                is_placeholder=True,
                source="placeholder",
            )

        fields.append(field)
        fields_by_key[key] = field

    # Recipient title
    if recipient == "SHO":
        ps_val = fields_by_key["police_station"].value
        recipient_title = f"The Station House Officer, {ps_val}"
    elif recipient == "ICC":
        wp_val = fields_by_key["workplace_name"].value
        recipient_title = f"The Presiding Officer, Internal Complaints Committee, {wp_val}"
    elif recipient == "LCC":
        dist_val = fields_by_key["district"].value
        recipient_title = f"The Chairperson, Local Complaints Committee, {dist_val}"
    elif recipient == "Protection Officer":
        dist_val = fields_by_key["district"].value
        recipient_title = f"The Protection Officer, {dist_val}"
    else:
        recipient_title = "The Station House Officer, [Name of Police Station]"

    # Build fixed template body
    subject = SUBJECTS.get(recipient, "Complaint and request to register an FIR")
    date_line = fields_by_key["letter_date"].value
    c_name = fields_by_key["complainant_name"].value
    c_addr = fields_by_key["complainant_address"].value
    c_phone = fields_by_key["complainant_phone"].value
    r_name = fields_by_key["respondent_name"].value
    r_des = fields_by_key["respondent_designation"].value
    i_date = fields_by_key["incident_date"].value
    i_time = fields_by_key["incident_time"].value
    i_place = fields_by_key["incident_place"].value
    witnesses = fields_by_key["witnesses"].value

    details_lines = [
        "Details of the incident:",
        f"- Name of the person: {r_name}",
        f"- Designation or relationship: {r_des}",
    ]
    if recipient in ("ICC", "LCC"):
        wp_val = fields_by_key["workplace_name"].value
        details_lines.append(f"- Workplace: {wp_val}")

    details_lines.extend([
        f"- Date: {i_date}",
        f"- Time: {i_time}",
        f"- Place: {i_place}",
        f"- Witnesses: {witnesses}",
    ])
    details_block = "\n".join(details_lines)

    closing = (
        "I request you to take appropriate action as per law.\n\n"
        "Yours faithfully,\n"
        f"{c_name}\n"
        f"Address: {c_addr}\n"
        f"Phone: {c_phone}"
    )

    body = (
        f"{date_line}\n\n"
        f"{recipient_title}\n\n"
        f"Subject: {subject}\n\n"
        f"Respected Sir/Madam,\n\n"
        f"I, {c_name}, am submitting this formal complaint regarding an incident that occurred against me.\n\n"
        f"{details_block}\n\n"
        f"Description of the incident (in my own words):\n"
        f"{narrative}\n\n"
        f"{closing}"
    )

    # missing_fields and notes
    missing_fields = [f.key for f in fields if f.is_placeholder]
    notes = []
    if recipient in ("ICC", "LCC"):
        notes.append(ICC_TIME_LIMIT if recipient == "ICC" else LCC_TIME_LIMIT)
    elif recipient == "SHO":
        doc_ids = {
            r["id"].split(":")[0]
            for r in results
            if isinstance(r, dict) and "id" in r
        }
        if "bnss_2023" in doc_ids:
            notes.append("You can register a Zero FIR at any police station")

    if chosen_by_routing and has_both_icc_and_lcc:
        notes.append(
            "If your workplace has fewer than 10 employees, or the complaint is against the "
            "employer, address this letter to the Local Complaints Committee instead."
        )

    notes.append("Review every [bracketed] item before you send this letter.")

    # references
    references = []
    if search is not None and results:
        references = [r["heading"] for r in results[:3] if isinstance(r, dict) and "heading" in r]

    # Privacy logging: timing and counts only
    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    logger.info(
        "Draft generated in %dms (recipient=%s, fields=%d, missing=%d, notes=%d, references=%d)",
        elapsed_ms,
        recipient,
        len(fields),
        len(missing_fields),
        len(notes),
        len(references),
    )

    return DraftResult(
        recipient=recipient,
        recipient_title=recipient_title,
        subject=subject,
        fields=fields,
        body=body,
        missing_fields=missing_fields,
        notes=notes,
        references=references,
        disclaimer=DISCLAIMER,
    )
