"""Forum routing module — rules-based recommendations for legal forums and helplines.
Pure Python rules, no LLM, no network.
Decides applicable forums based on the query text and retrieved section metadata.
Returns tuple[list[Forum], list[str]].
"""
import re
from schemas import Forum

# Forum definitions
LCC_TIME_LIMIT = (
    "3 months from the last incident, extendable by up to 3 months "
    "for reasons recorded in writing (verify)"
)
ICC_TIME_LIMIT = LCC_TIME_LIMIT

PWDVA_TIME_LIMIT = (
    "First hearing ordinarily within 3 days of the application; "
    "the Magistrate tries to decide within 60 days"
)

POSH = {"posh_handbook", "posh_act_supplement"}
PWDVA = {"pwdva_2005"}
CRIMINAL = {"bns_2023", "it_act_2000", "bnss_2023"}
NCW = {"ncw_charter"}


def route(query: str, results: list[dict]) -> tuple[list[Forum], list[str]]:
    """Determine legal forums and clarification questions based on query and results.

    Returns:
        (forums, needs_info): list of recommended Forum objects and list of questions.
    """
    q = (query or "").lower().strip()
    doc_ids = {
        r["id"].split(":")[0]
        for r in (results or [])
        if isinstance(r, dict) and "id" in r
    }

    if not q and not doc_ids:
        return [], []

    urgent_safety: list[Forum] = []
    institutional: list[Forum] = []
    criminal: list[Forum] = []
    legal_aid: list[Forum] = []
    ncw: list[Forum] = []
    needs_info: list[str] = []

    need_legal_aid = False

    # 1. Workplace harassment (POSH)
    has_posh_doc = bool(doc_ids & POSH)
    has_workplace_word = bool(re.search(
        r"\b(work|office|boss|colleague|colleagues|manager|employer|owner|maid|domestic\s+help|domestic\s+worker)\b",
        q,
    ))
    has_harassment_word = bool(re.search(
        r"\b(touch\w*|harass\w*|grop\w*|molest\w*|advance\w*|favou?r\w*|remark\w*|comment\w*|assault\w*|inappropriate|sexual\w*|stare\w*|stalk\w*)\b",
        q,
    ))
    is_workplace = has_posh_doc or (has_workplace_word and has_harassment_word)

    if is_workplace:
        hc_match = re.search(r"(\d+)\s*(?:employees|people|staff|workers)", q)
        headcount = int(hc_match.group(1)) if hc_match else None

        is_against_employer = bool(re.search(r"\b(employer|owner)\b", q))
        is_domestic_worker = bool(re.search(
            r"\b(maid|domestic\s+help|domestic\s+worker|works?\s+in\s+a\s+house)\b", q
        ))

        if is_against_employer or is_domestic_worker:
            institutional.append(Forum(
                name="Local Complaints Committee (LCC)",
                why="Complaint against the employer or domestic worker goes to the district LCC",
                time_limit=LCC_TIME_LIMIT,
                kb_ref="posh_handbook",
                category="institutional",
            ))
        elif headcount is not None:
            if headcount >= 10:
                institutional.append(Forum(
                    name="Internal Complaints Committee (ICC)",
                    why="Workplaces with 10 or more workers must have an Internal Complaints Committee (ICC)",
                    time_limit=ICC_TIME_LIMIT,
                    kb_ref="posh_handbook",
                    category="institutional",
                ))
            else:
                institutional.append(Forum(
                    name="Local Complaints Committee (LCC)",
                    why="Workplaces with fewer than 10 workers fall under the district Local Complaints Committee (LCC)",
                    time_limit=LCC_TIME_LIMIT,
                    kb_ref="posh_handbook",
                    category="institutional",
                ))
        else:
            institutional.append(Forum(
                name="Internal Complaints Committee (ICC)",
                why="If your workplace has 10 or more workers, the complaint goes to the Internal Complaints Committee (ICC)",
                time_limit=ICC_TIME_LIMIT,
                kb_ref="posh_handbook",
                category="institutional",
            ))
            institutional.append(Forum(
                name="Local Complaints Committee (LCC)",
                why="If your workplace has fewer than 10 workers (or the complaint is against the employer), it goes to the district LCC",
                time_limit=LCC_TIME_LIMIT,
                kb_ref="posh_handbook",
                category="institutional",
            ))
            needs_info.append("How many people work at your workplace?")

    # 2. Domestic violence / home (PWDVA)
    has_pwdva_doc = bool(doc_ids & PWDVA)
    has_dv_word = bool(re.search(
        r"\b(husband|in-laws|in\s+laws|inlaws|marital|thrown\s+out|kicked\s+out|beats?|beaten|dowry|hits?|abuse\w*|violen\w*|wife|slap\w*|hurt\w*)\b",
        q,
    ))
    is_dv = has_pwdva_doc or has_dv_word

    if is_dv:
        has_violence = bool(re.search(
            r"\b(beat\w*|hits?|abuse\w*|violen\w*|slap\w*|hurt\w*|thrown\s+out|kicked\s+out|threat\w*|unsafe)\b",
            q,
        ))
        if has_violence:
            urgent_safety.append(Forum(
                name="One Stop Centre / Women Helpline 181",
                why="Emergency rescue, medical aid, shelter, and psycho-social support for women in distress (status: verify)",
                time_limit=None,
                kb_ref="helplines_and_portals",
                category="safety",
            ))

        institutional.append(Forum(
            name="Protection Officer / Magistrate (PWDVA)",
            why="Provides protection orders, residence orders, and emergency relief against domestic violence",
            time_limit=PWDVA_TIME_LIMIT,
            kb_ref="pwdva_2005",
            category="institutional",
        ))
        need_legal_aid = True

    # 3. Criminal offence (BNS, BNSS, IT Act)
    has_crim_doc = bool(doc_ids & CRIMINAL)
    has_crim_word = bool(re.search(
        r"\b(police|fir|zero\s+fir|stalk\w*|threat\w*|photos?|rape\w*|molest\w*)\b",
        q,
    ))
    is_criminal = has_crim_doc or has_crim_word

    if is_criminal:
        criminal.append(Forum(
            name="Police station - FIR or Zero FIR",
            why="To report a cognizable criminal offence and register an FIR under BNSS",
            time_limit=None,
            kb_ref="bnss_2023",
            category="criminal",
        ))
        police_refused = bool(re.search(
            r"(police\s+refused|refus\w+|not\s+register\w*|won'?t\s+register\w*|refusing)",
            q,
        ))
        if police_refused:
            criminal.append(Forum(
                name="Superintendent of Police, then Magistrate",
                why="If police refuse to register an FIR, you can submit the complaint in writing to the SP or approach the Judicial Magistrate under BNSS",
                time_limit=None,
                kb_ref="bnss_2023",
                category="criminal",
            ))
        need_legal_aid = True

    # 4. Online abuse
    is_online_abuse = bool(re.search(
        r"\b(online|instagram|whatsapp|morphed|photos?|messages?|cyber\w*)\b",
        q,
    ))

    if is_online_abuse:
        criminal.append(Forum(
            name="National Cyber Crime Reporting Portal (cybercrime.gov.in)",
            why="Specialized portal to report cybercrimes, online abuse, and non-consensual sharing of intimate images",
            time_limit=None,
            kb_ref="helplines_and_portals",
            category="criminal",
        ))

    # 5. Money or cost worries (DLSA)
    is_money_worries = bool(re.search(r"\b(afford|lawyer|legal\s+aid|free)\b", q))

    if is_money_worries or need_legal_aid:
        legal_aid.append(Forum(
            name="District Legal Services Authority (free legal aid)",
            why="A woman qualifies under section 12(c) whatever her income",
            time_limit=None,
            kb_ref="nalsa_charter",
            category="legal_aid",
        ))

    # 6. National Commission for Women (NCW) - always append last if legal forums apply
    has_any_forum = bool(urgent_safety or institutional or criminal or legal_aid)
    has_ncw_doc = bool(doc_ids & NCW)
    is_ncw_query = has_ncw_doc or bool(re.search(r"\b(ncw|national\s+commission\s+for\s+women)\b", q))

    if has_any_forum or is_ncw_query:
        ncw.append(Forum(
            name="National Commission for Women",
            why="Can examine complaints and take them up with authorities but is not a court and is not an implementing agency",
            time_limit=None,
            kb_ref="ncw_charter",
            category="national",
        ))

    # Return forums in this order: urgent safety, institutional, criminal, legal aid, NCW. No duplicates.
    ordered = urgent_safety + institutional + criminal + legal_aid + ncw
    seen = set()
    forums: list[Forum] = []
    for f in ordered:
        if f.name not in seen:
            seen.add(f.name)
            forums.append(f)

    return forums, needs_info
