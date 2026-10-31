"""Evidence-bound drafting. Every factual sentence cites a library record as [LIB:<id>], or the pricing sheet as
[PRICING]. Anything without evidence becomes [CLIENT INPUT NEEDED: ...]. Citations to records not supplied for
the section are replaced with [INVALID CITATION: <id>] and reported.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .library import Library, Record
from .models import BaseModel, ModelError
from .sections import SECTIONS
from .util import first_words, write_json

CITATION = re.compile(r"\[LIB:([A-Za-z0-9_.\-]+)\]")
PRICING_TAG = "[PRICING]"
TAGS = re.compile(r"\[(CLIENT INPUT NEEDED|CLIENT DECISION NEEDED|INVALID CITATION)[^\]]*\]")
SKIP_STATUSES = {"not_applicable"}
SKIP_CATEGORIES = {"submission_format"}


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+(?=[A-Z(])", text.strip()) if s.strip()]


def cite(sentence: str, rid: str) -> str:
    s = sentence.rstrip()
    if s and s[-1] in ".!?":
        return f"{s[:-1]} [LIB:{rid}]{s[-1]}"
    return f"{s} [LIB:{rid}]."


def cited_summary(rec: Record) -> str:
    return " ".join(cite(s, rec.id) for s in _sentences(rec.summary))


def _fmt_amount(value: Any) -> str:
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{v:,.0f}" if v.is_integer() else f"{v:,.2f}"


def pricing_block(pricing: dict | None) -> list[str]:
    if not pricing:
        return ["[CLIENT INPUT NEEDED: pricing sheet for this bid]"]
    cur = pricing.get("currency", "")
    lines = ["| Item | Amount (" + cur + ") |", "|---|---|"]
    for item in pricing.get("items", []):
        lines.append(f"| {item.get('item', '')} | {_fmt_amount(item.get('amount'))} |")
    if pricing.get("total") is not None:
        lines.append(f"| Total | {_fmt_amount(pricing['total'])} |")
    lines.append("")
    terms = []
    if pricing.get("vat_inclusive") is not None:
        terms.append("Prices are inclusive of VAT" if pricing["vat_inclusive"] else "Prices are exclusive of VAT")
    if pricing.get("validity_days"):
        terms.append(f"prices remain valid for {pricing['validity_days']} days from the submission deadline")
    if pricing.get("payment_terms"):
        terms.append(f"payment terms are {pricing['payment_terms']}")
    if terms:
        lines.append("; ".join(terms) + f" {PRICING_TAG}.")
    return lines


FIGURE_PHRASE = re.compile(r"^(has|reports|is|holds) ")


def bidder_name(lib: Library) -> str:
    for rec in lib.by_type("company"):
        name = rec.figures.get("legal_name")
        if name:
            return str(name)
    return "The bidder"


def _row_block(row: dict, lib: Library, pricing: dict | None, section_key: str,
               used: set[str] | None = None) -> list[str]:
    used = set() if used is None else used
    out = [f"### {row['id']}: {first_words(row['text'], 90)}", "", f"> {row['text']}", ""]
    status = row["status"]
    if status in ("answered", "partial"):
        for ev in row["evidence"]:
            rec = lib.get(ev["library_id"])
            if not rec:
                continue
            relevance = ev.get("relevance", "")
            if FIGURE_PHRASE.match(relevance):
                out.append(cite(f"{bidder_name(lib)} {relevance}.", rec.id))
            elif rec.id in used:
                out.append(cite(f"See {rec.title} above.", rec.id))
            else:
                out.append(cited_summary(rec))
                used.add(rec.id)
        if section_key == "commercial" and row["category"] == "commercial":
            out.append("The pricing for this requirement is set out in the commercial table below " + PRICING_TAG + ".")
    if status == "partial":
        out.append(f"[CLIENT INPUT NEEDED: {row['gap_action'] or row['risk_note'] or 'strengthen the evidence'}]")
    elif status == "gap":
        out.append(f"[CLIENT INPUT NEEDED: {row['gap_action'] or 'evidence for this requirement'}]")
    elif status == "client_decision":
        out.append(f"[CLIENT DECISION NEEDED: {row['gap_action']}]")
    out.append("")
    return out


def _intro_records(lib: Library, key: str) -> list[Record]:
    if key == "company":
        return lib.by_type("company")[:1]
    return [r for r in lib.by_type("boilerplate", "product") if key in r.tags][:1]


def rules_section(key: str, title: str, rows: list[dict], lib: Library, pricing: dict | None) -> str:
    out = [f"## {title}", ""]
    used: set[str] = set()
    for rec in _intro_records(lib, key):
        out += [cited_summary(rec), ""]
        used.add(rec.id)
    for row in rows:
        out += _row_block(row, lib, pricing, key, used)
    if key == "commercial":
        out += ["### Pricing", ""] + pricing_block(pricing) + [""]
    return "\n".join(out).rstrip() + "\n"


DRAFT_SYSTEM = """You draft one section of a tender response for a supplier bidding on a government tender.
Rules, all mandatory:
1. Use only facts found in the evidence records provided. Never invent names, numbers, dates, certifications,
   clients, staff, prices or capabilities.
2. Every sentence that states a fact about the supplier ends with a citation [LIB:<record id>] placed before the
   closing punctuation, for example: "We run a bilingual service desk 24 hours a day [LIB:BP-002]."
   Cite only record ids listed in the evidence for this section.
3. Where the evidence does not cover what a requirement asks, write [CLIENT INPUT NEEDED: <what is missing>].
   Where a requirement needs a commercial or legal decision, write [CLIENT DECISION NEEDED: <decision>].
4. In the commercial section use only figures from the pricing sheet and cite them as [PRICING].
5. For each requirement write a subheading "### <requirement id>: <short title>", quote the requirement on the
   next line starting with "> ", then answer it directly and specifically.
6. Formal British English. Markdown only. Start with "## <section title>". No preamble, no closing remarks."""


def validate_citations(text: str, allowed: set[str]) -> tuple[str, list[str]]:
    invalid: list[str] = []

    def repl(m: re.Match) -> str:
        rid = m.group(1)
        if rid in allowed:
            return m.group(0)
        invalid.append(rid)
        return f"[INVALID CITATION: {rid}]"

    return CITATION.sub(repl, text), invalid


def model_section(model: BaseModel, tier: str, tender: dict, key: str, title: str, rows: list[dict],
                  lib: Library, pricing: dict | None) -> tuple[str, list[str]]:
    evidence: dict[str, Record] = {}
    for rec in _intro_records(lib, key):
        evidence[rec.id] = rec
    for row in rows:
        for ev in row["evidence"]:
            rec = lib.get(ev["library_id"])
            if rec:
                evidence[rec.id] = rec
    payload = {
        "tender": {k: tender.get(k) for k in ("buyer", "title", "reference")},
        "section_title": title,
        "requirements": [{"id": r["id"], "text": r["text"], "status": r["status"],
                          "gap_action": r["gap_action"], "risk_note": r["risk_note"]} for r in rows],
        "evidence": [r.brief(1500) for r in evidence.values()],
    }
    if key == "commercial":
        payload["pricing_sheet"] = pricing
    text = model.text(task=f"draft_{key}", system=DRAFT_SYSTEM, tier=tier,
                      user=json.dumps(payload, ensure_ascii=False), max_tokens=8000)
    text, invalid = validate_citations(text, set(evidence))
    if not text.lstrip().startswith("## "):
        text = f"## {title}\n\n{text}"
    for row in rows:  # no requirement may be silently dropped
        if not re.search(rf"^###\s+{re.escape(row['id'])}\b", text, re.M):
            text = text.rstrip() + "\n\n" + "\n".join(_row_block(row, lib, pricing, key))
    if key == "commercial" and pricing and "| Item |" not in text:
        text = text.rstrip() + "\n\n### Pricing\n\n" + "\n".join(pricing_block(pricing)) + "\n"
    return text.rstrip() + "\n", invalid


def draft_all(out_dir: str | Path, matrix: dict, lib: Library, pricing: dict | None,
              model: BaseModel | None = None) -> dict:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tier = matrix["tender"]["data_tier"]
    rows_by_section: dict[str, list[dict]] = {}
    for row in matrix["rows"]:
        if row["status"] in SKIP_STATUSES or row["category"] in SKIP_CATEGORIES:
            continue
        if row.get("judged_by") == "rule:criterion":
            continue
        rows_by_section.setdefault(row["response_section"], []).append(row)
    index: dict[str, Any] = {"sections": [], "drafted_by": model.provider if model else "rules"}
    n = 0
    for key, title, _ in SECTIONS:
        rows = rows_by_section.get(title, [])
        if not rows:
            continue
        n += 1
        invalid: list[str] = []
        if model is not None:
            try:
                text, invalid = model_section(model, tier, matrix["tender"], key, title, rows, lib, pricing)
            except ModelError as exc:
                print(f"warning: model drafting failed for {title}, using rules: {exc}")
                text = rules_section(key, title, rows, lib, pricing)
        else:
            text = rules_section(key, title, rows, lib, pricing)
        name = f"{n:02d}-{key}.md"
        (out_dir / name).write_text(text, encoding="utf-8")
        index["sections"].append({
            "key": key, "title": title, "file": name, "rows": [r["id"] for r in rows],
            "citations": sorted(set(CITATION.findall(text))), "invalid_citations": invalid,
            "placeholders": len(TAGS.findall(text)),
        })
    write_json(out_dir / "index.json", index)
    return index
