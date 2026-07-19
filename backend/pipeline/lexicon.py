"""Canonical narrative-criterion lexicon shared by evidence agents and the
faithfulness oracle.

Single source of truth: `evidence.py` uses it to gather and side-label
narrative evidence; `faithfulness.py` uses it to verify that stored side
labels match what the cited text supports. Sharing the phrase inventory
removes silent drift between the grader and the system it grades. The
oracle's independence lives in its other checks (exact-span grounding,
structured value re-computation, evidence-table and guideline validation),
not in a second keyword list.

Demo-quality keyword matching for synthetic charts. Not for clinical use.
"""

from __future__ import annotations

import re
from typing import Literal

Side = Literal["for", "against"]

# Keyword bags for demo-quality narrative resolution (synthetic charts).
# "sepsis" is deliberately NOT infection evidence: clinical validation must
# not accept the billed diagnosis label as evidence for itself.
NARRATIVE_KEYWORDS: dict[str, dict[str, tuple[str, ...]]] = {
    "infection": {
        "for": (
            "infection",
            "infected",
            "antibiotic",
            "antibiotics",
            "ceftriaxone",
            "vancomycin",
            "piperacillin",
            "culture",
            "uti",
            "pneumonia",
            "bacteremia",
            "cellulitis",
            "pyelonephritis",
            "abscess",
            "fever",
            "febrile",
            "chills",
            "cough",
            "dysuria",
            "leukocytosis",
        ),
        "against": (
            "no infection",
            "infection ruled out",
            "cultures negative",
            "not infected",
            "aseptic",
        ),
    },
    "vasopressors": {
        "for": (
            "norepinephrine",
            "levophed",
            "phenylephrine",
            "vasopressin drip",
            "on pressors",
            "started on pressors",
            "started vasopressor",
            "requiring vasopressors",
            "vasopressors are being",
        ),
        "against": (
            "no vasopressor",
            "no vasopressors",
            "not requiring vasopressor",
            "not requiring vasopressors",
            "without vasopressor",
            "without vasopressors",
            "off vasopressors",
            "not on vasopressors",
            "did not require vasopressor",
            "did not require vasopressors",
            "no longer requiring vasopressor",
            "no longer requiring vasopressors",
            "no longer on vasopressors",
            "not requiring pressors",
        ),
    },
    "altered_mentation": {
        "for": (
            "altered mental",
            "altered mentation",
            "confused",
            "confusion",
            "obtunded",
            "delirium",
            "gcs",
            "glasgow coma scale",
            "unresponsive",
            "encephalopath",
            "mental status change",
        ),
        "against": (
            "alert and oriented",
            "mental status clear",
            "normal mental",
            "a&ox3",
            "a and o x3",
            "gcs 15",
            "glasgow coma scale score of 15",
            "neurologically intact",
        ),
    },
}

# Generic negation around vasopressor/pressor words (catches plural forms)
VASOPRESSOR_NEGATION_RES: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(no|not|without|never|denies?)\b.{0,40}\b(vasopressors?|pressors?)\b"
    ),
    re.compile(
        r"\b(vasopressors?|pressors?)\b.{0,40}\b(not required|not indicated|discontinued)\b"
    ),
)

# Generic affirmation: "started on vasopressors", "vasopressors have been
# started", "initiating pressors", etc. Checked only when negation is absent.
VASOPRESSOR_AFFIRMATION_RES: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"\b(start(?:ed|ing)?|initiat(?:ed|ing|e)|beg[au]n|requir(?:es|ing|ed)|"
        r"continu(?:es|ed|ing)|remains? on|placed on|titrat\w+|treated with|"
        r"receiv(?:ing|ed|es)|maintained on|supported (?:with|on))\b"
        r".{0,60}\b(vasopressors?|pressors?)\b"
    ),
    re.compile(
        r"\b(vasopressors?|pressors?)\b.{0,40}"
        r"\b(started|initiated|begun|continued|ongoing|required|titrat\w+)\b"
    ),
)


def score_text(
    text: str,
    for_kws: tuple[str, ...],
    against_kws: tuple[str, ...],
    *,
    apply_vasopressor_rules: bool = False,
) -> tuple[float, float]:
    """Score one excerpt: (for_score, against_score). Negation phrases weigh 2x."""
    lower = text.lower()
    for_score = 0.0
    against_score = 0.0
    for kw in for_kws:
        if kw in lower:
            for_score += 1.0
    for kw in against_kws:
        if kw in lower:
            against_score += 2.0  # stronger weight for explicit negation phrases
    if apply_vasopressor_rules:
        if any(p.search(lower) for p in VASOPRESSOR_NEGATION_RES):
            against_score += 2.5
            # Do not also credit bare "vasopressors" as for when negation present
            if for_score > 0 and against_score > for_score:
                for_score = max(0.0, for_score - 1.0)
        elif any(p.search(lower) for p in VASOPRESSOR_AFFIRMATION_RES):
            for_score += 2.0
    return for_score, against_score


# Explicit composite-criterion statements ("no evidence of organ dysfunction").
# Surveillance language ("monitor for signs of organ dysfunction") is neither
# side: planning to watch for a finding is not evidence about the finding.
_ORGAN_DYSFUNCTION_MONITORING_RE = re.compile(
    r"\b(monitor\w*|watch\w*|surveil\w*)\b.{0,50}\borgan (dys)?function\b"
)
_ORGAN_DYSFUNCTION_NEGATION_RE = re.compile(
    r"\b(no|not|without|never|lack of|absence of|ruled out|resolv\w+)\b"
    r".{0,60}\borgan dysfunction\b"
)
_ORGAN_DYSFUNCTION_AFFIRMATION_RE = re.compile(
    r"\b(presence of|evidence of|worsening|indicat\w+|develop\w+|"
    r"consistent with|due to)\b.{0,40}\borgan dysfunction\b"
    r"|\bmulti-?organ failure\b|\bend-organ damage\b"
)


def organ_dysfunction_side(text: str) -> Side | None:
    """Side of an explicit organ-dysfunction statement, or None if no signal."""
    lower = text.lower()
    if _ORGAN_DYSFUNCTION_MONITORING_RE.search(lower):
        return None
    if _ORGAN_DYSFUNCTION_NEGATION_RE.search(lower):
        return "against"
    if _ORGAN_DYSFUNCTION_AFFIRMATION_RE.search(lower):
        return "for"
    return None


def narrative_side(criterion_id: str, text: str) -> Side | None:
    """Side one narrative excerpt supports for its criterion, or None if no signal."""
    if criterion_id == "organ_dysfunction":
        return organ_dysfunction_side(text)
    bags = NARRATIVE_KEYWORDS.get(criterion_id)
    if bags is None:
        return None
    for_score, against_score = score_text(
        text,
        bags["for"],
        bags["against"],
        apply_vasopressor_rules=criterion_id == "vasopressors",
    )
    if against_score > for_score and against_score > 0:
        return "against"
    if for_score > against_score and for_score > 0:
        return "for"
    return None
