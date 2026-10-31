"""Data tier classification at intake. See docs/data-protection.md section 3.

Tier C: classified, or third-party processing prohibited. Humans only.
Tier B: confidential or restricted material, or anything not declared public. In-country model only.
Tier A: declared public by the operator and no B or C markers found. Frontier model allowed.

The tier can be raised by the operator, never lowered below what the text implies.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_C = [
    r"\btop secret\b",
    r"\bsecurity classification\s*:\s*(secret|top secret|classified)\b",
    r"\bclassified (information|documents?|material)\b",
    r"\b(must|shall|may) not be (disclosed|shared|provided|made available|processed)[^.]{0,40}\bthird[- ]part(y|ies)\b",
    r"\bthird[- ]party processing (is )?(strictly )?prohibited\b",
    r"\bprohibited from (sharing|disclosing|processing)[^.]{0,60}\bthird[- ]part",
    r"سري للغاية",
]
_B = [
    r"\bconfidential\b",
    r"\brestricted\b",
    r"\bnot for (public )?distribution\b",
    r"\bnon[- ]disclosure\b",
    r"\bNDA\b",
    r"\b(tender|rfp|bid|these) documents?[^.]{0,80}\b(outside|within) (the )?(kingdom|ksa|uae|country)\b",
    r"\bسري\b",
    r"\bمقيد\b",
]
# Recorded for the reviewer, but they describe the delivered solution, not the tender documents.
_RESIDENCY = [
    r"\b(hosted|stored|processed|located|reside)\s+(with)?in\s+(the\s+)?(kingdom|ksa|saudi arabia|uae|united arab emirates|country)\b",
    r"\bdata residency\b",
    r"\bin[- ]kingdom\b",
]

RANK = {"A": 0, "B": 1, "C": 2}


class TierError(ValueError):
    pass


@dataclass
class TierResult:
    tier: str
    detected: str
    reasons: list[str] = field(default_factory=list)
    residency_mentions: list[str] = field(default_factory=list)


def _hits(patterns: list[str], text: str) -> list[str]:
    found = []
    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            found.append(m.group(0))
    return found


def classify(text: str, declared_public: bool = False, requested: str | None = None) -> TierResult:
    c_hits, b_hits = _hits(_C, text), _hits(_B, text)
    residency = _hits(_RESIDENCY, text)
    reasons: list[str] = []
    if c_hits:
        detected = "C"
        reasons += [f"Tier C marker: '{h}'" for h in c_hits]
    elif b_hits:
        detected = "B"
        reasons += [f"Tier B marker: '{h}'" for h in b_hits]
    elif declared_public:
        detected = "A"
        reasons.append("declared public by operator; no B or C markers found")
    else:
        detected = "B"
        reasons.append("not declared public; default Tier B")
    tier = detected
    if requested:
        requested = requested.upper()
        if requested not in RANK:
            raise TierError(f"unknown tier {requested}")
        if RANK[requested] < RANK[detected]:
            raise TierError(f"cannot lower tier from {detected} to {requested}: {'; '.join(reasons)}")
        if requested != detected:
            reasons.append(f"raised to Tier {requested} by operator")
        tier = requested
    return TierResult(tier=tier, detected=detected, reasons=reasons, residency_mentions=residency)
