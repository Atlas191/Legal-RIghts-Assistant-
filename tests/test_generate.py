"""Unit tests for verify_answer and build_context in generate.py (no Ollama required)."""
import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from generate import build_context, verify_answer

TEST_CASES = [
    (
        "valid cited answer passes",
        "You have the right to a safe workplace free from sexual harassment [S1].",
        2,
        ["Handbook 1.3 — Legal basis and the Act", "Section 75 — Sexual harassment"],
        True,
    ),
    (
        "no citations fails",
        "You have the right to a safe workplace free from sexual harassment.",
        2,
        ["Handbook 1.3 — Legal basis and the Act", "Section 75 — Sexual harassment"],
        False,
    ),
    (
        "[S9] with 3 sources fails",
        "You are protected under the provisions [S9].",
        3,
        ["Source 1", "Source 2", "Source 3"],
        False,
    ),
    (
        'an answer citing "Section 999" not in sources fails',
        "You can seek relief under Section 999 [S1] of the law.",
        1,
        ["Section 85 — Husband or relative of husband subjecting woman to cruelty"],
        False,
    ),
    (
        '"Section 85" present in a source passes',
        "Cruelty by a husband or in-laws is punishable under Section 85 [S1].",
        1,
        ["Section 85 — Husband or relative of husband subjecting woman to cruelty"],
        True,
    ),
    (
        'citing "Section 12" with only "Section 124" in sources fails',
        "You are protected under Section 12 [S1].",
        1,
        ["Section 124 — Assault or criminal force to woman with intent to outrage her modesty"],
        False,
    ),
    (
        '"section 75" (lowercase) with "Section 75" in sources passes',
        "This is prohibited under section 75 [S1].",
        1,
        ["Section 75 — Sexual harassment"],
        True,
    ),
    (
        '"section 999" (lowercase) not in sources fails',
        "You can seek relief under section 999 [S1] of the law.",
        1,
        ["Section 85 — Husband or relative of husband subjecting woman to cruelty"],
        False,
    ),
]


def test_build_context():
    """build_context marks a 'Scenario' heading and leaves other headings unchanged."""
    results = [
        {
            "heading": "Scenario: supervisor touching and colleagues' gossip",
            "act": "POSH",
            "text": "A worker is touched.",
        },
        {
            "heading": "Section 3. Prevention of sexual harassment",
            "act": "POSH",
            "text": "No woman shall be subjected to harassment.",
        },
    ]
    ctx = build_context(results)
    expected_s1 = (
        "[S1] (ILLUSTRATIVE EXAMPLE about a different woman, not the user's facts) "
        "Scenario: supervisor touching and colleagues' gossip (POSH)\n"
        "A worker is touched."
    )
    expected_s2 = (
        "[S2] Section 3. Prevention of sexual harassment (POSH)\n"
        "No woman shall be subjected to harassment."
    )
    assert expected_s1 in ctx, f"Expected S1 with ILLUSTRATIVE EXAMPLE marker, got:\n{ctx}"
    assert expected_s2 in ctx, f"Expected S2 unchanged, got:\n{ctx}"
    print("  [PASS] build_context marks a 'Scenario' heading and leaves other headings unchanged")


def test_advice_phrases_check():
    """Advice phrases check: fails on crafted bad answers and passes on clean ones."""
    source_texts = ["Section 85 — Cruelty by husband"]
    # Bad answer with advice
    bad_ans = "You should consult a lawyer [S1] for legal options."
    ok, reason = verify_answer(bad_ans, 1, source_texts)
    assert ok is False, "Expected advice answer to fail"
    assert reason == "Contains advice not in the sources: 'consult a lawyer'.", f"Got: {reason!r}"

    # Clean answer
    clean_ans = "Husband subjecting woman to cruelty is punishable under Section 85 [S1]."
    ok, reason = verify_answer(clean_ans, 1, source_texts)
    assert ok is True, f"Expected clean answer to pass, got: {reason!r}"
    print("  [PASS] advice phrases check fails on bad answer and passes on clean answer")


def test_definition_attribution_check():
    """Definition attribution check: fails on crafted bad answers and passes on clean ones."""
    # Bad answer: Section 85 does not define anything in the heading
    source_texts = ["Section 85 — Husband or relative of husband subjecting woman to cruelty"]
    bad_ans = "Cruelty is defined in Section 85 [S1] of the law."
    ok, reason = verify_answer(bad_ans, 1, source_texts)
    assert ok is False, "Expected bad definition attribution to fail"
    assert reason == "Section 85 does not define anything in the sources.", f"Got: {reason!r}"

    # Clean answer: Section 3 heading contains 'Definition'
    source_texts_def = ["Section 3. Definition of domestic violence"]
    clean_ans = "Domestic violence is defined in Section 3 [S1]."
    ok, reason = verify_answer(clean_ans, 1, source_texts_def)
    assert ok is True, f"Expected valid definition attribution to pass, got: {reason!r}"
    print("  [PASS] definition attribution check fails on bad answer and passes on clean answer")


def test_scenario_leakage_check():
    """Scenario leakage check: scenario source with 'dupatta' fails on mention and passes when clean."""
    source_texts = [
        (
            "[S1] (ILLUSTRATIVE EXAMPLE about a different woman, not the user's facts) "
            "Scenario: supervisor touching (POSH)\n"
            "A factory supervisor keeps trying to touch a worker on pretexts such as adjusting her dupatta."
        ),
        (
            "[S2] Section 3. Prevention of sexual harassment (POSH)\n"
            "No woman shall be subjected to sexual harassment at any workplace."
        ),
    ]
    query = "my boss keeps touching me at work"

    # Bad answer mentioning 'dupatta'
    bad_ans = "Your boss touching your dupatta is considered sexual harassment [S1]."
    ok, reason = verify_answer(bad_ans, 2, source_texts, query=query)
    assert ok is False, "Expected answer mentioning dupatta to fail scenario leakage"
    assert reason == "Answer uses details from an illustrative example: 'dupatta'.", f"Got: {reason!r}"

    # Clean answer
    clean_ans = "Unwelcome touching at work can constitute sexual harassment under Section 3 [S2]."
    ok, reason = verify_answer(clean_ans, 2, source_texts, query=query)
    assert ok is True, f"Expected clean answer to pass scenario leakage, got: {reason!r}"
    print("  [PASS] scenario leakage check fails on 'dupatta' and passes on clean answer")


def test_section_mention_support_check():
    """Section mention check: tests for Section 175(3), table cells, Section 124 vs 12, 12 weeks."""
    # answer "Section 175(3)" with a source row "| ... | 173(4) (...), then 175(3) (Magistrate) |" passes
    src_table = ["| ... | 173(4) (...), then 175(3) (Magistrate) |"]
    ans_175_3 = "You can apply under Section 175(3) [S1] to the Magistrate."
    ok, reason = verify_answer(ans_175_3, 1, src_table)
    assert ok is True, f"Expected Section 175(3) to pass, got: {reason!r}"

    # answer "Section 175" with no source containing 175 fails
    src_no_175 = ["Section 85 — Cruelty by husband"]
    ans_175 = "You can apply under Section 175 [S1] to the Magistrate."
    ok, reason = verify_answer(ans_175, 1, src_no_175)
    assert ok is False, "Expected Section 175 to fail"
    assert reason == "Mentioned 'Section 175' does not appear in any source.", f"Got: {reason!r}"

    # answer "Section 12" with only "Section 124" in the sources still fails
    src_124 = ["Section 124 — Assault or criminal force to woman"]
    ans_12 = "You have rights under Section 12 [S1]."
    ok, reason = verify_answer(ans_12, 1, src_124)
    assert ok is False, "Expected Section 12 with only Section 124 to fail"
    assert reason == "Mentioned 'Section 12' does not appear in any source.", f"Got: {reason!r}"

    # answer "Section 12" with only "12 weeks" in the sources fails
    src_12_weeks = ["A woman is entitled to 12 weeks of leave."]
    ok, reason = verify_answer(ans_12, 1, src_12_weeks)
    assert ok is False, "Expected Section 12 with only '12 weeks' to fail"
    assert reason == "Mentioned 'Section 12' does not appear in any source.", f"Got: {reason!r}"

    print("  [PASS] section mention check supports 175(3), rejects 124/12 weeks, fails absent sections")


PHOTOS_ANSWER = """If someone shared your private photos without your consent, you may be able to claim a violation of your right to privacy under the Information Technology Act, 2000.

According to Section 66E of the IT Act, intentionally or knowingly capturing, publishing, or transmitting an image of your private area without your consent, under circumstances violating your privacy, is punishable with imprisonment up to 3 years or with a fine up to Rs. 2,00,000 or both. [S1]

To determine if this applies to your situation, the court will consider whether you had a reasonable expectation of privacy in the circumstances where the images were captured. [S3] This means that the person who shared your photos must have intentionally or knowingly captured your image without your consent, and in circumstances where you could have reasonably expected to disrobe in privacy without being concerned about being photographed. [S3]

If you believe that your right to privacy has been violated, you can report the incident to the authorities. The court can direct the respondent to take action, including providing compensation for the violation of your right to privacy. [Note: This is not a step you must take, but rather a statement of what the court can direct the respondent to do.]

It is also worth noting that Section 77 of the Bharatiya Nyaya Sanhita, 2023, deals with voyeurism, which may also apply to your situation. However, this section is more specific to watching or capturing images of women in private acts, and may not directly apply to the sharing of private photos. [S2]

Next steps:

* You may want to report the incident to the police or other authorities.
* You may want to seek compensation for the violation of your right to privacy.
* You may want to consult with a lawyer or other expert for guidance on how to proceed."""


def test_advice_variants_check():
    """Check a: advice variants fail unless present in sources; clean answer passes."""
    source_texts = ["Section 85 — Cruelty by husband or relative of husband"]

    bad_ans = "You should consult with a legal professional [S1] before filing anything."
    ok, reason = verify_answer(bad_ans, 1, source_texts)
    assert ok is False, "Expected advice variant answer to fail"
    assert reason == "Contains advice not in the sources: 'consult with a legal professional'.", f"Got: {reason!r}"

    bad_seek = "You can seek legal guidance from an authority [S1]."
    ok, reason = verify_answer(bad_seek, 1, source_texts)
    assert ok is False, "Expected seek legal guidance variant to fail"
    assert reason == "Contains advice not in the sources: 'seek legal guidance from'.", f"Got: {reason!r}"

    bad_other = "You can speak to a doctor or other professional [S1]."
    ok, reason = verify_answer(bad_other, 1, source_texts)
    assert ok is False, "Expected or other professional variant to fail"
    assert reason == "Contains advice not in the sources: 'or other professional'.", f"Got: {reason!r}"

    clean_ans = "Cruelty by a husband is an offence under Section 85 [S1]."
    ok, reason = verify_answer(clean_ans, 1, source_texts)
    assert ok is True, f"Expected clean answer to pass, got: {reason!r}"
    print("  [PASS] advice variants check fails on bad answers and passes on clean answer")


def test_bracketed_notes_check():
    """Check b: [Note ...], [NB ...], [Disclaimer ...] fail; clean answer passes."""
    source_texts = ["Section 85 — Cruelty by husband"]

    for note_tag in [
        "[Note: This is general information.]",
        "[NB verify facts carefully]",
        "[Disclaimer: Not legal advice]",
    ]:
        bad_ans = f"Cruelty by a husband is punishable under Section 85 [S1]. {note_tag}"
        ok, reason = verify_answer(bad_ans, 1, source_texts)
        assert ok is False, f"Expected bracketed note {note_tag} to fail"
        assert reason == "Contains a bracketed note.", f"Got: {reason!r}"

    clean_ans = "Cruelty by a husband is punishable under Section 85 [S1]."
    ok, reason = verify_answer(clean_ans, 1, source_texts)
    assert ok is True, f"Expected clean answer without bracketed note to pass, got: {reason!r}"
    print("  [PASS] bracketed notes check fails on [Note/NB/Disclaimer] and passes on clean answer")


def test_uncited_paragraphs_check():
    """Check c: uncited paragraph >= 120 chars after paragraph 1 fails; cited or short/first passes."""
    source_texts = ["Section 85 — Cruelty by husband"]

    first_para = "This introductory paragraph has no citation but should be ignored because it is the first paragraph of the response and may exceed one hundred twenty characters."
    long_uncited = (
        "This second paragraph explains legal consequences in considerable detail without attaching any source reference marker anywhere inside its text."
    )
    bad_ans = f"{first_para}\n\n{long_uncited}\n\nCruelty is punishable under Section 85 [S1]."
    ok, reason = verify_answer(bad_ans, 1, source_texts)
    assert ok is False, "Expected long uncited non-first paragraph to fail"
    assert reason == "Paragraph without a citation.", f"Got: {reason!r}"

    short_uncited = "Short note under 120 chars."
    long_cited = (
        "This paragraph has plenty of characters over one hundred and twenty, and it properly includes a source marker at the end [S1]."
    )
    clean_ans = f"{first_para}\n\n{short_uncited}\n\n{long_cited}"
    ok, reason = verify_answer(clean_ans, 1, source_texts)
    assert ok is True, f"Expected clean paragraph structure to pass, got: {reason!r}"
    print("  [PASS] uncited paragraphs check fails on >=120 char uncited paragraph and passes otherwise")


def test_photos_answer_fails():
    """The pasted PHOTOS_ANSWER must fail verify_answer with reason from check a, b or c."""
    sources = [
        "Section 66E — Information Technology Act, 2000: Whoever, intentionally or knowingly captures, publishes or transmits the image of a private area of any person without his or her consent, under circumstances violating the privacy of that person, shall be punished with imprisonment up to three years or fine up to two lakh rupees or both.",
        "Section 77 — Bharatiya Nyaya Sanhita, 2023: Voyeurism — watching or capturing the image of a woman engaging in a private act in circumstances where she would usually have the expectation of not being observed.",
        "Section 66E (Explanation) — Under circumstances violating privacy means circumstances in which a person can have a reasonable expectation that he or she could disrobe in privacy, without being concerned that an image of his or her private area was being captured.",
    ]
    ok, reason = verify_answer(PHOTOS_ANSWER, 3, sources)
    assert ok is False, "Expected PHOTOS_ANSWER to fail verify_answer"
    valid_reasons = (
        reason.startswith("Contains advice not in the sources:")
        or reason == "Contains a bracketed note."
        or reason == "Paragraph without a citation."
    )
    assert valid_reasons, f"Expected reason from check a, b or c, got: {reason!r}"
    print(f"  [PASS] PHOTOS_ANSWER failed verification as expected ({reason})")


def run():
    passed = 0
    failed = 0

    for name, answer_text, n_sources, source_texts, expect_pass in TEST_CASES:
        ok, reason = verify_answer(answer_text, n_sources, source_texts)
        case_passed = (ok == expect_pass)
        status = "PASS" if case_passed else "FAIL"
        if case_passed:
            passed += 1
        else:
            failed += 1
        print(f"  [{status}] {name}")
        print(f"         expected={expect_pass}, got={ok} (reason: {reason!r})")

    extra_tests = [
        test_build_context,
        test_advice_phrases_check,
        test_definition_attribution_check,
        test_scenario_leakage_check,
        test_section_mention_support_check,
        test_advice_variants_check,
        test_bracketed_notes_check,
        test_uncited_paragraphs_check,
        test_photos_answer_fails,
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
