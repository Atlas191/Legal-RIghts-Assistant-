"""Unit tests for roadmap.py (no LLM, no network).
Run:  python tests/test_roadmap.py
Exit code 0 = all pass, 1 = at least one failure.
"""
import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from lra.schemas import Forum, RoadmapAction, RoadmapStep
from lra.guidance.routing import route
from lra.guidance.roadmap import build_roadmap
from lra.pipeline import LegalPipeline


def test_case_1_workplace_40_people():
    """1. workplace query with 40 people -> 3 steps; step 2 mentions ICC with the 3-month time_limit; evidence actions mention dates and witnesses"""
    query = "my boss touches me, we are 40 people"
    forums, needs_info = route(query, [])
    roadmap = build_roadmap(query, [], forums, needs_info)

    assert len(roadmap) == 3, f"Expected 3 steps, got {len(roadmap)}"
    step2 = roadmap[1]
    assert step2.kind == "institutional"
    assert any(
        "Internal Complaints Committee (ICC)" in a.text
        and a.time_limit is not None
        and "3 months" in a.time_limit
        for a in step2.actions
    ), f"ICC with 3-month time_limit missing in step 2: {[a.text for a in step2.actions]}"

    step1 = roadmap[0]
    assert any("date" in a.text.lower() and "witness" in a.text.lower() for a in step1.actions), (
        f"Dates and witnesses missing in step 1: {[a.text for a in step1.actions]}"
    )
    return True


def test_case_2_domestic_violence():
    """2. domestic violence query -> step 1's first action is 112; step 2 mentions the Protection Officer"""
    query = "my husband beats me and threw me out"
    forums, needs_info = route(query, [])
    roadmap = build_roadmap(query, [], forums, needs_info)

    assert len(roadmap) >= 2, f"Expected at least 2 steps, got {len(roadmap)}"
    step1 = roadmap[0]
    assert len(step1.actions) > 0
    assert "112" in step1.actions[0].text, f"First action is not 112: {step1.actions[0].text}"

    step2 = roadmap[1]
    assert any("Protection Officer" in a.text for a in step2.actions), (
        f"Protection Officer missing in step 2: {[a.text for a in step2.actions]}"
    )
    return True


def test_case_3_police_refusal():
    """3. police refused query -> an action about keeping a written copy and the SP, Magistrate forum in step 3"""
    query = "my husband beat me and police refused to register my FIR"
    forums, needs_info = route(query, [])
    roadmap = build_roadmap(query, [], forums, needs_info)

    # Step 1 should contain written copy action
    step1 = roadmap[0]
    assert any("written copy" in a.text.lower() for a in step1.actions), (
        f"Written copy action missing in step 1: {[a.text for a in step1.actions]}"
    )

    # Step 3 should contain SP, Magistrate forum
    assert len(roadmap) == 3, f"Expected 3 steps, got {len(roadmap)}"
    step3 = roadmap[2]
    assert step3.kind == "legal"
    assert any("Superintendent of Police, then Magistrate" in a.text for a in step3.actions), (
        f"SP/Magistrate missing in step 3: {[a.text for a in step3.actions]}"
    )
    return True


def test_case_4_online_abuse():
    """4. online abuse query -> cybercrime portal in step 3, screenshot guidance in step 1"""
    query = "my boss harassed me and shared my private photos online"
    forums, needs_info = route(query, [])
    roadmap = build_roadmap(query, [], forums, needs_info)

    # Step 1 has screenshot guidance
    step1 = roadmap[0]
    assert any("screenshot" in a.text.lower() for a in step1.actions), (
        f"Screenshot guidance missing in step 1: {[a.text for a in step1.actions]}"
    )

    # Step 3 has cybercrime portal
    assert len(roadmap) == 3, f"Expected 3 steps, got {len(roadmap)}"
    step3 = roadmap[2]
    assert step3.kind == "legal"
    assert any("National Cyber Crime Reporting Portal" in a.text for a in step3.actions), (
        f"Cybercrime portal missing in step 3: {[a.text for a in step3.actions]}"
    )
    return True


def test_case_5_maternity_empty():
    """5. maternity query (forums == []) -> roadmap == []"""
    res = [{
        "id": "maternity_benefit:3",
        "act": "Maternity Benefit Act",
        "heading": "Section 12",
        "section": "Section 12",
        "source_file": "x",
    }]
    forums, needs_info = route("can my employer fire me for being pregnant", res)
    assert forums == []
    roadmap = build_roadmap("can my employer fire me for being pregnant", res, forums, needs_info)
    assert roadmap == [], f"Expected empty roadmap, got {roadmap}"
    return True


def test_case_6_pipeline_off_topic():
    """6. off-topic query through the pipeline -> roadmap == []"""
    pipe = LegalPipeline.__new__(LegalPipeline)
    pipe._search = lambda q: ([], {"off_topic": True, "best_dist": 0.99, "max_bm25": 0.0})
    result = pipe.ask("capital of india")
    assert result.off_topic is True
    assert result.roadmap == [], f"Expected empty roadmap, got {result.roadmap}"
    return True


def test_case_7_general_guidance_and_kb_rules():
    """7. every general_guidance action text ends with the required phrase; every kb action has a kb_ref and every time_limit appears verbatim in some forum"""
    test_queries = [
        "my boss touches me, we are 40 people",
        "my husband beats me and threw me out",
        "my husband beat me and police refused to register my FIR",
        "someone shared my private photos online",
        "my boss keeps touching me at work",
    ]
    for q in test_queries:
        forums, needs_info = route(q, [])
        roadmap = build_roadmap(q, [], forums, needs_info)
        for s in roadmap:
            for a in s.actions:
                if a.basis == "general_guidance":
                    assert a.text.endswith(" (general guidance, not a legal requirement)"), (
                        f"general_guidance action does not end with required suffix: {a.text}"
                    )
                elif a.basis == "kb":
                    assert a.kb_ref is not None and len(a.kb_ref) > 0, (
                        f"kb action missing kb_ref: {a.text}"
                    )
                    if a.time_limit is not None:
                        assert any(a.time_limit == f.time_limit for f in forums), (
                            f"time_limit {a.time_limit} does not appear verbatim in any forum"
                        )
    return True


def test_case_8_headcount_unknown_action():
    """8. a headcount-unknown workplace query -> roadmap contains the headcount action"""
    query = "my boss keeps touching me at work"
    forums, needs_info = route(query, [])
    roadmap = build_roadmap(query, [], forums, needs_info)

    all_actions = [a for s in roadmap for a in s.actions]
    assert any("how many people work at your workplace" in a.text.lower() for a in all_actions), (
        f"Headcount action missing from roadmap: {[a.text for a in all_actions]}"
    )
    return True


TESTS = [
    ("1. workplace query with 40 people -> 3 steps, ICC, dates/witnesses", test_case_1_workplace_40_people),
    ("2. domestic violence query -> 112 first, Protection Officer in step 2", test_case_2_domestic_violence),
    ("3. police refused query -> written copy action, SP/Magistrate in step 3", test_case_3_police_refusal),
    ("4. online abuse query -> cybercrime portal in step 3, screenshot guidance", test_case_4_online_abuse),
    ("5. maternity query (forums == []) -> roadmap == []", test_case_5_maternity_empty),
    ("6. off-topic query through pipeline -> roadmap == []", test_case_6_pipeline_off_topic),
    ("7. general_guidance ends with suffix; kb has kb_ref; time_limit verbatim", test_case_7_general_guidance_and_kb_rules),
    ("8. headcount-unknown workplace query -> contains headcount action", test_case_8_headcount_unknown_action),
]


def run():
    passed = 0
    failed = 0

    for desc, fn in TESTS:
        try:
            ok = fn()
            if ok:
                passed += 1
                print(f"  [PASS] {desc}")
            else:
                failed += 1
                print(f"  [FAIL] {desc}")
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {desc} — {type(e).__name__}: {e}")

    print(f"\n{passed}/{passed + failed} passed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
