"""Unit tests for draft.py — complaint and petition drafting.
Run:  python tests/test_draft.py
Exit code 0 = all pass, 1 = at least one failure.
"""
import io
import logging
import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from schemas import DraftRequest, DraftResult, DraftField
from draft import build_draft, FIELD_SPECS


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_1_narrative_with_no_date_name_place():
    """1. narrative with no date, name or place -> date, time, place, respondent_name

    and witnesses are placeholders and all appear in missing_fields; the body
    contains each placeholder in brackets.
    """
    req = DraftRequest(narrative="I was harassed and I need help filing a complaint.")
    result = build_draft(req)

    expected_placeholders = {
        "incident_date": "[Date of Incident]",
        "incident_time": "[Time of Incident]",
        "incident_place": "[Place of Incident]",
        "respondent_name": "[Name of the Person]",
        "witnesses": "[Names of Witnesses, if any]",
    }

    for key, placeholder in expected_placeholders.items():
        assert key in result.missing_fields, f"Expected {key} in missing_fields"
        field = next((f for f in result.fields if f.key == key), None)
        assert field is not None, f"Field {key} missing from fields"
        assert field.is_placeholder, f"Field {key} should be marked is_placeholder"
        assert field.value == placeholder, f"Field {key} value should be {placeholder}, got {field.value}"
        assert placeholder in result.body, f"Placeholder {placeholder} missing from body"

    return True


def test_2_narrative_with_extracted_fields():
    """2. 'On 12 March 2026 at about 6 pm in the office cabin my manager touched me'

    -> date, time, place and designation filled with source user_text; respondent_name still a placeholder.
    """
    narrative = "On 12 March 2026 at about 6 pm in the office cabin my manager touched me"
    req = DraftRequest(narrative=narrative)
    result = build_draft(req)

    field_map = {f.key: f for f in result.fields}

    # Date
    assert field_map["incident_date"].source == "user_text", f"Date source: {field_map['incident_date'].source}"
    assert not field_map["incident_date"].is_placeholder
    assert "12 March 2026" in field_map["incident_date"].value

    # Time
    assert field_map["incident_time"].source == "user_text", f"Time source: {field_map['incident_time'].source}"
    assert not field_map["incident_time"].is_placeholder

    # Place
    assert field_map["incident_place"].source == "user_text", f"Place source: {field_map['incident_place'].source}"
    assert not field_map["incident_place"].is_placeholder

    # Designation
    assert field_map["respondent_designation"].source == "user_text"
    assert not field_map["respondent_designation"].is_placeholder
    assert field_map["respondent_designation"].value.lower() == "manager"

    # Respondent name stays placeholder
    assert field_map["respondent_name"].is_placeholder
    assert field_map["respondent_name"].source == "placeholder"
    assert "respondent_name" in result.missing_fields

    return True


def test_3_mocked_llm_hallucination_rejected():
    """3. mocked llm returns {'respondent_name':'Rajesh Kumar'} while narrative

    never mentions that name -> the field stays a placeholder (hallucination rejected).
    """
    narrative = "On 12 March 2026 at about 6 pm my manager touched me in the office"
    mock_llm = lambda prompt, **kwargs: {"respondent_name": "Rajesh Kumar"}

    req = DraftRequest(narrative=narrative)
    result = build_draft(req, llm=mock_llm)

    field_map = {f.key: f for f in result.fields}
    assert field_map["respondent_name"].is_placeholder, "Hallucinated name should be rejected"
    assert field_map["respondent_name"].value == "[Name of the Person]"
    assert field_map["respondent_name"].source == "placeholder"
    assert "respondent_name" in result.missing_fields

    return True


def test_4_mocked_llm_valid_substring_accepted():
    """4. mocked llm returns a name that does appear in narrative -> accepted, source user_text."""
    narrative = "Rajesh Kumar called me into the office cabin and harassed me"
    mock_llm = lambda prompt, **kwargs: {"respondent_name": "Rajesh Kumar"}

    req = DraftRequest(narrative=narrative)
    result = build_draft(req, llm=mock_llm)

    field_map = {f.key: f for f in result.fields}
    assert not field_map["respondent_name"].is_placeholder
    assert field_map["respondent_name"].value == "Rajesh Kumar"
    assert field_map["respondent_name"].source == "user_text"
    assert "respondent_name" not in result.missing_fields

    return True


def test_5_form_details_override_extracted():
    """5. details provided via the form override extracted values (source user_form)."""
    narrative = "On 12 March 2026 at about 6 pm in the office cabin my manager touched me"
    details = {
        "incident_date": "15 April 2026",
        "incident_place": "Head Office, 4th Floor",
        "respondent_name": "Suresh Sharma",
        "respondent_designation": "Vice President",
    }
    req = DraftRequest(narrative=narrative, details=details)
    result = build_draft(req)

    field_map = {f.key: f for f in result.fields}

    for k, v in details.items():
        assert field_map[k].value == v, f"Field {k} expected {v}, got {field_map[k].value}"
        assert field_map[k].source == "user_form", f"Field {k} should have source 'user_form'"
        assert not field_map[k].is_placeholder
        assert k not in result.missing_fields

    return True


def test_6_narrative_appears_verbatim_once():
    """6. the body contains the narrative exactly once, verbatim."""
    narrative = (
        "My supervisor Mr. Gupta approached me at the desk on Monday morning and made "
        "explicit unwanted remarks regarding my appearance."
    )
    req = DraftRequest(narrative=narrative)
    result = build_draft(req)

    count = result.body.count(narrative)
    assert count == 1, f"Narrative should appear exactly once in body, found {count} times"
    assert "Description of the incident (in my own words):\n" + narrative in result.body

    return True


def test_7_recipient_choice():
    """7. recipient choice: workplace narrative -> ICC or LCC title;

    'police refused' -> SHO; an explicit req.recipient overrides routing.
    """
    # Workplace narrative -> ICC or LCC
    req_work = DraftRequest(narrative="my manager touched me at work")
    res_work = build_draft(req_work)
    assert res_work.recipient in ("ICC", "LCC"), f"Expected ICC or LCC, got {res_work.recipient}"
    assert (
        "Internal Complaints Committee" in res_work.recipient_title
        or "Local Complaints Committee" in res_work.recipient_title
    )

    # Police refused -> SHO
    req_refuse = DraftRequest(narrative="police refused to register my FIR")
    res_refuse = build_draft(req_refuse)
    assert res_refuse.recipient == "SHO", f"Expected SHO, got {res_refuse.recipient}"
    assert "The Station House Officer" in res_refuse.recipient_title

    # Explicit recipient override
    req_override = DraftRequest(narrative="my manager touched me at work", recipient="SHO")
    res_override = build_draft(req_override)
    assert res_override.recipient == "SHO", f"Expected override SHO, got {res_override.recipient}"
    assert "The Station House Officer" in res_override.recipient_title

    # Mock search returning bnss_2023 includes Zero FIR note and references
    mock_search = lambda q: (
        [
            {"meta": {"parent_id": "bnss_2023:0", "parent_text": "Section 173 — Information in cognizable cases\nbody", "heading": "Section 173 — Information in cognizable cases", "act": "BNSS", "section": "173", "formerly_ipc": "", "source_file": "bnss_2023.md"}},
            {"meta": {"parent_id": "bns_2023:1", "parent_text": "Section 78 — Stalking\nbody", "heading": "Section 78 — Stalking", "act": "BNS", "section": "78", "formerly_ipc": "", "source_file": "bns_2023.md"}},
        ],
        {"off_topic": False, "best_dist": 0.5, "max_bm25": 10.0}
    )
    res_search = build_draft(req_refuse, search=mock_search)
    assert any("Zero FIR" in n for n in res_search.notes), f"Expected Zero FIR note in {res_search.notes}"
    assert len(res_search.references) == 2, f"Expected 2 references, got {res_search.references}"
    assert res_search.references[0] == "Section 173 — Information in cognizable cases"

    return True


def test_8_empty_and_oversize_raise_value_error():
    """8. empty narrative and a 4001-character narrative raise ValueError."""
    # Empty string
    try:
        build_draft(DraftRequest(narrative=""))
        assert False, "Empty narrative should raise ValueError"
    except ValueError:
        pass

    # Whitespace only
    try:
        build_draft(DraftRequest(narrative="    \n\t  "))
        assert False, "Whitespace narrative should raise ValueError"
    except ValueError:
        pass

    # 4001 characters
    try:
        build_draft(DraftRequest(narrative="a" * 4001))
        assert False, "4001-character narrative should raise ValueError"
    except ValueError:
        pass

    # 4000 characters should succeed
    res_4000 = build_draft(DraftRequest(narrative="a" * 4000))
    assert res_4000 is not None

    return True


def test_9_logging_privacy():
    """9. logging test: capture logs, assert the narrative text is absent."""
    secret = "CONFIDENTIAL_UNIQUE_TOKEN_987654321_NARRATIVE"
    req = DraftRequest(narrative=f"This contains a {secret} that must never be logged.")

    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    draft_logger = logging.getLogger("draft")
    draft_logger.addHandler(handler)
    draft_logger.setLevel(logging.INFO)

    try:
        build_draft(req)
        logged_text = log_stream.getvalue()
        assert secret not in logged_text, "Confidential narrative found in logs!"
        assert "CONFIDENTIAL" not in logged_text
        assert "Draft generated in" in logged_text
    finally:
        draft_logger.removeHandler(handler)

    return True


def test_10_no_placeholder_is_lost():
    """10. no placeholder is lost: for any case, every key in missing_fields

    appears as its placeholder inside body.
    """
    cases = [
        DraftRequest(narrative="someone harassed me"),
        DraftRequest(
            narrative="my boss touched me at work",
            recipient="ICC",
        ),
        DraftRequest(
            narrative="domestic violence by husband",
            recipient="Protection Officer",
        ),
        DraftRequest(
            narrative="on 12 March 2026 my manager touched me",
            recipient="LCC",
            details={"complainant_name": "Priya Sharma"},
        ),
    ]

    for req in cases:
        res = build_draft(req)
        # Build mapping from key to placeholder
        placeholder_map = {k: ph for k, _, ph in FIELD_SPECS}
        for key in res.missing_fields:
            ph = placeholder_map[key]
            assert ph in res.body, (
                f"Missing field {key} with placeholder {ph!r} not found in body!\n"
                f"Recipient: {res.recipient}\nBody:\n{res.body}"
            )

    return True


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

TESTS = [
    ("1. narrative with no date/name/place -> placeholders in missing_fields & body", test_1_narrative_with_no_date_name_place),
    ("2. narrative with date/time/place/designation -> source user_text", test_2_narrative_with_extracted_fields),
    ("3. mocked llm hallucination rejected -> stays placeholder", test_3_mocked_llm_hallucination_rejected),
    ("4. mocked llm valid substring -> accepted with source user_text", test_4_mocked_llm_valid_substring_accepted),
    ("5. form details override extracted values (source user_form)", test_5_form_details_override_extracted),
    ("6. body contains narrative exactly once, verbatim", test_6_narrative_appears_verbatim_once),
    ("7. recipient choice (workplace -> ICC/LCC, refused -> SHO, explicit override)", test_7_recipient_choice),
    ("8. empty and 4001-character narratives raise ValueError", test_8_empty_and_oversize_raise_value_error),
    ("9. logging test: narrative text is completely absent from logs", test_9_logging_privacy),
    ("10. no placeholder lost: every key in missing_fields appears as placeholder in body", test_10_no_placeholder_is_lost),
]


def run():
    passed = 0
    failed = 0
    print("Running draft tests...")

    for name, fn in TESTS:
        try:
            fn()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}")
            print(f"         Error: {e}")
            failed += 1

    print(f"\n{passed}/{passed + failed} passed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
