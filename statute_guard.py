"""Statute-number guard to refuse unindexed IPC/BNS/BNSS/CrPC section lookups.
Builds an exact lookup index lazily from knowledge_base/ chunks. Never logs query text or numbers."""
import logging
import re

from kb_utils import load_chunks

logger = logging.getLogger("statute_guard")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [statute_guard] %(message)s", datefmt="%H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

SYSTEM_LABELS = {
    "ipc": "IPC",
    "bns": "BNS",
    "bnss": "BNSS",
    "crpc": "CrPC",
    "any": "the",
}

NOT_COVERED_TAIL = (
    "in my knowledge base, so I can't answer about it. I cover "
    "selected sections on offences against women and related procedure "
    "(for example IPC 498A, 354, 354A, 354C, 354D, 375, 376, 509, "
    "or BNS 63 to 87, 124, 351, and BNSS 173). "
    "Try one of those, or describe your situation in your own words."
)

_SYS_PATTERN = r"ipc|bnss|bns|cr\.?p\.?c\.?"
_SEC_PATTERN = r"(?:sections?|sec\.?|s\.)"
_REF_REGEX = re.compile(
    rf"(?i)"
    rf"(?P<sys1>\b(?:{_SYS_PATTERN}))(?:\s+(?:{_SEC_PATTERN}\s*)?|(?<=\.)\s*|\s*{_SEC_PATTERN}\s*)(?P<num1>\d{{1,3}}[A-Za-z]{{0,2}})(?![0-9A-Za-z])(?:\s*\([^)]*\))?"
    rf"|"
    rf"(?:{_SEC_PATTERN}\s+)?(?P<num2>\b\d{{1,3}}[A-Za-z]{{0,2}})(?![0-9A-Za-z])(?:\s*\([^)]*\))?\s+(?:of\s+)?(?P<sys2>{_SYS_PATTERN})(?![0-9A-Za-z])"
    rf"|"
    rf"\b{_SEC_PATTERN}\s*(?P<num3>\d{{1,3}}[A-Za-z]{{0,2}})(?![0-9A-Za-z])(?:\s*\([^)]*\))?"
)

_INDEX_CACHE: dict | None = None


def _normalize_system(raw_sys: str) -> str:
    s = raw_sys.lower().replace(".", "")
    if s.startswith("cr"):
        return "crpc"
    return s


def build_index(chunks) -> dict:
    """Build exact-match maps from normalised statute numbers to parent_ids."""
    section_numbers: dict[str, set[str]] = {}
    ipc_numbers: dict[str, set[str]] = {}
    crpc_numbers: dict[str, set[str]] = {}
    parent_docs: dict[str, str] = {}

    seen_parents = set()
    for c in chunks:
        meta = c.metadata
        parent_id = meta.get("parent_id", "")
        doc_id = meta.get("doc_id", "")
        heading = meta.get("heading", "")
        formerly_ipc = meta.get("formerly_ipc", "")
        parent_text = meta.get("parent_text", "")
        page_content = getattr(c, "page_content", "") or ""

        if parent_id:
            parent_docs[parent_id] = doc_id

        # Extract CrPC references from both child chunk text and parent text
        for text_blob in (page_content, parent_text):
            if text_blob:
                for tok in re.findall(r"(?i)cr\.?p\.?c\.?\s*(?:section\s*)?(\d+[A-Za-z]?)", text_blob):
                    crpc_numbers.setdefault(tok.upper(), set()).add(parent_id)

        if parent_id in seen_parents:
            continue
        seen_parents.add(parent_id)

        # section_numbers from headings starting with Section/Sections (not Handbook)
        if re.match(r"^(?:Section|Sections)\b", heading, re.I) and "handbook" not in heading.lower():
            head_prefix = heading.split("—", 1)[0]
            head_clean = re.sub(r"\([^)]*\)", "", head_prefix)
            for rm in re.finditer(r"\b(\d+)\s+to\s+(\d+)\b", head_clean, re.I):
                start_n, end_n = int(rm.group(1)), int(rm.group(2))
                if start_n <= end_n:
                    for n in range(start_n, end_n + 1):
                        section_numbers.setdefault(str(n), set()).add(parent_id)
            for tok in re.findall(r"\d+[A-Za-z]?", head_clean):
                section_numbers.setdefault(tok.upper(), set()).add(parent_id)

        # ipc_numbers from formerly_ipc metadata (comma-separated, ignoring bracketed notes)
        if formerly_ipc:
            fipc_clean = re.sub(r"\([^)]*\)", "", formerly_ipc)
            for piece in fipc_clean.split(","):
                for tok in re.findall(r"\d+[A-Za-z]?", piece):
                    ipc_numbers.setdefault(tok.upper(), set()).add(parent_id)

    return {
        "section_numbers": section_numbers,
        "ipc_numbers": ipc_numbers,
        "crpc_numbers": crpc_numbers,
        "parent_docs": parent_docs,
    }


def _get_index() -> dict:
    global _INDEX_CACHE
    if _INDEX_CACHE is None:
        _INDEX_CACHE = build_index(load_chunks())
    return _INDEX_CACHE


def extract_references(query: str) -> list[tuple[str, str]]:
    """Extract (system, number) statute references from a query."""
    refs: list[tuple[str, str]] = []
    for m in _REF_REGEX.finditer(query):
        if m.group("sys1"):
            sys_name = _normalize_system(m.group("sys1"))
            num = m.group("num1").upper()
        elif m.group("sys2"):
            sys_name = _normalize_system(m.group("sys2"))
            num = m.group("num2").upper()
        else:
            sys_name = "any"
            num = m.group("num3").upper()
        refs.append((sys_name, num))
    return refs


def resolve(refs: list[tuple[str, str]], index: dict) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Resolve references strictly by exact normalised number against index."""
    sec_map = index["section_numbers"]
    ipc_map = index["ipc_numbers"]
    crpc_map = index["crpc_numbers"]
    parent_docs = index["parent_docs"]

    resolved: list[tuple[str, str]] = []
    unresolved: list[tuple[str, str]] = []

    for sys_name, num in refs:
        found = False
        if sys_name == "ipc":
            found = num in ipc_map
        elif sys_name == "bns":
            pids = sec_map.get(num, ())
            found = any(parent_docs.get(pid) == "bns_2023" for pid in pids)
        elif sys_name == "bnss":
            pids = sec_map.get(num, ())
            found = any(parent_docs.get(pid) == "bnss_2023" for pid in pids)
        elif sys_name == "crpc":
            found = num in crpc_map
        else:  # "any"
            found = (num in sec_map) or (num in ipc_map) or (num in crpc_map)

        if found:
            resolved.append((sys_name, num))
        else:
            unresolved.append((sys_name, num))

    return resolved, unresolved


def _format_not_covered(unresolved: list[tuple[str, str]]) -> str:
    deduped: list[tuple[str, str]] = []
    seen = set()
    for item in unresolved:
        if item not in seen:
            seen.add(item)
            deduped.append(item)

    parts = []
    for sys_name, num in deduped:
        label = SYSTEM_LABELS.get(sys_name, "the")
        parts.append(f"{label} section {num}")

    if len(parts) == 1:
        ref_str = parts[0]
        pronoun = "it"
    else:
        ref_str = ", ".join(parts[:-1]) + " and " + parts[-1]
        pronoun = "them"

    return (
        f"I don't have {ref_str} in my knowledge base, so I can't answer about {pronoun}. "
        "I cover selected sections on offences against women and related procedure "
        "(for example IPC 498A, 354, 354A, 354C, 354D, 375, 376, 509, "
        "or BNS 63 to 87, 124, 351, and BNSS 173). "
        "Try one of those, or describe your situation in your own words."
    )


def check(query: str) -> str | None:
    """Return None if query has no statute refs or at least one resolves; else NOT_COVERED message."""
    refs = extract_references(query)
    if not refs:
        return None
    resolved, unresolved = resolve(refs, _get_index())
    if resolved:
        logger.info("statute guard: ok")
        return None
    logger.info("statute guard: unresolved")
    return _format_not_covered(unresolved)
