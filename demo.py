"""Hybrid retrieval demo — CLI front-end.
Shows only results that are actually relevant, and politely refuses off-topic questions.
Optional --llm flag enables plain-language answer generation with citation verification."""
import sys
import textwrap
from retrieval import load_search, retrieve

DEBUG = True             # True prints the scores behind each decision

WIDTH = 96
DISCLAIMER = "General legal information only, not legal advice. In an emergency call 112."
OFF_TOPIC_MSG = (
    "I'm a legal assistant for women's rights in India, so I can't help with that question.\n"
    "Try describing a situation about:\n"
    "  - harassment at work (POSH Act)\n"
    "  - domestic violence or being thrown out of your home (PWDVA)\n"
    "  - stalking, voyeurism, threats or online harassment (BNS)\n"
    "  - cruelty or dowry harassment by a husband or in-laws (BNS)\n"
    "  - what the National Commission for Women can do"
)


def show(result, llm_res=None):
    print("\n" + "=" * WIDTH)
    if result["off_topic"]:
        print(OFF_TOPIC_MSG)
        if DEBUG:
            print(f"\n[debug] best dense distance {result['best_dist']:.2f}, best BM25 {result['max_bm25']:.1f}")
        print("=" * WIDTH)
        return

    if llm_res is not None:
        print("LEGAL ASSISTANT ANSWER:")
        print("=" * WIDTH)
        for para in llm_res["answer"].split("\n"):
            print(textwrap.fill(para, width=WIDTH))
        print("\n" + "=" * WIDTH)

    print(f"RELEVANT LEGAL SECTIONS FOUND: {len(result['results'])}")
    print("=" * WIDTH)
    for i, r in enumerate(result["results"], 1):
        print(f"\n[{i}] {r['heading']}")
        print(f"    Law    : {r['act']}")
        if r["formerly_ipc"]:
            print(f"    Formerly IPC: {r['formerly_ipc']}")
        print(f"    Source : {r['source_file']}")
        print("    " + "-" * (WIDTH - 4))
        for para in r["text"].split("\n"):
            print(textwrap.fill(para, width=WIDTH, initial_indent="    ", subsequent_indent="    "))
    print("\n" + "-" * WIDTH)
    print(DISCLAIMER)


if __name__ == "__main__":
    use_llm = "--llm" in sys.argv
    if use_llm:
        from generate import answer

    search = load_search()

    print("Legal Rights Assistant for Women (prototype). Describe a situation, or type 'quit'.")
    while True:
        query = input("\n👤 Your situation: ").strip()
        if query.lower() in ("quit", "exit"):
            break
        if query:
            res = retrieve(search, query)
            llm_res = answer(query, res) if use_llm else None
            show(res, llm_res=llm_res)
