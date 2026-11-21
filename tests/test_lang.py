"""Unit tests for lang.py and pipeline multilingual support — no Ollama required.
Run:  ./venv/bin/python tests/test_lang.py
Exit code 0 = all pass, 1 = at least one failure.
"""
import io
import logging
import os
import sys
from unittest.mock import patch, MagicMock

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from schemas import Turn
from lang import (
    detect_language,
    glossary_keywords,
    verify_translation,
    _strip_preamble,
    translate_answer,
    translate_previous_turn,
    OFF_TOPIC,
    DISCLAIMER,
    UNAVAILABLE,
)
from pipeline import LegalPipeline
from tests.run_golden import CASES

_search_fn = None


def _get_search():
    global _search_fn
    if _search_fn is None:
        from retrieval import load_search
        _search_fn = load_search()
    return _search_fn


def _make_pipeline():
    pipe = LegalPipeline.__new__(LegalPipeline)
    pipe._search = _get_search()
    return pipe


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_detect_language_devanagari():
    """Devanagari query detected as 'hi'."""
    assert detect_language("मेरे पति मुझे मारते हैं और घर से निकाल दिया") == "hi"
    assert detect_language("मेरा बॉस मुझे काम पर गलत तरीके से छूता है") == "hi"
    print("PASS: test_detect_language_devanagari")


def test_detect_language_hinglish():
    """Roman-Hindi marker query detected as 'hinglish'."""
    assert detect_language("mera pati mujhe maarta hai aur ghar se nikal diya") == "hinglish"
    assert detect_language("office mein mera boss mujhe galat tarah se chhuta hai") == "hinglish"
    print("PASS: test_detect_language_hinglish")


def test_detect_language_golden_en():
    """Every English golden query is detected as 'en'."""
    assert len(CASES) > 0
    for item in CASES:
        q = item[0]
        detected = detect_language(q)
        assert detected == "en", f"Query {q!r} was detected as {detected!r}, expected 'en'"
    print(f"PASS: test_detect_language_golden_en ({len(CASES)} cases)")


def test_glossary_keywords():
    """glossary_keywords extracts expected terms including husband, beats, thrown out of house."""
    hi_q = "मेरे पति मुझे मारते हैं और घर से निकाल दिया"
    kws_hi = glossary_keywords(hi_q)
    assert "husband" in kws_hi, f"'husband' not in {kws_hi}"
    assert "beats" in kws_hi, f"'beats' not in {kws_hi}"
    assert "thrown out of house" in kws_hi, f"'thrown out of house' not in {kws_hi}"

    hing_q = "mera pati mujhe maarta hai aur ghar se nikal diya"
    kws_hing = glossary_keywords(hing_q)
    assert "husband" in kws_hing, f"'husband' not in {kws_hing}"
    assert "beats" in kws_hing, f"'beats' not in {kws_hing}"
    assert "thrown out of house" in kws_hing, f"'thrown out of house' not in {kws_hing}"
    print("PASS: test_glossary_keywords")


def test_verify_translation():
    """verify_translation enforces [S#] markers, digit sequences, and script rules."""
    src_en = "Under Section 3 [S1], you have protection orders for 3 months [S2]."

    # Good Hindi
    good_hi = "धारा 3 [S1] के तहत, आपके पास 3 महीने [S2] के लिए संरक्षण आदेश हैं।"
    assert verify_translation(src_en, good_hi, "hi") is True

    # Dropped [S1]
    dropped_s1 = "धारा 3 के तहत, आपके पास 3 महीने [S2] के लिए संरक्षण आदेश हैं।"
    assert verify_translation(src_en, dropped_s1, "hi") is False

    # Dropped "3"
    dropped_3 = "धारा [S1] के तहत, आपके पास महीने [S2] के लिए संरक्षण आदेश हैं।"
    assert verify_translation(src_en, dropped_3, "hi") is False

    # "hi" output with no Devanagari
    no_dev = "Under Section 3 [S1], you have protection orders for 3 months [S2]."
    assert verify_translation(src_en, no_dev, "hi") is False

    # "hinglish" output containing Devanagari
    hinglish_with_dev = "Dhara 3 [S1] ke tehat 3 महीने [S2] ke liye orders hain."
    assert verify_translation(src_en, hinglish_with_dev, "hinglish") is False

    # Good Hinglish
    good_hinglish = "Section 3 [S1] ke tehat aapko 3 months [S2] tak protection mil sakti hai."
    assert verify_translation(src_en, good_hinglish, "hinglish") is True

    # Output containing "90" when source has no 90 fails verify_translation
    invented_90 = "धारा 3 [S1] के तहत, आपके पास 90 महीने [S2] के लिए संरक्षण आदेश हैं।"
    assert verify_translation(src_en, invented_90, "hi") is False
    print("PASS: test_verify_translation")


def test_strip_preamble_and_verified():
    """A translation starting with 'Here is the translation:' is cleaned and still verified."""
    src_en = "Under Section 3 [S1], you have protection orders for 3 months [S2]."
    raw_hi = (
        "Here is the translation:\n"
        "धारा 3 [S1] के तहत, आपके पास 3 महीने [S2] के लिए संरक्षण आदेश हैं।\n"
        "Note: consult a legal professional."
    )
    cleaned = _strip_preamble(raw_hi)
    assert not cleaned.lower().startswith("here is"), "Preamble was not dropped"
    assert "note:" not in cleaned.lower(), "Trailing note was not dropped"
    assert verify_translation(src_en, cleaned, "hi") is True

    # Test that translate_answer strips preamble before returning
    mock_llm = MagicMock(return_value=raw_hi)
    trans = translate_answer(src_en, "hi", llm=mock_llm)
    assert trans is not None
    assert not trans.lower().startswith("here is")
    assert verify_translation(src_en, trans, "hi") is True
    print("PASS: test_strip_preamble_and_verified")


def test_follow_up_translator_cache():
    """A follow-up asks the previous-turn translator once for two identical previous turns."""
    pipe = _make_pipeline()
    translate_previous_turn.cache_clear()

    prev_turn = Turn(role="user", text="मेरे पति मुझे मारते हैं")
    mock_prev_trans = MagicMock(return_value="my husband beats me")

    mock_gen = MagicMock(return_value={
        "answer": "You can seek protection orders under Section 3 [S1].",
        "citations": ["pwdva_2005:sec-3"],
        "verified": True,
        "fallback": False,
    })

    with patch("lang.translate_to_english", mock_prev_trans), \
         patch("pipeline.generate_answer", mock_gen):
        # Query 1: follow-up under 8 words in English
        pipe.ask("what to do", history=[prev_turn])
        # Query 2: identical previous turn
        pipe.ask("where to go", history=[prev_turn])

    assert mock_prev_trans.call_count == 1, (
        f"Expected translator to be called once for identical previous turn, got {mock_prev_trans.call_count}"
    )
    print("PASS: test_follow_up_translator_cache")


def test_pipeline_hindi_query():
    """Pipeline with mocked translator/generator on Hindi DV query."""
    pipe = _make_pipeline()
    mock_trans_en = "my husband beats me and threw me out of the house"
    mock_gen_return = {
        "answer": "Under Section 3 [S1], domestic violence includes physical abuse.",
        "citations": ["pwdva_2005:sec-3"],
        "verified": True,
        "fallback": False,
    }
    mock_trans_hi = "धारा 3 [S1] के तहत घरेलू हिंसा में शारीरिक शोषण शामिल है।"

    with patch("pipeline.translate_to_english", return_value=mock_trans_en), \
         patch("pipeline.generate_answer", return_value=mock_gen_return), \
         patch("pipeline.translate_answer", return_value=mock_trans_hi):
        result = pipe.ask("मेरे पति मुझे मारते हैं और घर से निकाल दिया")

    assert result.off_topic is False
    assert result.detected_lang == "hi"
    assert result.response_lang == "hi"
    assert any("pwdva" in s.id or "pwdva" in s.source_file for s in result.sources), "pwdva section expected"
    assert result.answer == mock_trans_hi
    assert result.answer_en == mock_gen_return["answer"]
    assert result.translation_verified is True
    assert result.disclaimer == DISCLAIMER["hi"]
    print("PASS: test_pipeline_hindi_query")


def test_pipeline_translation_drops_s1():
    """Pipeline when translated answer drops [S1] keeps English answer and sets translation_verified=False."""
    pipe = _make_pipeline()
    mock_trans_en = "my husband beats me"
    mock_gen_return = {
        "answer": "Under Section 3 [S1], you can seek protection.",
        "citations": ["pwdva_2005:sec-3"],
        "verified": True,
        "fallback": False,
    }
    mock_trans_hi_bad = "धारा 3 के तहत आप सुरक्षा मांग सकती हैं।"  # Missing [S1]

    with patch("pipeline.translate_to_english", return_value=mock_trans_en), \
         patch("pipeline.generate_answer", return_value=mock_gen_return), \
         patch("pipeline.translate_answer", return_value=mock_trans_hi_bad):
        result = pipe.ask("मेरे पति मुझे मारते हैं")

    assert result.off_topic is False
    assert result.answer == mock_gen_return["answer"]
    assert result.answer_en is None
    assert result.translation_verified is False
    assert result.response_lang == "en"
    assert result.disclaimer == DISCLAIMER["en"]
    print("PASS: test_pipeline_translation_drops_s1")


def test_pipeline_hindi_off_topic():
    """Pipeline on Hindi off-topic query returns off_topic=True and Hindi OFF_TOPIC string."""
    pipe = _make_pipeline()
    mock_trans_en = "how do I get a passport"

    with patch("pipeline.translate_to_english", return_value=mock_trans_en):
        result = pipe.ask("पासपोर्ट कैसे बनवाएं")

    assert result.off_topic is True
    assert result.answer == OFF_TOPIC["hi"]
    assert result.disclaimer == DISCLAIMER["hi"]
    assert result.sources == []
    print("PASS: test_pipeline_hindi_off_topic")


def test_pipeline_translator_fails_no_glossary():
    """Pipeline when translator fails and no glossary hits returns UNAVAILABLE message."""
    pipe = _make_pipeline()

    # Query with Devanagari letters that do not match any glossary words
    devanagari_random = "कखग चछज"
    with patch("pipeline.translate_to_english", return_value=None):
        result = pipe.ask(devanagari_random)

    assert result.off_topic is False
    assert result.fallback is True
    assert result.sources == []
    assert result.answer == UNAVAILABLE["hi"]
    assert result.disclaimer == DISCLAIMER["hi"]
    print("PASS: test_pipeline_translator_fails_no_glossary")


def test_privacy_logging_never_contains_query_or_answer():
    """Pipeline and lang loggers never log query text, translations, or answers."""
    pipe = _make_pipeline()
    secret_query = "गुप्त प्रश्न 123456"
    secret_translation = "secret translated query 987654"
    secret_answer = "secret legal answer 555555 [S1]"
    secret_answer_hi = "गुप्त कानूनी उत्तर 555555 [S1]"

    log_stream = io.StringIO()
    handler = logging.StreamHandler(log_stream)
    p_logger = logging.getLogger("pipeline")
    l_logger = logging.getLogger("lang")
    p_logger.addHandler(handler)
    l_logger.addHandler(handler)

    mock_gen_return = {
        "answer": secret_answer,
        "citations": ["pwdva_2005:sec-3"],
        "verified": True,
        "fallback": False,
    }

    try:
        with patch("pipeline.translate_to_english", return_value=secret_translation), \
             patch("pipeline.generate_answer", return_value=mock_gen_return), \
             patch("pipeline.translate_answer", return_value=secret_answer_hi):
            pipe.ask(secret_query)
    finally:
        p_logger.removeHandler(handler)
        l_logger.removeHandler(handler)

    logged = log_stream.getvalue()
    assert secret_query not in logged, "Secret query was logged!"
    assert secret_translation not in logged, "Secret translation was logged!"
    assert secret_answer not in logged, "Secret answer was logged!"
    assert secret_answer_hi not in logged, "Secret translated answer was logged!"
    print("PASS: test_privacy_logging_never_contains_query_or_answer")


TESTS = [
    test_detect_language_devanagari,
    test_detect_language_hinglish,
    test_detect_language_golden_en,
    test_glossary_keywords,
    test_verify_translation,
    test_strip_preamble_and_verified,
    test_follow_up_translator_cache,
    test_pipeline_hindi_query,
    test_pipeline_translation_drops_s1,
    test_pipeline_hindi_off_topic,
    test_pipeline_translator_fails_no_glossary,
    test_privacy_logging_never_contains_query_or_answer,
]


def main():
    failed = 0
    for t in TESTS:
        try:
            t()
        except Exception as e:
            print(f"FAIL: {t.__name__} - {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    if failed:
        print(f"\n{failed} / {len(TESTS)} tests failed.")
        sys.exit(1)
    else:
        print(f"\nAll {len(TESTS)} test cases passed.")


if __name__ == "__main__":
    main()
