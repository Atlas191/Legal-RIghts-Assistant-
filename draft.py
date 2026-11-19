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

RECIPIENT_TITLES = {
    "SHO": "The Station House Officer, [Name of Police Station]",
    "ICC": "The Presiding Officer, Internal Complaints Committee, [Name of Workplace]",
    "LCC": "The Chairperson, Local Complaints Committee, [District]",
    "Protection Officer": "The Protection Officer, [District]",
}

SUBJECTS = {
    "SHO": "Complaint and request to register an FIR",
    "ICC": "Complaint regarding sexual harassment at the workplace",
    "LCC": "Complaint regarding sexual harassment at the workplace",
    "Protection Officer": "Application for protection and relief under the Protection of Women from Domestic Violence Act",
}

FIELD_SPECS = [
    ("complainant_name", "Complainant Name", "[Your Name]"),
    ("complainant_address", "Complainant Address", "[Your Address]"),
    ("complainant_phone", "Complainant Phone", "[Your Phone Number]"),
    ("respondent_name", "Respondent Name", "[Name of the Person]"),
    ("respondent_designation", "Respondent Designation", "[Their Designation or Relationship to You]"),
    ("workplace_name", "Workplace Name", "[Name of Workplace]"),  # only for ICC/LCC
    ("incident_date", "Date of Incident", "[Date of Incident]"),
    ("incident_time", "Time of Incident", "[Time of Incident]"),
    ("incident_place", "Place of Incident", "[Place of Incident]"),
    ("witnesses", "Witnesses", "[Names of Witnesses, if any]"),
]

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

DESIGNATION_RE = re.compile(
    r"\b(boss|manager|supervisor|colleague|owner|employer|husband|"
    r"brother-in-law|father-in-law|mother-in-law|landlord|neighbour|neighbor|teacher|stranger)\b",
    re.I,
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
    # Text after " at the ", " in the ", " in my ", " at my " up to a comma, period or " and ",
    # only if it is 1 to 6 words.
    pattern = re.compile(r"\b(?:at|in)\s+(?:the|my)\s+", re.I)
    for m in pattern.finditer(text):
        remainder = text[m.end():]
        delim = re.search(r"[,.\n]|\s+and\s+", remainder, re.I)
        candidate = remainder[:delim.start()] if delim else remainder
        candidate = candidate.strip(" \t\r\n,.;:\"'")
        words = candidate.split()
        if 1 <= len(words) <= 6:
            return candidate
    return None


def extract_designation(text: str) -> str | None:
    m = DESIGNATION_RE.search(text)
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

    # Retrieval (when search is given)
    results = []
    if search is not None:
        try:
            ret_data = retrieve(search, narrative)
            results = ret_data.get("results", [])
        except Exception:
            results = []

    # 5. Determine Recipient
    if req.recipient:
        recipient = req.recipient
    else:
        forums, _ = route(narrative, results)
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

    # 2 & 3. Construct fields
    details = req.details or {}
    fields = []
    fields_by_key = {}

    for key, label, placeholder in FIELD_SPECS:
        if key == "workplace_name" and recipient not in ("ICC", "LCC"):
            continue

        form_val = details.get(key, "").strip() if details.get(key) else ""
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

    # 5. Recipient title
    base_title = RECIPIENT_TITLES.get(recipient, RECIPIENT_TITLES["SHO"])
    if recipient == "ICC":
        wp_val = fields_by_key.get("workplace_name").value if "workplace_name" in fields_by_key else "[Name of Workplace]"
        recipient_title = f"The Presiding Officer, Internal Complaints Committee, {wp_val}"
    else:
        recipient_title = base_title

    # 6. Build fixed template body
    subject = SUBJECTS.get(recipient, "Complaint and request to register an FIR")
    date_line = "[Date of Letter]"
    c_name = fields_by_key.get("complainant_name").value
    c_addr = fields_by_key.get("complainant_address").value
    c_phone = fields_by_key.get("complainant_phone").value
    r_name = fields_by_key.get("respondent_name").value
    r_des = fields_by_key.get("respondent_designation").value
    i_date = fields_by_key.get("incident_date").value
    i_time = fields_by_key.get("incident_time").value
    i_place = fields_by_key.get("incident_place").value
    witnesses = fields_by_key.get("witnesses").value

    details_lines = [
        "Details of the incident:",
        f"- Name of the person: {r_name}",
        f"- Designation or relationship: {r_des}",
    ]
    if recipient in ("ICC", "LCC"):
        wp_val = fields_by_key.get("workplace_name").value
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

    # 7. missing_fields and notes
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

    notes.append("Review every [bracketed] item before you send this letter.")

    # 8. references
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
