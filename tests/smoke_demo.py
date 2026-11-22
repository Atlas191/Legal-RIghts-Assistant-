"""Smoke demo script for Legal Rights Assistant (runs against real Ollama model).

Runs 8 diverse queries, displays an evaluation table, prints full answers for queries 1, 2, and 4,
executes follow-up context resolution, and builds a complaint draft.
Exits with code 1 if an exception occurs, query 8 is not off-topic, or follow-up does not route to ICC.
"""
import os
import sys
import time

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pipeline import get_pipeline
from schemas import Turn, DraftRequest
from draft import build_draft


def main():
    pipe = get_pipeline()

    queries = [
        "my boss keeps touching me at work",
        "my husband beats me and threw me out",
        "someone shared my private photos without my consent",
        "police refused to register my FIR",
        "I can't afford a lawyer",
        "498A",
        "mera pati mujhe maarta hai aur ghar se nikal diya",
        "how do i file my income tax return",
    ]

    results = []
    print("\n" + "=" * 90)
    print("RUNNING SMOKE DEMO (8 QUERIES)")
    print("=" * 90)

    for i, q in enumerate(queries, 1):
        t0 = time.time()
        res = pipe.ask(q)
        elapsed = time.time() - t0
        first_heading = res.sources[0].heading if res.sources else "None"
        forum_names = ", ".join(f.name.split(" — ")[0] for f in res.routing) if res.routing else "None"
        step_count = len(res.roadmap)
        results.append({
            "idx": i,
            "query": q,
            "detected_lang": res.detected_lang,
            "off_topic": res.off_topic,
            "verified": res.verified,
            "fallback": res.fallback,
            "seconds": elapsed,
            "first_heading": first_heading,
            "forum_names": forum_names,
            "step_count": step_count,
            "answer": res.answer,
        })

    # Print table
    print("\n" + "=" * 140)
    print(f"{'#':<3} | {'Query':<52} | {'Lang':<5} | {'OffTop':<6} | {'Verif':<5} | {'Fallbk':<6} | {'Sec':<5} | {'Steps':<5} | {'First Heading':<30} | {'Forums'}")
    print("-" * 140)
    for r in results:
        q_disp = (r['query'][:49] + "...") if len(r['query']) > 52 else r['query']
        h_disp = (r['first_heading'][:27] + "...") if len(r['first_heading']) > 30 else r['first_heading']
        print(f"{r['idx']:<3} | {q_disp:<52} | {r['detected_lang']:<5} | {str(r['off_topic']):<6} | {str(r['verified']):<5} | {str(r['fallback']):<6} | {r['seconds']:<5.2f} | {r['step_count']:<5} | {h_disp:<30} | {r['forum_names']}")
    print("=" * 140)

    # Print full answer text for queries 1, 2, and 4
    for idx in (1, 2, 4):
        item = results[idx - 1]
        print("\n" + "-" * 70)
        print(f"FULL ANSWER FOR QUERY {idx}: \"{item['query']}\"")
        print("-" * 70)
        print(item["answer"])

    # Follow-up test: query 1 followed by "we are 40 people" with history
    print("\n" + "=" * 70)
    print("FOLLOW-UP TEST: Query 1 followed by 'we are 40 people'")
    print("=" * 70)
    q1_item = results[0]
    history = [
        Turn(role="user", text=q1_item["query"]),
        Turn(role="assistant", text=q1_item["answer"]),
    ]
    follow_up_q = "we are 40 people"
    res_follow = pipe.ask(follow_up_q, history=history)
    print(f"Resolved query: {res_follow.resolved_query}")
    follow_forums = [f.name for f in res_follow.routing]
    print(f"Forum names: {follow_forums}")

    has_icc = any("Internal Complaints Committee" in name for name in follow_forums)
    has_lcc = any("Local Complaints Committee" in name for name in follow_forums)
    print(f"ICC present: {has_icc} (expected True), LCC present: {has_lcc} (expected False)")

    # Build draft from query 1 narrative with pipeline search
    print("\n" + "=" * 70)
    print("DRAFT TEST: Building draft from Query 1 narrative")
    print("=" * 70)
    draft_req = DraftRequest(narrative=q1_item["query"])
    draft_res = build_draft(draft_req, search=pipe.search)
    print("--- LETTER BODY ---")
    print(draft_res.body)
    print("\n--- MISSING FIELDS ---")
    print(draft_res.missing_fields)

    # Validation checks for exit code
    q8_item = results[7]
    if not q8_item["off_topic"]:
        print(f"\n[ERROR] Query 8 expected off_topic=True, got {q8_item['off_topic']}")
        sys.exit(1)

    if not has_icc or has_lcc:
        print(f"\n[ERROR] Follow-up expected ICC present and LCC absent, got {follow_forums}")
        sys.exit(1)

    print("\n[SUCCESS] All smoke demo checks passed.")
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n[EXCEPTION] smoke_demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
