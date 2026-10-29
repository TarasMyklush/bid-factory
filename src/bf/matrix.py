"""Compliance matrix builder. Output validates against schemas/compliance-matrix.schema.json.

Order of judgement for each clause:
1. Category rules that need no evidence (submission format, contract terms, commercial, evaluation rules).
2. Deterministic checks against library facts: named certifications and their expiry, minimum project counts,
   turnover, local content, nationalisation, years in business, annex forms.
3. A model judgement over retrieved candidates, if a model is allowed for the tier.
4. Otherwise, retrieval coverage thresholds.
Then, always: every cited record's expiry date is checked against the submission deadline.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from importlib import resources
from typing import Any

import jsonschema

from .library import Library, Record
from .models import BaseModel, ModelError
from .sections import SECTION_FOR_CATEGORY
from .util import first_words, parse_amount, parse_count, parse_datetime

ANSWERED_AT = 0.45
PARTIAL_AT = 0.25
EXPIRY_WARNING_DAYS = 90
GAP_LEAD_DAYS = 7
BATCH = 8

PREFERRED: dict[str, tuple[str, ...]] = {
    "eligibility": ("company", "registration", "financial"),
    "legal_registration": ("registration", "company"),
    "financial": ("financial", "company"),
    "local_content": ("company", "registration", "certification"),
    "nationalisation": ("company",),
    "certification": ("certification",),
    "past_performance": ("project",),
    "technical_requirement": ("product", "boilerplate", "policy"),
    "methodology": ("boilerplate", "product"),
    "team": ("person",),
    "sla": ("boilerplate", "product"),
    "security_compliance": ("policy", "certification"),
    "data_residency": ("product", "policy"),
    "commercial": ("commercial",),
    "form": ("form",),
}
_RANK = {"answered": 0, "not_applicable": 0, "partial": 1, "client_decision": 1, "gap": 2}
NITAQAT_BANDS = ["red", "low green", "medium green", "high green", "platinum"]


class MatrixError(ValueError):
    pass


@dataclass
class Judgement:
    status: str
    evidence: list[tuple[Record, str]] = field(default_factory=list)
    risk_note: str = ""
    gap_action: str = ""
    owner: str = "client"
    source: str = "rules"


def load_schema() -> dict:
    return json.loads(resources.files("bf").joinpath("schemas/compliance-matrix.schema.json").read_text("utf-8"))


def validate(matrix: dict) -> None:
    validator = jsonschema.Draft202012Validator(load_schema(), format_checker=jsonschema.FormatChecker())
    errors = sorted(validator.iter_errors(matrix), key=lambda e: list(e.path))
    if errors:
        lines = [f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}" for e in errors[:20]]
        raise MatrixError("matrix failed schema validation:\n  " + "\n  ".join(lines))


def _worse(a: str, b: str) -> str:
    return a if _RANK[a] >= _RANK[b] else b


# ---------------------------------------------------------------- deterministic checks

_STD = re.compile(r"\b(ISO(?:/IEC)?\s*\d{4,5}(?:-\d)?|CMMI(?:[- ](?:DEV|SVC))?(?:\s*(?:level|ML)\s*\d)?|SOC\s*2)\b", re.I)


def _norm_std(text: str) -> str:
    t = text.lower().replace("/iec", "")
    t = re.sub(r"iso\s*(\d{4,5})", r"iso\1", t)
    t = re.sub(r"soc\s*2", "soc2", t)
    t = re.sub(r"cmmi[- ]?(dev|svc)?\s*(level|ml)?\s*(\d)", r"cmmi\3", t)
    return t


def _std_keys(text: str) -> list[tuple[str, str]]:
    out = []
    for m in _STD.finditer(text):
        label = m.group(1)
        key = re.match(r"(iso\d{4,5}|soc2|cmmi\d?)", _norm_std(label))
        if key and key.group(1) not in [k for k, _ in out]:
            out.append((key.group(1), label))
    return out


def _expiry(rec: Record, deadline: date) -> tuple[str, str, str]:
    if rec.valid_until is None:
        return "answered", "", ""
    if rec.valid_until < deadline:
        return ("gap", f"{rec.id} expired or expires on {rec.valid_until}, before the submission deadline {deadline}",
                f"Obtain a renewed or current version of {rec.title}")
    if rec.valid_until < deadline + timedelta(days=EXPIRY_WARNING_DAYS):
        return ("partial", f"{rec.id} expires on {rec.valid_until}, within {EXPIRY_WARNING_DAYS} days of submission",
                f"Confirm renewal of {rec.title} is scheduled; the buyer may ask for it at contract signature")
    return "answered", "", ""


def check_certification(text: str, lib: Library, deadline: date) -> Judgement | None:
    keys = _std_keys(text)
    if not keys:
        return None
    j = Judgement(status="answered")
    notes, actions = [], []
    for key, label in keys:
        recs = [r for r in lib.by_type("certification") if key in _norm_std(r.corpus())]
        if not recs:
            j.status = _worse(j.status, "gap")
            notes.append(f"no {label} certificate in the library")
            actions.append(f"Provide a valid {label} certificate")
            continue
        best = max(recs, key=lambda r: r.valid_until or date.min)
        j.evidence.append((best, f"{best.title} covers {label}"))
        if best.valid_until is None:
            j.status = _worse(j.status, "partial")
            notes.append(f"{best.id}: no expiry date recorded")
            actions.append(f"Record the expiry date of {best.title}")
    j.risk_note = "; ".join(notes)
    j.gap_action = "; ".join(actions)
    j.source = "check:certification"
    return j


_MIN_COUNT = re.compile(
    r"(?:at least|minimum(?: of)?|not less than|no fewer than)\s+(\w+)(?:\s*\(\d+\))?\s+(?:\w+\s+){0,2}?"
    r"(projects|contracts|engagements|references|implementations)\b", re.I)


def check_min_projects(text: str, lib: Library) -> Judgement | None:
    m = _MIN_COUNT.search(text)
    if not m:
        return None
    n = parse_count(m.group(1))
    if not n:
        return None
    relevant = [(r, lib.coverage(text, r.id)[0]) for r in lib.by_type("project")]
    relevant = sorted([(r, c) for r, c in relevant if c >= 0.15], key=lambda x: -x[1])
    citable = [r for r, _ in relevant if r.permission != "no"]
    blocked = [r for r, _ in relevant if r.permission == "no"]
    j = Judgement(status="answered", source="check:project_count")
    j.evidence = [(r, f"similar project ({r.title})") for r in citable[: max(n, 1)]]
    notes = []
    on_request = [r.id for r in citable[:n] if r.permission == "on_request"]
    if on_request:
        notes.append(f"{', '.join(on_request)} may be cited only with the client's approval for this bid")
    if len(citable) < n:
        j.status = "gap"
        notes.insert(0, f"{len(citable)} citable similar projects in the library, {n} required")
        action = f"Add {n - len(citable)} more similar project record(s) with reference letters"
        if blocked:
            action += f", or obtain permission to cite {', '.join(r.id for r in blocked)}"
        j.gap_action = action
    j.risk_note = "; ".join(notes)
    return j


_TURNOVER = re.compile(
    r"(?:turnover|revenue)[^.]{0,80}?(?:not less than|at least|minimum(?: of)?|exceeding|in excess of)\s+"
    r"(SAR|SR|AED|USD|US\$)?\s*(\d[\d,.]*)\s*(million|mn|m|billion|bn)?\b", re.I)


def _company_figure(lib: Library, key: str) -> tuple[Record, Any] | None:
    for r in lib.by_type("company", "financial", "registration"):
        if key in r.figures:
            return r, r.figures[key]
    return None


def check_turnover(text: str, lib: Library) -> Judgement | None:
    m = _TURNOVER.search(text)
    if not m:
        return None
    required = parse_amount(m.group(2), m.group(3))
    currency = (m.group(1) or "").upper().replace("SR", "SAR").replace("US$", "USD") or None
    found = _company_figure(lib, "annual_turnover")
    if not found or required is None:
        return Judgement("gap", risk_note="no turnover figure in the library",
                         gap_action="Add audited turnover figures for the last three years", source="check:turnover")
    rec, have = found
    have = float(have)
    have_cur = rec.figures.get("turnover_currency")
    evidence = [(rec, f"reports annual turnover of {have_cur or ''} {have:,.0f}".replace("  ", " "))]
    evidence += [(r, "audited financial statements") for r in lib.by_type("financial")
                 if "audited" in r.corpus().lower()][:1]
    if currency and have_cur and currency != have_cur:
        return Judgement("partial", evidence, f"turnover recorded in {have_cur}, tender asks for {currency}",
                         "Convert turnover at the buyer's stated exchange rate and confirm", source="check:turnover")
    if have >= required:
        return Judgement("answered", evidence, source="check:turnover")
    return Judgement("gap", evidence, f"turnover {have:,.0f} is below the required {required:,.0f}",
                     "Turnover requirement not met: consider a consortium or a partner with the required turnover",
                     source="check:turnover")


_LOCAL_CONTENT = re.compile(r"local content[^.]{0,80}?(\d{1,3}(?:\.\d+)?)\s*%|(\d{1,3}(?:\.\d+)?)\s*%[^.]{0,40}local content", re.I)
_NATIONALS = re.compile(r"(\d{1,3})\s*%[^.]{0,80}\b(saudi|emirati|uae) nationals\b", re.I)


def check_percentage(text: str, lib: Library) -> Judgement | None:
    for pattern, key, label in ((_LOCAL_CONTENT, "local_content_pct", "local content score"),
                                (_NATIONALS, "saudi_nationals_pct", "share of Saudi nationals")):
        m = pattern.search(text)
        if not m:
            continue
        required = float(next(g for g in m.groups() if g and re.match(r"\d", g)))
        if pattern is _NATIONALS and m.group(2).lower() in ("emirati", "uae"):
            key, label = "uae_nationals_pct", "share of UAE nationals"
        found = _company_figure(lib, key)
        if not found:
            return Judgement("gap", risk_note=f"no {label} recorded in the library",
                             gap_action=f"Provide the current {label} with its certificate", source=f"check:{key}")
        rec, have = found
        ev = [(rec, f"has a {label} of {have}%")]
        if float(have) >= required:
            return Judgement("answered", ev, source=f"check:{key}")
        return Judgement("gap", ev, f"{label} {have}% is below the required {required:g}%",
                         f"Raise the {label} to {required:g}% or bid with a partner that meets it", source=f"check:{key}")
    return None


def check_nitaqat(text: str, lib: Library) -> Judgement | None:
    if not re.search(r"\bnitaqat\b", text, re.I):
        return None
    lowered = text.lower()
    named = [b for b in NITAQAT_BANDS if b in lowered]
    if not named:
        named = ["low green"] if "green" in lowered else []
    if not named:
        return None
    required = min(NITAQAT_BANDS.index(b) for b in named)
    found = _company_figure(lib, "nitaqat_band")
    if not found:
        return Judgement("gap", risk_note="no Nitaqat band recorded",
                         gap_action="Provide the current Nitaqat certificate", source="check:nitaqat")
    rec, band = found
    band = str(band).lower()
    if band in NITAQAT_BANDS and NITAQAT_BANDS.index(band) >= required:
        return Judgement("answered", [(rec, f"is in the {band} Nitaqat band")], source="check:nitaqat")
    return Judgement("gap", [(rec, f"is in the {band} Nitaqat band")], f"Nitaqat band {band} is below {NITAQAT_BANDS[required]}",
                     "Saudisation band does not meet the requirement", source="check:nitaqat")


_YEARS = re.compile(
    r"(?:at least|minimum(?: of)?|not less than|no fewer than)\s+(\w+)\s+years?\s+(?:of\s+)?"
    r"(?:experience|operations|operating|in business|track record)", re.I)


def check_years(text: str, lib: Library, deadline: date) -> Judgement | None:
    m = _YEARS.search(text)
    if not m:
        return None
    n = parse_count(m.group(1))
    if not n:
        return None
    found = _company_figure(lib, "founded_year") or _company_figure(lib, "years_in_business")
    if not found:
        return Judgement("gap", risk_note="founding year not recorded",
                         gap_action="Add the company's founding date", source="check:years")
    rec, value = found
    years = deadline.year - int(value) if "founded_year" in rec.figures else int(value)
    ev = [(rec, f"has {years} years in business" + (f", founded in {value}" if "founded_year" in rec.figures else ""))]
    if years >= n:
        return Judgement("answered", ev, source="check:years")
    return Judgement("gap", ev, f"{years} years in business, {n} required",
                     "Experience requirement not met: consider a partner", source="check:years")


_ANNEX = re.compile(r"\bannex\s+([a-z0-9]{1,3})\b", re.I)


def check_forms(text: str, lib: Library) -> Judgement | None:
    annexes = [a.upper() for a in _ANNEX.findall(text)]
    if not annexes:
        return None
    forms = lib.by_type("form")
    j = Judgement("answered", source="check:forms")
    missing = []
    for a in annexes:
        hit = next((f for f in forms if re.search(rf"\bannex\s+{a}\b", f.corpus(), re.I)), None)
        if hit:
            j.evidence.append((hit, f"completed Annex {a}"))
        else:
            missing.append(a)
    if missing:
        j.status = "partial" if j.evidence else "gap"
        j.risk_note = f"no completed form in the library for Annex {', '.join(missing)}"
        j.gap_action = f"Complete and sign Annex {', '.join(missing)}"
    return j


# ---------------------------------------------------------------- category rules

_EVAL_RULE = re.compile(r"\b(will be (evaluated|scored|assessed|disqualified)|carries|weight(ed|ing)?|pass mark|out of \d+)\b", re.I)
_BIDDER_ACTION = re.compile(r"\b(bidder|supplier|vendor|contractor|tenderer)s? (shall|must)\b", re.I)
_VALIDITY = re.compile(r"\bvalid for (\d{1,4}) days\b", re.I)


def category_rule(clause: dict, pricing: dict | None) -> Judgement | None:
    cat, text = clause["category"], clause["text"]
    if cat == "submission_format":
        return Judgement("answered", owner="bid_factory", source="rule:submission",
                         risk_note="Handled in pack assembly and the submission checklist")
    if cat == "contract_term":
        return Judgement("client_decision", source="rule:contract_term",
                         gap_action="Client's legal review: accept, qualify or seek clarification on this term")
    if cat == "commercial":
        if not pricing:
            return Judgement("client_decision", source="rule:commercial",
                             gap_action="Provide the pricing sheet for this bid")
        m = _VALIDITY.search(text)
        if m and int(pricing.get("validity_days") or 0) < int(m.group(1)):
            return Judgement("client_decision", source="rule:commercial",
                             risk_note=f"pricing sheet validity {pricing.get('validity_days')} days, tender requires {m.group(1)}",
                             gap_action=f"Confirm prices can be held for {m.group(1)} days")
        return Judgement("answered", source="rule:commercial",
                         risk_note="Priced from the client's pricing sheet; the client signs off every figure")
    if cat == "other" and clause.get("kind") != "criterion" and _EVAL_RULE.search(text) and not _BIDDER_ACTION.search(text):
        return Judgement("not_applicable", owner="bid_factory", source="rule:evaluation",
                         risk_note="Evaluation rule; informs the pass mark and weighting, no response required")
    return None


def deterministic_check(clause: dict, lib: Library, deadline: date) -> Judgement | None:
    text, cat = clause["text"], clause["category"]
    if clause.get("kind") == "criterion":
        return None
    checks = []
    if cat in ("certification", "security_compliance", "local_content"):
        checks.append(lambda: check_certification(text, lib, deadline))
    if cat in ("past_performance", "eligibility"):
        checks.append(lambda: check_min_projects(text, lib))
    if cat in ("financial", "eligibility"):
        checks.append(lambda: check_turnover(text, lib))
    if cat in ("local_content", "nationalisation", "eligibility"):
        checks.append(lambda: check_percentage(text, lib))
    if cat in ("nationalisation", "eligibility"):
        checks.append(lambda: check_nitaqat(text, lib))
    if cat == "eligibility":
        checks.append(lambda: check_years(text, lib, deadline))
    if cat == "form":
        checks.append(lambda: check_forms(text, lib))
    for run in checks:
        j = run()
        if j is not None:
            return j
    return None


def coverage_judgement(clause: dict, candidates: list[tuple[Record, float, list[str]]]) -> Judgement:
    prefer = PREFERRED.get(clause["category"], ())
    good = [c for c in candidates if c[1] >= ANSWERED_AT]
    if good and (not prefer or good[0][0].type in prefer):
        return Judgement("answered", [(r, f"matches on: {', '.join(s[:5])}") for r, _, s in good[:3]],
                         source="rules:coverage")
    if candidates and candidates[0][1] >= PARTIAL_AT:
        typed = [c for c in candidates[:3] if not prefer or c[0].type in prefer][:2] or candidates[:1]
        return Judgement("partial", [(r, f"partial match on: {', '.join(s[:5])}") for r, _, s in typed],
                         "Evidence is indirect; strengthen before submission",
                         "Confirm or add evidence that directly answers this clause", source="rules:coverage")
    return Judgement("gap", gap_action=f"Provide evidence for: {first_words(clause['text'], 90)}", source="rules:coverage")


# ---------------------------------------------------------------- model judgement

JUDGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["judgements"],
    "properties": {
        "judgements": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["clause_id", "status", "evidence_ids", "relevance", "gap_action", "risk_note"],
                "properties": {
                    "clause_id": {"type": "string"},
                    "status": {"type": "string", "enum": ["answered", "partial", "gap", "not_applicable"]},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                    "relevance": {"type": "string"},
                    "gap_action": {"type": "string"},
                    "risk_note": {"type": "string"},
                },
            },
        }
    },
}

JUDGE_SYSTEM = """You assess a supplier's evidence against tender clauses for a government bid.
For each clause, decide using ONLY the candidate evidence records listed under it:
- answered: the records fully satisfy the clause.
- partial: the records satisfy part of it, or only indirectly.
- gap: nothing listed satisfies it.
- not_applicable: the clause asks nothing of the bidder (explain why in risk_note).
evidence_ids must be ids from that clause's candidate list; never invent ids. Do not assume facts that are not in
the records. relevance: one sentence on how the records answer the clause. gap_action: what the supplier must
provide to close the gap (empty if answered). risk_note: anything the reviewer should check (may be empty).
Return one judgement per clause id."""


def model_judgements(model: BaseModel, tier: str, items: list[tuple[dict, list]]) -> dict[str, Judgement]:
    out: dict[str, Judgement] = {}
    for start in range(0, len(items), BATCH):
        batch = items[start:start + BATCH]
        payload = []
        allowed: dict[str, dict[str, Record]] = {}
        for clause, cands in batch:
            allowed[clause["id"]] = {r.id: r for r, _, _ in cands}
            payload.append({"clause_id": clause["id"], "category": clause["category"],
                            "mandatory": clause["mandatory"], "text": clause["text"],
                            "candidates": [r.brief(800) for r, _, _ in cands]})
        try:
            result = model.json(task="matrix_judgement", system=JUDGE_SYSTEM, tier=tier, schema=JUDGE_SCHEMA,
                                user=json.dumps({"clauses": payload}, ensure_ascii=False), max_tokens=6000)
        except ModelError as exc:
            print(f"warning: model judgement failed, using rules for this batch: {exc}")
            continue
        for item in result.get("judgements", []):
            cid = item.get("clause_id")
            if cid not in allowed:
                continue
            ev = [(allowed[cid][e], item.get("relevance", "")) for e in item.get("evidence_ids", []) if e in allowed[cid]]
            status = item.get("status", "gap")
            risk = item.get("risk_note", "")
            invented = [e for e in item.get("evidence_ids", []) if e not in allowed[cid]]
            if invented:
                risk = (risk + "; " if risk else "") + f"model cited unknown records {', '.join(invented)} (dropped)"
            if status == "answered" and not ev:
                status = "partial"
                risk = (risk + "; " if risk else "") + "model said answered without valid evidence"
            if status == "not_applicable" and not risk:
                status = "gap"
            out[cid] = Judgement(status, ev, risk, item.get("gap_action", ""), source="model")
    return out


# ---------------------------------------------------------------- build

def _gap_deadline(deadline: date) -> str:
    return max(date.today(), deadline - timedelta(days=GAP_LEAD_DAYS)).isoformat()


def build_matrix(run_id: str, tender: dict, clauses: list[dict], lib: Library, pricing: dict | None,
                 model: BaseModel | None = None) -> dict:
    deadline_dt = parse_datetime(tender["deadline"])
    if deadline_dt is None:
        raise MatrixError(f"tender deadline is not an ISO date-time: {tender.get('deadline')!r}")
    deadline = deadline_dt.date()
    judgements: dict[str, Judgement] = {}
    candidates: dict[str, list] = {}
    pending: list[tuple[dict, list]] = []
    for c in clauses:
        cands = lib.search(c["text"], k=5, prefer=PREFERRED.get(c["category"], ()))
        candidates[c["id"]] = cands
        j = category_rule(c, pricing) or deterministic_check(c, lib, deadline)
        if j is not None:
            judgements[c["id"]] = j
        elif c.get("kind") != "criterion":
            pending.append((c, cands))
    if model is not None and pending:
        judgements.update(model_judgements(model, tender["data_tier"], [(c, k) for c, k in pending if k]))
    for c, cands in pending:
        if c["id"] not in judgements:
            judgements[c["id"]] = coverage_judgement(c, cands)

    # Expiry of every cited record, against the deadline.
    for cid, j in judgements.items():
        for rec, _ in j.evidence:
            status, note, action = _expiry(rec, deadline)
            if status != "answered":
                j.status = _worse(j.status, status)
                j.risk_note = "; ".join(x for x in (j.risk_note, note) if x)
                j.gap_action = "; ".join(x for x in (j.gap_action, action) if x)

    # Scored criteria rows take the weakest status of the clauses in their category.
    by_cat: dict[str, list[str]] = {}
    for c in clauses:
        if c.get("kind") != "criterion" and c["id"] in judgements:
            by_cat.setdefault(c["category"], []).append(judgements[c["id"]].status)
    for c in clauses:
        if c.get("kind") == "criterion":
            statuses = by_cat.get(c["category"])
            if statuses:
                worst = max(statuses, key=lambda s: _RANK[s])
                judgements[c["id"]] = Judgement(
                    "answered" if worst in ("answered", "not_applicable") else "partial", owner="bid_factory",
                    risk_note=f"Scored criterion; answered by the {SECTION_FOR_CATEGORY.get(c['category'], 'response')} section",
                    source="rule:criterion")
            else:
                judgements[c["id"]] = coverage_judgement(c, candidates[c["id"]])

    rows = []
    for c in clauses:
        j = judgements[c["id"]]
        owner = j.owner
        if j.status in ("answered", "not_applicable") and owner == "client" and j.source != "rule:commercial":
            owner = "bid_factory"
        row: dict[str, Any] = {
            "id": c["id"],
            "source": {"document": c["document"], "location": c["location"]},
            "text": c["text"],
            "category": c["category"],
            "mandatory": bool(c["mandatory"]),
            "scored": bool(c["scored"]),
            "status": j.status,
            "owner": owner,
            "evidence": [],
            "response_section": SECTION_FOR_CATEGORY.get(c["category"], "General"),
            "gap_action": j.gap_action,
            "risk_note": j.risk_note,
            "reviewer_notes": "",
            "judged_by": j.source,
        }
        if c.get("weight") is not None:
            row["weight"] = c["weight"]
        seen = set()
        for rec, relevance in j.evidence:
            if rec.id in seen:
                continue
            seen.add(rec.id)
            ev: dict[str, Any] = {"library_id": rec.id, "relevance": relevance or rec.title}
            if rec.valid_until:
                ev["valid_until"] = rec.valid_until.isoformat()
            row["evidence"].append(ev)
        if j.status in ("gap", "partial", "client_decision"):
            row["gap_deadline"] = _gap_deadline(deadline)
        rows.append(row)

    matrix = {
        "run_id": run_id,
        "tender": {k: tender[k] for k in ("buyer", "reference", "title", "portal", "country", "deadline", "data_tier")},
        "rows": rows,
        "summary": summarise(rows),
    }
    for k in ("evaluation_method", "technical_weight_pct", "commercial_weight_pct", "pass_mark_pct"):
        if tender.get(k) is not None:
            matrix["tender"][k] = tender[k]
    validate(matrix)
    return matrix


_NO_GO = {"eligibility", "legal_registration", "nationalisation", "financial", "local_content"}
_PARTNER = {"past_performance", "certification", "team", "technical_requirement", "security_compliance", "data_residency"}


def summarise(rows: list[dict]) -> dict:
    by_status = {s: 0 for s in ("answered", "partial", "gap", "client_decision", "not_applicable")}
    for r in rows:
        by_status[r["status"]] += 1
    mandatory = [r for r in rows if r["mandatory"]]
    mandatory_gaps = [r for r in mandatory if r["status"] == "gap"]
    available = sum(r.get("weight") or 0 for r in rows if r["scored"] and r["status"] != "not_applicable")
    evidenced = sum((r.get("weight") or 0) * (1.0 if r["status"] == "answered" else 0.5 if r["status"] == "partial" else 0)
                    for r in rows if r["scored"])
    reasons = [f"{r['id']} ({r['category']}): {r['risk_note'] or r['gap_action'] or 'mandatory gap'}" for r in mandatory_gaps]
    if any(r["category"] in _NO_GO for r in mandatory_gaps):
        rec = "no_go"
    elif any(r["category"] in _PARTNER for r in mandatory_gaps):
        rec = "go_with_partner"
    elif mandatory_gaps:
        rec = "no_go"
    else:
        rec = "go"
        reasons = ["no mandatory gaps"]
    return {
        "total": len(rows),
        "mandatory_total": len(mandatory),
        "mandatory_gaps": len(mandatory_gaps),
        "scored_points_available": round(available, 2),
        "scored_points_evidenced": round(evidenced, 2),
        "by_status": by_status,
        "go_no_go": {"recommendation": rec, "reasons": reasons},
    }
