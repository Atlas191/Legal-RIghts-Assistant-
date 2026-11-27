"""Unit tests for statute_guard.py and pipeline statute guard short-circuit (no Ollama, no embedding model)."""
import logging
import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from kb_utils import load_chunks
from pipeline import DISCLAIMER, LegalPipeline
import statute_guard

GUARD_CASES = [
    ("ipc sec 311", True),
    ("ipc 311", True),
    ("section 311", True),
    ("bns 311", True),
    ("ipc 302", True),
    ("ipc 498A", False),
    ("ipc sec 498a", False),
    ("ipc 354", False),
    ("ipc 354D", False),
    ("ipc 506", False),
    ("ipc 375", False),
    ("ipc 326A", False),
    ("bns 351", False),
    ("bns 63", False),
    ("bnss 173", False),
    ("crpc 154", False),
    ("section 85", False),
    ("498A", False),
    ("what is section 498A", False),
    ("section 12(c)", False),
    ("we are 40 people", False),
    ("I have 3 months", False),
    ("ipc 311 and ipc 498A", False),
    ("ipc 311 and ipc 302", True),
]


def test_exact_matching_no_prefix():
    """Prefix matching must not happen: '354' resolves to 354 only, and '35' does not resolve."""
    index = statute_guard.build_index(load_chunks())
    res_354, unres_354 = statute_guard.resolve([("ipc", "354")], index)
    assert res_354 == [("ipc", "354")] and unres_354 == []
    res_35, unres_35 = statute_guard.resolve([("ipc", "35")], index)
    assert res_35 == [] and unres_35 == [("ipc", "35")]
    print("  [PASS] exact matching rejects partial prefix matches")


def test_message_content_and_multiple():
    """Verify NOT_COVERED message wording for single and multiple unresolved sections."""
    msg_311 = statute_guard.check("ipc sec 311")
    assert msg_311 is not None
    # Note: NOT_COVERED's example parenthetical includes '351' verbatim per spec 1e,
    # so verify the refusal sentence does not cite 351 and 'Section 351' is absent.
    first_sentence = msg_311.split(".", 1)[0]
    assert "IPC" in first_sentence and "311" in first_sentence, f"Unexpected refusal: {first_sentence}"
    assert "351" not in first_sentence and "Section 351" not in msg_311, f"Unexpected 351 claim: {msg_311}"

    msg_both = statute_guard.check("ipc 311 and ipc 302")
    assert msg_both is not None
    assert "311" in msg_both and "302" in msg_both, f"Expected both 311 and 302 in: {msg_both}"
    print("  [PASS] NOT_COVERED messages format single and multiple refs cleanly without leaking 351")


def test_privacy_logging():
    """statute_guard logger must never log query text or statute numbers."""
    records = []

    class CaptureHandler(logging.Handler):
        def emit(self, record):
            records.append(record.getMessage())

    sg_logger = logging.getLogger("statute_guard")
    h = CaptureHandler()
    sg_logger.addHandler(h)
    try:
        statute_guard.check("ipc sec 311")
        statute_guard.check("ipc 498A")
    finally:
        sg_logger.removeHandler(h)

    assert len(records) == 2
    assert records == ["statute guard: unresolved", "statute guard: ok"], f"Unexpected logs: {records}"
    for rec in records:
        assert "311" not in rec and "498" not in rec and "ipc" not in rec.lower()
    print("  [PASS] statute_guard logs only 'statute guard: unresolved' / 'statute guard: ok'")


class _SentinelCalledError(RuntimeError):
    pass


def test_pipeline_short_circuit():
    """LegalPipeline.ask() skips retrieval on unresolved refs and calls retrieval on resolved refs."""
    pipe = LegalPipeline.__new__(LegalPipeline)

    def _stub_search(*args, **kwargs):
        raise _SentinelCalledError("retrieval was called")

    pipe._search = _stub_search

    # 1) "ipc sec 311" -> off_topic=True with NOT_COVERED message, retrieval never called
    res = pipe.ask("ipc sec 311")
    assert res.off_topic is True
    assert res.verified is False
    assert res.fallback is True
    assert res.sources == []
    assert res.routing == []
    assert res.roadmap == []
    assert res.disclaimer == DISCLAIMER
    assert res.resolved_query == "ipc sec 311"
    assert "IPC" in res.answer and "311" in res.answer

    # 2) "ipc 498A" -> passes guard and reaches retrieval
    called = False
    try:
        pipe.ask("ipc 498A")
    except _SentinelCalledError:
        called = True
    assert called is True, "Expected 'ipc 498A' to reach retrieval"
    print("  [PASS] LegalPipeline short-circuits 'ipc sec 311' before retrieval and passes 'ipc 498A'")


def run():
    passed = 0
    failed = 0

    for query, expect_msg in GUARD_CASES:
        msg = statute_guard.check(query)
        got_msg = msg is not None
        ok = got_msg == expect_msg
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"  [{status}] {query!r} -> {'message' if got_msg else 'None'} (expected={'message' if expect_msg else 'None'})")

    extra_tests = [
        test_exact_matching_no_prefix,
        test_message_content_and_multiple,
        test_privacy_logging,
        test_pipeline_short_circuit,
    ]
    for fn in extra_tests:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {fn.__name__} failed: {e}")
            failed += 1

    print(f"\n{passed}/{passed + failed} passed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
