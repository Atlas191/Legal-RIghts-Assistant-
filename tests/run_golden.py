"""Golden-set regression test for the retrieval pipeline.
Run:  python tests/run_golden.py
Exit code 0 = all pass, 1 = at least one failure.
"""
import os, sys

# Ensure the project root is on sys.path so imports work from tests/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from retrieval import load_search, retrieve

# (query, expect, substring_or_None)
# expect = "refuse"  -> off_topic must be True
# expect = "match"   -> off_topic must be False AND substring must appear
#                        in at least one result's "heading" or "act"
#                        ("498A" and "section 85" require the FIRST result's heading to contain it)
CASES = [
    ("498A",
     "match", "Section 85"),
    ("section 85",
     "match", "Section 85"),
    ("354D",
     "match", "Section 78"),
    ("IPC 354D",
     "match", "Section 78"),
    ("BNS 78",
     "match", "Section 78"),
    ("capital of india",
     "refuse", None),
    ("how can i apply for a new passport or renew my driving licence online",
     "refuse", None),
    ("how do i file my income tax return",
     "refuse", None),
    ("my boss keeps touching me at work",
     "match", "POSH"),
    ("my husband beats me and threw me out",
     "match", "Protection of Women from Domestic Violence"),
    ("someone is sending me obscene messages online",
     "match", "Information Technology"),
    ("can my employer fire me for being pregnant",
     "match", "Maternity"),
    ("a man keeps following me and calling me",
     "match", "Section 78"),
    ("someone shared my private photos without my consent",
     "match", "66E"),
    ("what can the National Commission for Women do",
     "match", "National Commission for Women"),
    ("how long do I have to file a complaint at work",
     "match", "POSH"),
    ("police refused to register my FIR",
     "match", "Bharatiya Nagarik Suraksha"),
    ("I can't afford a lawyer",
     "match", "Legal Services"),
    ("what number do I call for help",
     "match", "Helplines"),
    ("my complaint is more than three months old at work",
     "match", "POSH"),
    ("how to open a bank account",
     "refuse", None),
    ("what is the best way to invest in mutual funds",
     "refuse", None),
    ("how to apply for a pan card online",
     "refuse", None),
    ("my husband's family keeps demanding more dowry",
     "match", "Dowry"),
    ("he threatens to post my photos if I leave him",
     "match", "Criminal intimidation"),
    ("my manager asks for sexual favours in return for a promotion",
     "match", "Sexual harassment"),
    ("my employer did not give me maternity leave",
     "match", "Maternity"),
    ("someone is stalking me on instagram",
     "match", "Stalking"),
    ("how do I report a cyber crime",
     "match", "cybercrime"),
    ("my husband is not paying maintenance",
     "match", "Maintenance"),
    ("can I get free legal help for domestic violence",
     "match", "Legal Services"),
    ("I was thrown out of my in-laws house",
     "match", "Domestic Violence"),
    ("66E",
     "match", "66E"),
]


def run():
    print("Loading search engine...")
    search = load_search()
    passed = 0
    failed = 0

    for query, expect, substring in CASES:
        result = retrieve(search, query)
        ok = False
        detail = ""

        if expect == "refuse":
            ok = result["off_topic"]
            detail = "off_topic=%s dist=%.2f bm25=%.1f" % (
                result["off_topic"], result["best_dist"], result["max_bm25"])
        elif expect == "match":
            if result["off_topic"]:
                detail = "WRONGLY REFUSED  dist=%.2f bm25=%.1f" % (
                    result["best_dist"], result["max_bm25"])
            else:
                if query in {"498A", "section 85"}:
                    ok = bool(result["results"] and substring in result["results"][0]["heading"])
                else:
                    for r in result["results"]:
                        if substring in r["heading"] or substring in r["act"]:
                            ok = True
                            break
                heads = [r["heading"] for r in result["results"]]
                acts  = [r["act"]     for r in result["results"]]
                detail = "headings=%s  acts=%s" % (heads, acts)

        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"  [{status}] {query!r}")
        print(f"         expect={expect} substr={substring!r}")
        print(f"         {detail}")

    print(f"\n{passed}/{passed + failed} passed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run())
