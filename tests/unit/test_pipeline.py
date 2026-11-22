"""Unit tests for pipeline.py — no Ollama required (generate is mocked).
Run:  python tests/test_pipeline.py
Exit code 0 = all pass, 1 = at least one failure.
"""
import io
import logging
import os
import sys
from unittest.mock import patch, MagicMock

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from lra.schemas import Turn, AskResult
from lra.pipeline import LegalPipeline, get_pipeline, DISCLAIMER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_search_fn = None


def _get_search():
    """Load the real search engine once across all tests."""
    global _search_fn
    if _search_fn is None:
        from lra.rag.retrieval import load_search
        _search_fn = load_search()
    return _search_fn


def _make_pipeline():
    """Build a LegalPipeline reusing the shared search function."""
    pipe = LegalPipeline.__new__(LegalPipeline)
    pipe._search = _get_search()
    return pipe


MOCK_GEN_RETURN = {
    "answer": "You are protected under Section 85 [S1]. This covers cruelty by a husband or in-laws.",
    "citations": ["sec-bns-85"],
    "verified": True,
    "fallback": False,
}


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------
def test_on_topic_returns_sources_and_disclaimer():
    """On-topic query returns sources, cited IDs, routing, and a disclaimer."""
    pipe = _make_pipeline()
    with patch("lra.pipeline.generate_answer", return_value=MOCK_GEN_RETURN):
        result = pipe.ask("my husband beats me")
    assert isinstance(result, AskResult)
    assert not result.off_topic
    assert len(result.sources) > 0
    assert result.sources[0].text != ""
    assert hasattr(result.sources[0], "formerly_ipc")
    assert result.cited_source_ids == ["sec-bns-85"]
    assert len(result.routing) > 0
    assert len(result.roadmap) > 0
    assert isinstance(result.needs_info, list)
    assert result.disclaimer == DISCLAIMER
    return True


def test_off_topic_no_ollama():
    """Off-topic query returns off_topic=True with no Ollama call, empty routing."""
    pipe = _make_pipeline()
    mock_gen = MagicMock()
    with patch("lra.pipeline.generate_answer", mock_gen):
        result = pipe.ask("capital of india")
    assert result.off_topic is True
    assert result.sources == []
    assert result.cited_source_ids == []
    assert result.routing == []
    assert result.needs_info == []
    assert result.roadmap == []
    mock_gen.assert_not_called()
    return True


def test_follow_up_resolution():
    """Short follow-up with > LOOKUP_MAX_TOKENS tokens gets resolved_query = prev user query + current."""
    pipe = _make_pipeline()
    history = [
        Turn(role="user", text="my husband beats me"),
        Turn(role="assistant", text="Here are relevant sections..."),
    ]
    with patch("lra.pipeline.generate_answer", return_value=MOCK_GEN_RETURN):
        result = pipe.ask("can they demand dowry money", history=history)
    assert result.resolved_query == "my husband beats me can they demand dowry money"
    return True


def test_lookup_query_skips_follow_up():
    """Lookup query with statute reference skips follow-up join."""
    pipe = _make_pipeline()
    history = [
        Turn(role="user", text="my husband beats me"),
        Turn(role="assistant", text="Here are relevant sections..."),
    ]
    with patch("lra.pipeline.generate_answer", return_value=MOCK_GEN_RETURN):
        result = pipe.ask("498A", history=history)
    assert result.resolved_query == "498A"
    return True


def test_follow_up_joins_and_reroutes_workplace():
    """f) history = [user 'my boss keeps touching me at work', assistant '...']; query 'we are 40 people' -> resolved_query contains both, routing has ICC and not LCC, needs_info == []"""
    pipe = _make_pipeline()
    history = [
        Turn(role="user", text="my boss keeps touching me at work"),
        Turn(role="assistant", text="Here are the relevant provisions..."),
    ]
    with patch("lra.pipeline.generate_answer", return_value=MOCK_GEN_RETURN):
        result = pipe.ask("we are 40 people", history=history)

    assert "my boss keeps touching me at work" in result.resolved_query
    assert "we are 40 people" in result.resolved_query
    routing_names = [f.name for f in result.routing]
    assert any("Internal Complaints Committee (ICC)" in n for n in routing_names), f"ICC missing from {routing_names}"
    assert not any("Local Complaints Committee (LCC)" in n for n in routing_names), f"LCC should not be in {routing_names}"
    assert result.needs_info == [], f"Expected empty needs_info, got {result.needs_info}"
    return True


def test_statute_lookups_skip_join():
    """g) with the same history, '498A', '66E' and 'section 85' each keep resolved_query equal to the query itself."""
    pipe = _make_pipeline()
    history = [
        Turn(role="user", text="my boss keeps touching me at work"),
        Turn(role="assistant", text="Here are the relevant provisions..."),
    ]
    with patch("lra.pipeline.generate_answer", return_value=MOCK_GEN_RETURN):
        for query in ["498A", "66E", "section 85"]:
            result = pipe.ask(query, history=history)
            assert result.resolved_query == query, (
                f"Expected resolved_query to be {query!r}, got {result.resolved_query!r}"
            )
            assert not result.off_topic, (
                f"Expected {query!r} to not be off_topic, got {result.off_topic}"
            )
    return True


def test_empty_query_raises():
    """Empty query raises ValueError."""
    pipe = _make_pipeline()
    try:
        pipe.ask("")
        return False  # should have raised
    except ValueError:
        return True


def test_oversize_query_raises():
    """Query over 1000 characters raises ValueError."""
    pipe = _make_pipeline()
    try:
        pipe.ask("a" * 1001)
        return False
    except ValueError:
        return True


def test_logs_do_not_contain_query_text():
    """Pipeline logs never contain the actual query text."""
    pipe = _make_pipeline()
    test_query = "my husband beats me and threw me out"

    # Capture log output
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setLevel(logging.DEBUG)
    logger = logging.getLogger("pipeline")
    logger.addHandler(handler)

    with patch("lra.pipeline.generate_answer", return_value=MOCK_GEN_RETURN):
        pipe.ask(test_query)

    logger.removeHandler(handler)
    log_output = buf.getvalue()
    assert test_query not in log_output, "Query text leaked into logs!"
    return True


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
TESTS = [
    ("on-topic returns sources and disclaimer", test_on_topic_returns_sources_and_disclaimer),
    ("off-topic returns off_topic=True with no Ollama call", test_off_topic_no_ollama),
    ("short follow-up resolves query correctly", test_follow_up_resolution),
    ("lookup query skips follow-up join", test_lookup_query_skips_follow_up),
    ("f) follow-up joins and reroutes workplace", test_follow_up_joins_and_reroutes_workplace),
    ("g) statute lookups skip join", test_statute_lookups_skip_join),
    ("empty query raises ValueError", test_empty_query_raises),
    ("oversize query raises ValueError", test_oversize_query_raises),
    ("logs do not contain query text", test_logs_do_not_contain_query_text),
]


def run():
    print("Loading search engine for pipeline tests...")
    _get_search()  # pre-load once

    passed = 0
    failed = 0

    for name, fn in TESTS:
        try:
            ok = fn()
            if ok:
                passed += 1
                print(f"  [PASS] {name}")
            else:
                failed += 1
                print(f"  [FAIL] {name}")
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {name} — {type(e).__name__}: {e}")

    print(f"\n{passed}/{passed + failed} passed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
