"""Unit tests for routing.py (pure Python rules, no Ollama).
Run:  python tests/test_routing.py
Exit code 0 = all pass, 1 = at least one failure.
"""
import os
import sys

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from lra.guidance.routing import route

ICC_NAME = "Internal Complaints Committee (ICC)"
LCC_NAME = "Local Complaints Committee (LCC)"
PWDVA_NAME = "Protection Officer / Magistrate (PWDVA)"
HELPLINE_NAME = "One Stop Centre / Women Helpline 181"
FIR_NAME = "Police station - FIR or Zero FIR"
SP_MAG_NAME = "Superintendent of Police, then Magistrate"
CYBER_NAME = "National Cyber Crime Reporting Portal (cybercrime.gov.in)"
DLSA_NAME = "District Legal Services Authority (free legal aid)"
NCW_NAME = "National Commission for Women"


def test_case_1():
    """1. 'my boss touches me, we are 40 people' -> ICC, not LCC"""
    forums, needs_info = route("my boss touches me, we are 40 people", [])
    names = [f.name for f in forums]
    assert ICC_NAME in names, f"Expected {ICC_NAME} in {names}"
    assert LCC_NAME not in names, f"Did not expect {LCC_NAME} in {names}"
    assert len(needs_info) == 0, f"Expected empty needs_info, got {needs_info}"
    return True


def test_case_2():
    """2. 'my boss touches me, we are 6 people' -> LCC, not ICC"""
    forums, needs_info = route("my boss touches me, we are 6 people", [])
    names = [f.name for f in forums]
    assert LCC_NAME in names, f"Expected {LCC_NAME} in {names}"
    assert ICC_NAME not in names, f"Did not expect {ICC_NAME} in {names}"
    assert len(needs_info) == 0, f"Expected empty needs_info, got {needs_info}"
    return True


def test_case_3():
    """3. 'my employer, the owner of the shop, harassed me' -> LCC"""
    forums, needs_info = route("my employer, the owner of the shop, harassed me", [])
    names = [f.name for f in forums]
    assert LCC_NAME in names, f"Expected {LCC_NAME} in {names}"
    assert ICC_NAME not in names, f"Did not expect {ICC_NAME} in {names}"
    return True


def test_case_4():
    """4. 'I am a maid and the owner's son touches me' -> LCC"""
    forums, needs_info = route("I am a maid and the owner's son touches me", [])
    names = [f.name for f in forums]
    assert LCC_NAME in names, f"Expected {LCC_NAME} in {names}"
    assert ICC_NAME not in names, f"Did not expect {ICC_NAME} in {names}"
    return True


def test_case_5():
    """5. 'my boss keeps touching me at work' -> both ICC and LCC plus a needs_info question"""
    forums, needs_info = route("my boss keeps touching me at work", [])
    names = [f.name for f in forums]
    assert ICC_NAME in names, f"Expected {ICC_NAME} in {names}"
    assert LCC_NAME in names, f"Expected {LCC_NAME} in {names}"
    assert any("how many people work" in q.lower() for q in needs_info), (
        f"Expected headcount question in {needs_info}"
    )
    return True


def test_case_6():
    """6. 'my husband beats me and threw me out' -> PWDVA forum, legal aid, NCW"""
    forums, needs_info = route("my husband beats me and threw me out", [])
    names = [f.name for f in forums]
    assert PWDVA_NAME in names, f"Expected {PWDVA_NAME} in {names}"
    assert DLSA_NAME in names, f"Expected {DLSA_NAME} in {names}"
    assert NCW_NAME in names, f"Expected {NCW_NAME} in {names}"
    return True


def test_case_7():
    """7. 'police refused to register my FIR' -> FIR, SP and Magistrate"""
    forums, needs_info = route("police refused to register my FIR", [])
    names = [f.name for f in forums]
    assert FIR_NAME in names, f"Expected {FIR_NAME} in {names}"
    assert SP_MAG_NAME in names, f"Expected {SP_MAG_NAME} in {names}"
    return True


def test_case_8():
    """8. 'someone shared my private photos online' -> cybercrime portal and FIR"""
    forums, needs_info = route("someone shared my private photos online", [])
    names = [f.name for f in forums]
    assert CYBER_NAME in names, f"Expected {CYBER_NAME} in {names}"
    assert FIR_NAME in names, f"Expected {FIR_NAME} in {names}"
    return True


def test_case_9():
    """9. 'I can't afford a lawyer' -> DLSA"""
    forums, needs_info = route("I can't afford a lawyer", [])
    names = [f.name for f in forums]
    assert DLSA_NAME in names, f"Expected {DLSA_NAME} in {names}"
    return True


def test_case_10():
    """10. 'capital of india' -> empty routing"""
    forums, needs_info = route("capital of india", [])
    assert len(forums) == 0, f"Expected no forums, got {[f.name for f in forums]}"
    assert len(needs_info) == 0, f"Expected no needs_info, got {needs_info}"
    return True


def test_case_maternity_pregnant():
    """a) maternity results with 'can my employer fire me for being pregnant' -> forums == [] and needs_info == []"""
    res = [{
        "id": "maternity_benefit:3",
        "act": "Maternity Benefit Act, 1961 (as amended 2017)",
        "heading": "Section 12 — Dismissal during absence or pregnancy",
        "section": "Section 12",
        "source_file": "x",
    }]
    forums, needs_info = route("can my employer fire me for being pregnant", res)
    assert forums == [], f"Expected forums == [], got {forums}"
    assert needs_info == [], f"Expected needs_info == [], got {needs_info}"
    return True


def test_case_maternity_leave():
    """b) same maternity results with 'my employer did not give me maternity leave' -> forums == []"""
    res = [{
        "id": "maternity_benefit:3",
        "act": "Maternity Benefit Act, 1961 (as amended 2017)",
        "heading": "Section 5 — Right to payment of maternity benefit",
        "section": "Section 5",
        "source_file": "x",
    }]
    forums, needs_info = route("my employer did not give me maternity leave", res)
    assert forums == [], f"Expected forums == [], got {forums}"
    return True


def test_case_posh_touching():
    """c) POSH results ('posh_handbook:20') with 'my boss keeps touching me at work' -> ICC and LCC both present, needs_info has headcount question"""
    res = [{
        "id": "posh_handbook:20",
        "act": "POSH Act",
        "heading": "Section 3 — Prevention of sexual harassment",
        "section": "Section 3",
        "source_file": "x",
    }]
    forums, needs_info = route("my boss keeps touching me at work", res)
    names = [f.name for f in forums]
    assert ICC_NAME in names, f"Expected {ICC_NAME} in {names}"
    assert LCC_NAME in names, f"Expected {LCC_NAME} in {names}"
    assert any("how many people work" in q.lower() for q in needs_info), (
        f"Expected headcount question in {needs_info}"
    )
    return True


def test_case_bnss_maintenance():
    """d) BNSS results ('bnss_2023:9') with 'my husband is not paying maintenance' -> PWDVA forum present, One Stop Centre/181 absent"""
    res = [{
        "id": "bnss_2023:9",
        "act": "Bharatiya Nagarik Suraksha Sanhita, 2023",
        "heading": "Section 144 — Maintenance for wife and children",
        "section": "Section 144",
        "source_file": "x",
    }]
    forums, needs_info = route("my husband is not paying maintenance", res)
    names = [f.name for f in forums]
    assert PWDVA_NAME in names, f"Expected {PWDVA_NAME} in {names}"
    assert HELPLINE_NAME not in names, f"Did not expect {HELPLINE_NAME} in {names}"
    return True


def test_exact_ordering_all_categories():
    """e) 'my husband beat me, police refused to register my FIR and I cannot afford a lawyer' -> all five categories present, exact index order urgent < institutional < FIR < SP/Magistrate < DLSA < NCW"""
    query = "my husband beat me, police refused to register my FIR and I cannot afford a lawyer"
    forums, _ = route(query, [])
    names = [f.name for f in forums]

    assert HELPLINE_NAME in names, f"Missing {HELPLINE_NAME}"
    assert PWDVA_NAME in names, f"Missing {PWDVA_NAME}"
    assert FIR_NAME in names, f"Missing {FIR_NAME}"
    assert SP_MAG_NAME in names, f"Missing {SP_MAG_NAME}"
    assert DLSA_NAME in names, f"Missing {DLSA_NAME}"
    assert NCW_NAME in names, f"Missing {NCW_NAME}"

    idx_urgent = names.index(HELPLINE_NAME)
    idx_inst = names.index(PWDVA_NAME)
    idx_fir = names.index(FIR_NAME)
    idx_sp = names.index(SP_MAG_NAME)
    idx_dlsa = names.index(DLSA_NAME)
    idx_ncw = names.index(NCW_NAME)

    assert idx_urgent < idx_inst < idx_fir < idx_sp < idx_dlsa < idx_ncw, (
        f"Incorrect ordering: urgent({idx_urgent}) < inst({idx_inst}) < "
        f"fir({idx_fir}) < sp({idx_sp}) < dlsa({idx_dlsa}) < ncw({idx_ncw})"
    )
    return True


TESTS = [
    ("1. my boss touches me, we are 40 people -> ICC, not LCC", test_case_1),
    ("2. my boss touches me, we are 6 people -> LCC, not ICC", test_case_2),
    ("3. my employer, the owner of the shop, harassed me -> LCC", test_case_3),
    ("4. I am a maid and the owner's son touches me -> LCC", test_case_4),
    ("5. my boss keeps touching me at work -> both ICC and LCC plus needs_info", test_case_5),
    ("6. my husband beats me and threw me out -> PWDVA, DLSA, NCW", test_case_6),
    ("7. police refused to register my FIR -> FIR, SP and Magistrate", test_case_7),
    ("8. someone shared my private photos online -> cybercrime portal and FIR", test_case_8),
    ("9. I can't afford a lawyer -> DLSA", test_case_9),
    ("10. capital of india -> empty routing", test_case_10),
    ("a) maternity pregnant -> empty routing and needs_info", test_case_maternity_pregnant),
    ("b) maternity leave -> empty routing", test_case_maternity_leave),
    ("c) POSH touching -> both ICC and LCC plus headcount question", test_case_posh_touching),
    ("d) BNSS maintenance -> PWDVA present, 181 absent", test_case_bnss_maintenance),
    ("e) exact ordering all categories: urgent < inst < FIR < SP < DLSA < NCW", test_exact_ordering_all_categories),
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
