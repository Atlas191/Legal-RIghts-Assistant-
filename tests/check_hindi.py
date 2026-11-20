"""Evaluation script for Hindi and Hinglish queries against the live pipeline.
Requires Ollama running locally.
Run:  ./venv/bin/python tests/check_hindi.py
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("HF_HUB_OFFLINE", "1")

from lang import detect_language, translate_to_english, glossary_keywords
from pipeline import get_pipeline
from retrieval import retrieve

TEST_CASES = [
    {
        "query": "मेरे पति मुझे मारते हैं और घर से निकाल दिया",
        "expected": ["Domestic Violence"],
        "expect_off_topic": False,
    },
    {
        "query": "मेरा बॉस मुझे काम पर गलत तरीके से छूता है",
        "expected": ["POSH"],
        "expect_off_topic": False,
    },
    {
        "query": "mera pati mujhe maarta hai aur ghar se nikal diya",
        "expected": ["Domestic Violence"],
        "expect_off_topic": False,
    },
    {
        "query": "office mein mera boss mujhe galat tarah se chhuta hai",
        "expected": ["POSH"],
        "expect_off_topic": False,
    },
    {
        "query": "ek aadmi mera peecha karta hai aur baar baar call karta hai",
        "expected": ["Section 78"],
        "expect_off_topic": False,
    },
    {
        "query": "kisi ne meri private photos bina meri ijazat ke share kar di",
        "expected": ["66E"],
        "expect_off_topic": False,
    },
    {
        "query": "sasural wale dahej maang rahe hain",
        "expected": ["Dowry", "Section 85", "Section 80"],
        "expect_off_topic": False,
    },
    {
        "query": "police ne meri FIR likhne se mana kar diya",
        "expected": ["Nagarik Suraksha"],
        "expect_off_topic": False,
    },
    {
        "query": "mere paas vakeel ke paise nahi hain",
        "expected": ["Legal Services"],
        "expect_off_topic": False,
    },
    {
        "query": "mujhe pregnancy ki wajah se naukri se nikal diya",
        "expected": ["Maternity"],
        "expect_off_topic": False,
    },
    {
        "query": "passport kaise banwayein",
        "expected": [],
        "expect_off_topic": True,
    },
]


def run_checks():
    print("=" * 100)
    print("HINDI & HINGLISH RETRIEVAL EVALUATION")
    print("=" * 100)

    pipe = get_pipeline()
    search = pipe.search

    table_rows = []
    all_passed = True

    for item in TEST_CASES:
        q = item["query"]
        expected = item["expected"]
        expect_off_topic = item["expect_off_topic"]

        lang = detect_language(q)
        trans = translate_to_english(q) or ""
        kws = glossary_keywords(q)
        search_query = (trans + " " + " ".join(kws)).strip() if lang != "en" else q

        ret = retrieve(search, search_query)
        off_topic = ret["off_topic"]
        results = ret.get("results", [])
        first_heading = results[0]["heading"] if results else "None"
        first_act = results[0]["act"] if results else ""

        if expect_off_topic:
            status = "PASS" if off_topic else "FAIL"
        else:
            matches_expected = any(
                exp.lower() in first_heading.lower() or exp.lower() in first_act.lower()
                for exp in expected
            )
            status = "PASS" if (not off_topic and matches_expected) else "FAIL"

        if status == "FAIL":
            all_passed = False

        table_rows.append({
            "query": q,
            "lang": lang,
            "trans": trans[:80],
            "off_topic": off_topic,
            "heading": f"{first_heading} ({first_act})" if first_act else first_heading,
            "status": status,
        })

    # Print markdown table
    print(f"\n| {'Query':<45} | {'Lang':<8} | {'Translation (first 80 chars)':<35} | {'Off Topic':<10} | {'Status':<6} | First Heading |")
    print(f"|{'-'*47}|{'-'*10}|{'-'*37}|{'-'*12}|{'-'*8}|{'-'*30}|")
    for row in table_rows:
        q_disp = row["query"] if len(row["query"]) <= 43 else row["query"][:40] + "..."
        trans_disp = row["trans"] if len(row["trans"]) <= 33 else row["trans"][:30] + "..."
        head_disp = row["heading"] if len(row["heading"]) <= 35 else row["heading"][:32] + "..."
        print(f"| {q_disp:<45} | {row['lang']:<8} | {trans_disp:<35} | {str(row['off_topic']):<10} | {row['status']:<6} | {head_disp} |")

    print("\n" + "=" * 100)
    print("END-TO-END PIPELINE RUNS (2 QUERIES)")
    print("=" * 100)

    e2e_queries = [
        "मेरे पति मुझे मारते हैं और घर से निकाल दिया",
        "mera pati mujhe maarta hai aur ghar se nikal diya",
    ]

    for q in e2e_queries:
        print(f"\n--- Testing Query: {q} ---")
        t0 = time.time()
        res = pipe.ask(q)
        elapsed = time.time() - t0

        print(f"Time taken: {elapsed:.2f}s")
        print(f"Detected Lang: {res.detected_lang} | Response Lang: {res.response_lang}")
        print(f"Translation Verified: {res.translation_verified}")
        print(f"\n[English Original Answer (answer_en)]:\n{res.answer_en}")
        print(f"\n[Translated Answer (answer)]:\n{res.answer}")
        print(f"\n[Disclaimer]: {res.disclaimer}")
        print("-" * 80)

    print("\nOverall Status:", "ALL PASSED" if all_passed else "SOME CHECKS FAILED")


if __name__ == "__main__":
    run_checks()
