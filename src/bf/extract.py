"""Clause extraction. Deterministic: numbering, bullets, requirement sentences and evaluation tables.

Each candidate clause gets a location, a mandatory flag, a scored flag and weight, and a category.
Clauses in introduction or background sections are kept only if they contain shall or must.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .documents import Document
from .util import norm_space, sha256_text

_NUMBERED = re.compile(
    r"^\s*(?:(?:section|clause|article)\s+)?(\d{1,3}(?:\.\d{1,3}){0,4}\.?|[A-Z]\.\d{1,3}(?:\.\d{1,3})*|\([a-z0-9]{1,3}\)|[a-z]\))\s+(\S.*)$",
    re.I,
)
_MD_HEADING = re.compile(r"^\s*#{1,6}\s+(.*)$")
_BULLET = re.compile(r"^\s*[-*•]\s+(\S.*)$")
_TABLE_ROW = re.compile(r"^\s*\|(.+)\|\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}")

_REQ = re.compile(
    r"\b(shall|must|is required to|are required to|required|mandatory|should|minimum|at least|not less than|"
    r"no fewer than|will be (evaluated|scored|assessed|disqualified)|disqualif\w*|"
    r"will (apply|be applied|be imposed)|(bidder|supplier|vendor|contractor|tenderer)s? (will|is to|are to)|submit|"
    r"provide (a|an|the|evidence|details|copies|proof))\b",
    re.I,
)
_STRONG = re.compile(r"\b(shall|must)\b", re.I)
_MANDATORY = re.compile(
    r"\b(shall|must|mandatory|is required|are required|required to|will be disqualified|disqualif\w*|"
    r"pre-?condition|minimum requirement|not less than|at least)\b",
    re.I,
)
_OPTIONAL = re.compile(r"\b(desirable|preferred|advantage|optional|may|nice to have|bonus)\b", re.I)
_WEIGHT = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*(%|percent|points?|marks?)", re.I)
_SKIP_SECTION = re.compile(r"\b(introduction|background|definitions?|overview|about (the|this)|glossary)\b", re.I)
_EVAL_SECTION = re.compile(r"\b(evaluation|criteria|scoring|award)\b", re.I)

# Ordered: the first match wins. Text is tested first, then the section heading.
CATEGORY_RULES: list[tuple[str, str]] = [
    ("submission_format", r"\b(submitted electronically|submission instructions|late submissions?|page limit|not exceed \d+ pages|font size|file format|in pdf format|envelope|sealed)\b"),
    ("data_residency", r"\b(data residency|hosted (with)?in|stored (with)?in|in[- ]kingdom|within the (kingdom|country|uae)|cst[- ]licensed|data centre in)\b"),
    ("local_content", r"\b(local content|lcgpa|in[- ]country value|icv)\b"),
    ("nationalisation", r"\b(saudi[sz]ation|nitaqat|emirati[sz]ation|saudi nationals|uae nationals|nationali[sz]ation)\b"),
    ("legal_registration", r"\b(commercial registration|trade licen[cs]e|vat registration|zakat|gosi|chamber of commerce|registered on (the )?etimad|tax registration)\b"),
    ("team", r"\b(cvs?|curriculum vitae|key personnel|service delivery manager|project manager|nominate|team members?|on-site team|staffing)\b"),
    ("certification", r"\b(iso(/iec)?\s*\d{4,5}|cmmi|soc ?2|certified|certificate|certification|accredit\w*)\b"),
    ("past_performance", r"\b(similar (projects|contracts|engagements)|past performance|reference letters?|client references|case stud(y|ies)|track record)\b"),
    ("financial", r"\b(turnover|audited financial|financial statements|bid bond|performance bond|bank guarantee|revenue of)\b"),
    ("contract_term", r"\b(liquidated damages|penalt(y|ies)|termination|liability|indemn\w*|governing law|warranty period)\b"),
    ("commercial", r"\b(financial proposal|pricing schedule|price|prices|pricing|payment terms|rates|cost|discount)\b"),
    ("form", r"\b(form|annex [a-z0-9]+|declaration|undertaking|pledge|letter of (authori[sz]ation|intent))\b"),
    ("sla", r"\b(service levels?|sla|response time|resolved within|responded to within|availability of|uptime|service credits)\b"),
    ("security_compliance", r"\b(nca|ecc|cybersecurity|cyber security|penetration test\w*|encryption|security controls)\b"),
    ("methodology", r"\b(methodology|approach|work plan|implementation plan|transition plan|project plan|knowledge transfer)\b"),
    ("eligibility", r"\b(eligib\w*|qualified bidders|pre-?qualification|years of experience|in business)\b"),
    ("technical_requirement", r"\b(solution|system|platform|shall support|service desk|functional|integrat\w*|operate)\b"),
]
_SECTION_FALLBACK = [
    ("eligibility", r"\beligib|legal|qualification"),
    ("certification", r"\bcertif"),
    ("past_performance", r"\bpast performance|experience|references"),
    ("technical_requirement", r"\btechnical|scope of work|requirements"),
    ("sla", r"\bservice level"),
    ("team", r"\bteam|personnel|staff"),
    ("methodology", r"\bimplementation|methodology|transition"),
    ("commercial", r"\bcommercial|financial proposal|pricing"),
    ("submission_format", r"\bsubmission"),
]


@dataclass
class Clause:
    id: str
    document: str
    page: int
    location: str
    number: str
    section: str
    text: str
    mandatory: bool
    scored: bool
    weight: float | None
    category: str
    kind: str  # clause | sentence | bullet | criterion


def categorize(text: str, section: str) -> str:
    for cat, pat in CATEGORY_RULES:
        if re.search(pat, text, re.I):
            return cat
    for cat, pat in _SECTION_FALLBACK:
        if re.search(pat, section or "", re.I):
            return cat
    return "other"


def _is_heading_like(number: str, rest: str) -> bool:
    return len(rest) <= 80 and not _REQ.search(rest) and not rest.rstrip().endswith((".", ":", ";"))


def _split_sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text) if s.strip()]


def extract_clauses(docs: list[Document]) -> list[Clause]:
    raw: list[dict] = []
    for doc in docs:
        multi_page = len(doc.pages) > 1
        section = ""
        for page_no, page in enumerate(doc.pages, start=1):
            block: dict | None = None

            def flush() -> None:
                nonlocal block
                if block and block["lines"]:
                    raw.append(block)
                block = None

            for line_no, line in enumerate(page.splitlines(), start=1):
                stripped = line.strip()
                if not stripped:
                    flush()
                    continue
                m = _MD_HEADING.match(line)
                if m:
                    flush()
                    section = norm_space(re.sub(r"^\d+(\.\d+)*\.?\s*", "", m.group(1)))
                    continue
                if _TABLE_ROW.match(line):
                    flush()
                    if _TABLE_SEP.match(line):
                        continue
                    cells = [c.strip() for c in _TABLE_ROW.match(line).group(1).split("|")]
                    if _EVAL_SECTION.search(section) and len(cells) >= 2 and _WEIGHT.search(cells[-1]):
                        raw.append({"doc": doc, "page": page_no, "line": line_no, "number": "", "section": section,
                                    "lines": [f"{cells[0]}: {cells[-1]}"], "kind": "criterion", "multi": multi_page})
                    continue
                m = _NUMBERED.match(line)
                if m:
                    flush()
                    number, rest = m.group(1).rstrip("."), m.group(2)
                    if _is_heading_like(number, rest) and "." not in number:
                        section = norm_space(rest)
                        continue
                    block = {"doc": doc, "page": page_no, "line": line_no, "number": number, "section": section,
                             "lines": [rest], "kind": "clause", "multi": multi_page}
                    continue
                m = _BULLET.match(line)
                if m:
                    flush()
                    block = {"doc": doc, "page": page_no, "line": line_no, "number": "", "section": section,
                             "lines": [m.group(1)], "kind": "bullet", "multi": multi_page}
                    continue
                if block is None:
                    block = {"doc": doc, "page": page_no, "line": line_no, "number": "", "section": section,
                             "lines": [], "kind": "paragraph", "multi": multi_page}
                block["lines"].append(stripped)
            flush()

    clauses: list[Clause] = []
    seen: set[str] = set()
    for b in raw:
        text = norm_space(" ".join(b["lines"]))
        pieces = [text]
        kind = b["kind"]
        if kind == "paragraph":
            pieces = [s for s in _split_sentences(text) if _REQ.search(s)]
            kind = "sentence"
        for piece in pieces:
            piece = piece[:1500]
            if kind != "criterion" and not _REQ.search(piece):
                continue
            if _SKIP_SECTION.search(b["section"]) and not _STRONG.search(piece):
                continue
            key = sha256_text(re.sub(r"\W+", " ", piece.lower()).strip()[:160])
            if key in seen:
                continue
            seen.add(key)
            in_eval = bool(_EVAL_SECTION.search(b["section"]))
            weight_m = _WEIGHT.search(piece) if (in_eval or kind == "criterion") else None
            scored = kind == "criterion" or in_eval or bool(re.search(r"\b(will be scored|scored)\b", piece, re.I))
            mandatory = bool(_MANDATORY.search(piece)) and not (
                _OPTIONAL.search(piece) and not _STRONG.search(piece)
            )
            if kind == "criterion":
                mandatory = False
            loc = f"clause {b['number']}" if b["number"] else f"line {b['line']}"
            if b["multi"]:
                loc += f", page {b['page']}"
            if b["section"]:
                loc += f" ({b['section']})"
            clauses.append(Clause(
                id="", document=b["doc"].name, page=b["page"], location=loc, number=b["number"],
                section=b["section"], text=piece, mandatory=mandatory, scored=scored,
                weight=float(weight_m.group(1)) if weight_m else None,
                category=categorize(piece, b["section"]), kind=kind,
            ))
    for i, c in enumerate(clauses, start=1):
        c.id = f"C-{i:03d}"
    return clauses


def clauses_to_json(clauses: list[Clause]) -> list[dict]:
    return [asdict(c) for c in clauses]
