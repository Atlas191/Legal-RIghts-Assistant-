"""Actionable roadmap builder: constructs sequential immediate, institutional, and legal steps.
Pure Python rules, no LLM, no network.
Returns list[RoadmapStep].
"""
import re
from lra.schemas import Forum, RoadmapAction, RoadmapStep

GENERAL_GUIDANCE_SUFFIX = " (general guidance, not a legal requirement)"


def build_roadmap(
    query: str,
    results: list[dict],
    forums: list[Forum],
    needs_info: list[str] | None = None,
) -> list[RoadmapStep]:
    """Construct an actionable sequential roadmap based on query and recommended forums.

    Returns:
        list of RoadmapStep (renumbered 1..n, omitting empty steps).
    """
    if not forums:
        return []

    q = (query or "").lower().strip()
    step1_actions: list[RoadmapAction] = []

    # --- Step 1: Immediate steps ---
    # Immediate danger check
    has_safety = any(f.category == "safety" for f in forums)
    has_danger_word = bool(re.search(
        r"\b(beat\w*|hits?|threat\w*|unsafe|kicked\s+out|thrown\s+out)\b",
        q,
    ))
    if has_safety or has_danger_word:
        step1_actions.append(RoadmapAction(
            text="If you are in immediate danger, call 112.",
            basis="kb",
            kb_ref="helplines_and_portals",
            time_limit=None,
        ))

    # Evidence guidance (max 6 actions, deduplicated)
    raw_evidence: list[str] = []

    has_workplace = any(
        f.name in ["Internal Complaints Committee (ICC)", "Local Complaints Committee (LCC)"]
        for f in forums
    )
    if has_workplace:
        raw_evidence.extend([
            "Write down each incident with date, time, place and witnesses",
            "Keep messages, emails and screenshots",
            "Save your own copy of the evidence somewhere outside the workplace system",
        ])

    has_pwdva = any("pwdva" in f.name.lower() for f in forums)
    if has_pwdva:
        raw_evidence.extend([
            "Get any injuries medically examined and keep the report",
            "Photograph injuries and damage",
            "Keep copies of messages and call logs",
        ])

    has_cyber = any("cyber" in f.name.lower() for f in forums)
    if has_cyber:
        raw_evidence.extend([
            "Take screenshots showing the page address and date",
            "Do not delete the messages or the account",
            "Note the sender's username or number",
        ])

    has_sp = any("superintendent" in f.name.lower() for f in forums)
    if has_sp:
        raw_evidence.append(
            "Keep a written copy of your complaint and any postal or email receipt"
        )

    seen = set()
    for text in raw_evidence:
        if text not in seen:
            seen.add(text)
            step1_actions.append(RoadmapAction(
                text=text + GENERAL_GUIDANCE_SUFFIX,
                basis="general_guidance",
                kb_ref=None,
                time_limit=None,
            ))
            if len(seen) == 6:
                break

    # --- Step 2: Institutional pathway ---
    inst_actions: list[RoadmapAction] = []
    for f in forums:
        if f.category == "institutional":
            inst_actions.append(RoadmapAction(
                text="Approach the " + f.name + ": " + f.why,
                basis="kb",
                kb_ref=f.kb_ref,
                time_limit=f.time_limit,
            ))

    has_needs_info = (
        bool(needs_info)
        if needs_info is not None
        else (
            any(f.name == "Internal Complaints Committee (ICC)" for f in forums)
            and any(f.name == "Local Complaints Committee (LCC)" for f in forums)
        )
    )
    if has_needs_info and inst_actions:
        inst_actions.append(RoadmapAction(
            text="Tell me how many people work at your workplace so I can narrow this down" + GENERAL_GUIDANCE_SUFFIX,
            basis="general_guidance",
            kb_ref=None,
            time_limit=None,
        ))

    # --- Step 3: Legal and judicial pathway ---
    legal_actions: list[RoadmapAction] = []
    for cat in ["criminal", "legal_aid", "national"]:
        for f in forums:
            if f.category == cat:
                legal_actions.append(RoadmapAction(
                    text="Approach the " + f.name + ": " + f.why,
                    basis="kb",
                    kb_ref=f.kb_ref,
                    time_limit=f.time_limit,
                ))

    # Compile candidate steps and renumber 1..n
    candidates = []
    if step1_actions:
        candidates.append(("immediate", "Immediate steps", step1_actions))
    if inst_actions:
        candidates.append(("institutional", "Institutional pathway", inst_actions))
    if legal_actions:
        candidates.append(("legal", "Legal and judicial pathway", legal_actions))

    roadmap: list[RoadmapStep] = []
    for idx, (kind, title, actions) in enumerate(candidates, 1):
        roadmap.append(RoadmapStep(
            step=idx,
            kind=kind,
            title=title,
            actions=actions,
        ))

    return roadmap
