"""Unit tests for verify_answer in generate.py (no Ollama required)."""
import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from generate import verify_answer

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
]


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

    print(f"\n{passed}/{passed + failed} passed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
