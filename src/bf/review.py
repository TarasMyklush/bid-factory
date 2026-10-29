"""Automated review before the human gate. Mirrors templates/review-checklist.md sections A to F.

Blocking findings stop delivery. Advisory findings go to the human reviewer. Client actions are the open
placeholders the client must resolve. The human still reads and signs the checklist.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .draft import CITATION, PRICING_TAG, TAGS
from .library import Library
from .matrix import _norm_std, _std_keys
from .models import BaseModel, ModelError
from .util import numbers_in, parse_datetime, write_json

FACT = re.compile(
    r"\d|\b(certified|certification|accredit\w*|awards?|years?|clients?|projects?|guarantee\w*|uptime|iso|itil|"
    r"nca|staff|employees|offices?|partners?|licensed|registered)\b", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<![\w-])\+?\d[\d\s()-]{8,}\d(?![\w-])")
REQ_ID = re.compile(r"\bC-\d{3,}\b")
VALID_STATUSES = {"answered", "partial", "gap", "client_decision", "not_applicable"}


@dataclass
class Finding:
    code: str
    severity: str  # blocking | advisory | client_action
    where: str
    message: str


def _prose_lines(text: str) -> list[tuple[int, str]]:
    """Lines that carry claims: not headings, not quoted requirement text, not table rows."""
    out = []
    for n, line in enumerate(text.splitlines(), start=1):
        s = line.strip()
        if not s or s.startswith(("#", ">", "|")):
            continue
        out.append((n, re.sub(r"^[-*]\s+(\[ \]\s*)?", "", s)))
    return out


def _sentences(line: str) -> list[str]:
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+", line) if p.strip()]
    merged: list[str] = []
    for p in parts:
        if merged and re.fullmatch(r"(\[[^\]]+\]\s*)+[.!?]?", p):
            merged[-1] += " " + p
        else:
            merged.append(p)
    return merged


def _strip_markup(text: str) -> str:
    text = TAGS.sub(" ", text)
    text = CITATION.sub(" ", text)
    text = text.replace(PRICING_TAG, " ")
    return REQ_ID.sub(" ", text)


def _pricing_numbers(pricing: Any) -> set[float]:
    found: set[float] = set()
    if isinstance(pricing, dict):
        for v in pricing.values():
            found |= _pricing_numbers(v)
    elif isinstance(pricing, list):
        for v in pricing:
            found |= _pricing_numbers(v)
    elif isinstance(pricing, bool):
        pass
    elif isinstance(pricing, (int, float)):
        found.add(float(pricing))
    elif isinstance(pricing, str):
        found |= set(numbers_in(pricing))
    return found


def review(matrix: dict, clauses: list[dict], lib: Library, sections_dir: str | Path, index: dict,
           pricing: dict | None, model_log: str | Path | None = None, model: BaseModel | None = None) -> dict:
    sections_dir = Path(sections_dir)
    findings: list[Finding] = []
    deadline = (parse_datetime(matrix["tender"]["deadline"]) or None)
    deadline_d: date | None = deadline.date() if deadline else None
    tier = matrix["tender"]["data_tier"]

    # A. Matrix
    row_ids = {r["id"] for r in matrix["rows"]}
    for c in clauses:
        if c["id"] not in row_ids:
            findings.append(Finding("A1", "blocking", c["id"], "extracted clause missing from the matrix"))
    for r in matrix["rows"]:
        if r["status"] not in VALID_STATUSES:
            findings.append(Finding("A1", "blocking", r["id"], f"invalid status {r['status']}"))
        if r["mandatory"] and r["status"] == "gap":
            findings.append(Finding("A2", "blocking", r["id"],
                                    f"mandatory gap: {r['risk_note'] or r['gap_action'] or r['text'][:100]}"))

    # B, C. Sections
    texts: dict[str, str] = {}
    for sec in index["sections"]:
        texts[sec["file"]] = (sections_dir / sec["file"]).read_text(encoding="utf-8")
    pricing_nums = _pricing_numbers(pricing) if pricing else set()
    for file, text in texts.items():
        for rid in CITATION.findall(text):
            rec = lib.get(rid)
            if rec is None:
                findings.append(Finding("B1", "blocking", file, f"citation to unknown record {rid}"))
            elif rec.type == "project" and rec.permission == "no":
                findings.append(Finding("B4", "blocking", file, f"{rid} is not permitted to be cited"))
            elif rec.type == "project" and rec.permission == "on_request":
                findings.append(Finding("B4", "advisory", file, f"{rid} may be cited only with the client's approval for this bid"))
            elif rec.valid_until and deadline_d and rec.valid_until < deadline_d:
                findings.append(Finding("B3", "blocking", file, f"{rid} is cited but expires {rec.valid_until}, before the deadline"))
        for m in re.finditer(r"\[INVALID CITATION: ([^\]]+)\]", text):
            findings.append(Finding("B1", "blocking", file, f"draft cited a record not supplied for this section: {m.group(1)}"))
        for n, line in _prose_lines(text):
            for sent in _sentences(line):
                if CITATION.search(sent) or PRICING_TAG in sent or TAGS.search(sent):
                    continue
                if FACT.search(sent):
                    findings.append(Finding("B2", "blocking", f"{file}:{n}", f"unsupported claim: {sent[:160]}"))
            plain = _strip_markup(line)
            for key, label in _std_keys(plain):
                certs = [r for r in lib.by_type("certification") if key in _norm_std(r.corpus())]
                valid = [r for r in certs if not (r.valid_until and deadline_d and r.valid_until < deadline_d)]
                if not valid:
                    findings.append(Finding("B3", "blocking", f"{file}:{n}",
                                            f"draft names {label} but the library has no certificate valid at the deadline"))
        if EMAIL.search(text) or PHONE.search(text):
            findings.append(Finding("B5", "blocking", file, "personal contact details found in the draft"))
        if file.endswith("-commercial.md") and pricing_nums:
            for n, line in enumerate(text.splitlines(), start=1):
                s = line.strip()
                if not s or s.startswith(("#", ">")):
                    continue
                for value in numbers_in(_strip_markup(s)):
                    if not any(abs(value - p) < 0.005 for p in pricing_nums):
                        findings.append(Finding("C1", "blocking", f"{file}:{n}",
                                                f"number {int(value) if value.is_integer() else value} does not appear in the pricing sheet"))
        for m in TAGS.finditer(text):
            if not m.group(0).startswith("[INVALID"):
                findings.append(Finding("D2", "client_action", file, m.group(0)))

    # D. Forms
    for r in matrix["rows"]:
        if r["category"] == "form" and r["status"] in ("gap", "partial"):
            findings.append(Finding("D1", "advisory", r["id"], r["gap_action"] or "form incomplete"))

    # F. Data handling: no non-resident provider may have seen Tier B material.
    if model_log and Path(model_log).exists():
        for line in Path(model_log).read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if entry.get("tier") in ("B", "C") and entry.get("provider") == "anthropic":
                findings.append(Finding("F1", "blocking", entry.get("task", "?"),
                                        f"Tier {entry['tier']} material was sent to a non-resident model"))

    # Optional second pass by a model, advisory only.
    if model is not None:
        findings += _model_pass(model, tier, texts, lib, pricing)

    blocking = [f for f in findings if f.severity == "blocking"]
    return {
        "result": "blocked" if blocking else "ready_for_human_review",
        "counts": {s: sum(1 for f in findings if f.severity == s) for s in ("blocking", "advisory", "client_action")},
        "unsupported_claims": sum(1 for f in findings if f.code == "B2"),
        "findings": [asdict(f) for f in findings],
    }


REVIEW_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["findings"],
    "properties": {"findings": {"type": "array", "items": {
        "type": "object", "additionalProperties": False, "required": ["quote", "problem"],
        "properties": {"quote": {"type": "string"}, "problem": {"type": "string"}}}}},
}
REVIEW_SYSTEM = """You review one section of a tender response before a human reviewer sees it.
Report only real problems: a sentence whose claim is not supported by the cited evidence record, a contradiction
with another statement, a number that is not in the pricing sheet, or an answer that does not address the quoted
requirement. Quote the exact sentence. Do not report style. Return an empty list if there are no problems."""


def _model_pass(model: BaseModel, tier: str, texts: dict[str, str], lib: Library, pricing: dict | None) -> list[Finding]:
    out: list[Finding] = []
    for file, text in texts.items():
        ids = sorted(set(CITATION.findall(text)))
        payload = {"section": text, "evidence": [lib.get(i).brief(800) for i in ids if lib.get(i)]}
        if file.endswith("-commercial.md"):
            payload["pricing_sheet"] = pricing
        try:
            res = model.json(task="review_section", system=REVIEW_SYSTEM, tier=tier, schema=REVIEW_SCHEMA,
                             user=json.dumps(payload, ensure_ascii=False), max_tokens=3000)
        except ModelError as exc:
            out.append(Finding("M0", "advisory", file, f"model review pass failed: {exc}"))
            continue
        for f in res.get("findings", []):
            out.append(Finding("M1", "advisory", file, f"{f.get('problem', '')}: {f.get('quote', '')[:160]}"))
    return out


def render_findings(result: dict, matrix: dict) -> str:
    t = matrix["tender"]
    c = result["counts"]
    head = "BLOCKED" if result["result"] == "blocked" else "READY FOR HUMAN REVIEW"
    out = [f"# Review findings: {t['reference']}", "",
           f"Result: **{head}**. Blocking: {c['blocking']}. Advisory: {c['advisory']}. Client actions: {c['client_action']}.",
           "", "Automated checks only. The human reviewer still completes and signs templates/review-checklist.md.", ""]
    for sev, title in (("blocking", "Blocking"), ("advisory", "Advisory"), ("client_action", "Client actions")):
        items = [f for f in result["findings"] if f["severity"] == sev]
        out += [f"## {title}", ""]
        out += [f"- [{f['code']}] {f['where']}: {f['message']}" for f in items] or ["_None._"]
        out.append("")
    return "\n".join(out)


def write_review(run_dir: str | Path, result: dict, matrix: dict) -> None:
    run_dir = Path(run_dir)
    write_json(run_dir / "review.json", result)
    (run_dir / "review-findings.md").write_text(render_findings(result, matrix), encoding="utf-8")
