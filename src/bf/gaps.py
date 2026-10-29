"""Gap report, rendered from the compliance matrix. Format follows templates/gap-report.md."""
from __future__ import annotations

import re

from .matrix import _NO_GO, _PARTNER
from .util import first_words, md_cell

_VERDICT = {
    "go": "Go. No mandatory gaps remain open.",
    "no_go": "No-go as things stand. A mandatory requirement the supplier cannot meet by itself is open.",
    "go_with_partner": "Go only with a partner. Mandatory gaps exist that a partner or subcontractor could close.",
}


def _table(header: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "_None._\n"
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    lines += ["| " + " | ".join(md_cell(c) for c in r) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def _expiring(row: dict) -> bool:
    return "expire" in (row.get("risk_note") or "").lower()


def render_gap_report(matrix: dict) -> str:
    t, s, rows = matrix["tender"], matrix["summary"], matrix["rows"]
    gng = s["go_no_go"]
    out = [
        f"# Gap report: {t['buyer']} / {t['reference']}",
        "",
        f"Run: {matrix['run_id']}. Deadline: {t['deadline']}. Data tier: {t['data_tier']}. Portal: {t['portal']}.",
        "",
        "## Verdict",
        "",
        _VERDICT[gng["recommendation"]],
        "",
    ]
    out += [f"- {r}" for r in gng["reasons"]]
    out += [
        "",
        f"Matrix: {s['total']} clauses, {s['mandatory_total']} mandatory, {s['mandatory_gaps']} mandatory gaps open. "
        f"Scored points evidenced: {s['scored_points_evidenced']:g} of {s['scored_points_available']:g}.",
        "",
    ]

    def ref(r: dict) -> str:
        return f"{r['id']} ({r['source']['location']})"

    must_missing = [r for r in rows if r["mandatory"] and r["status"] == "gap" and not _expiring(r)]
    must_expiring = [r for r in rows if r["mandatory"] and r["status"] in ("gap", "partial") and _expiring(r)]
    scored_weak = [r for r in rows if r["scored"] and r["status"] == "partial" and not _expiring(r)]
    decisions = [r for r in rows if r["status"] == "client_decision"]
    nice = [r for r in rows if not r["mandatory"] and r["status"] == "gap"]
    partner = [r for r in must_missing + must_expiring if r["category"] in _PARTNER]
    blockers = [r for r in must_missing if r["category"] in _NO_GO]

    out += ["## 1. Must-have and missing", "", "Failure here disqualifies. Each item needs an owner and a date before drafting continues.", ""]
    out.append(_table(["Clause", "Requirement", "Why we fail today", "Action", "Owner", "Needed by"],
                      [[ref(r), first_words(r["text"], 120), r["risk_note"] or "no evidence in the library",
                        r["gap_action"], r["owner"], r.get("gap_deadline", "")] for r in must_missing]))
    out += ["## 2. Must-have and expiring", "", "Valid today or recently, invalid at submission or soon after.", ""]
    out.append(_table(["Clause", "Item", "Problem", "Action", "Owner", "Needed by"],
                      [[ref(r), first_words(r["text"], 100), r["risk_note"], r["gap_action"], r["owner"],
                        r.get("gap_deadline", "")] for r in must_expiring]))
    out += ["## 3. Scored and weak", "", "We can answer, but the evidence is thin and points will be lost.", ""]
    out.append(_table(["Clause", "Points", "What we have", "Action", "Owner"],
                      [[ref(r), f"{r.get('weight', '')}", ", ".join(e["library_id"] for e in r["evidence"]) or "nothing direct",
                        r["gap_action"], r["owner"]] for r in scored_weak]))
    out += ["## 4. Client decisions", "", "Commercial or legal choices only the client can make.", ""]
    out.append(_table(["Clause", "Decision needed", "Note", "Decide by"],
                      [[ref(r), r["gap_action"], r["risk_note"], r.get("gap_deadline", "")] for r in decisions]))
    out += ["## 5. Nice to have", ""]
    out += [f"- {ref(r)}: {first_words(r['text'], 120)}. {r['gap_action']}" for r in nice] or ["_None._"]
    out += ["", "## 6. Partner or subcontractor needs", ""]
    out.append(_table(["Clause", "Capability", "Why"],
                      [[ref(r), r["category"].replace("_", " "), r["risk_note"] or r["gap_action"]] for r in partner]))
    if blockers:
        out += ["Mandatory gaps a partner cannot usually close for the bidder:", ""]
        out += [f"- {ref(r)}: {r['risk_note'] or r['gap_action']}" for r in blockers]
        out.append("")
    out += ["## 7. Local content, nationalisation and residency", ""]
    lc = [r for r in rows if r["category"] in ("local_content", "nationalisation", "data_residency")]
    out += [f"- {ref(r)} [{r['status']}]: {first_words(r['text'], 140)}" + (f" Note: {r['risk_note']}" if r["risk_note"] else "")
            for r in lc] or ["_None found in the tender._"]
    out += ["", "## 8. Submission mechanics", ""]
    sub = [r for r in rows if r["category"] == "submission_format" or re.search(r"\b(bid|performance|tender) bond|bank guarantee|bid security\b", r["text"], re.I)]
    out += [f"- {ref(r)}: {first_words(r['text'], 160)}" for r in sub] or ["_None found in the tender._"]
    out.append("")
    return "\n".join(out)
