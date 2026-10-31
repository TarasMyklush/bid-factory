"""Pack assembly: submission checklist, compliance matrix, technical and commercial responses, annex index.

A pack with open mandatory gaps is still built, but every file carries a NOT FOR SUBMISSION banner and the
manifest marks it undeliverable.
"""
from __future__ import annotations

import csv
import re
from datetime import timedelta, timezone
from pathlib import Path
from typing import Any

from .draft import CITATION, TAGS
from .library import Library
from .util import first_words, md_cell, now_iso, parse_datetime, write_json

BUYER_TZ = {"SA": (timezone(timedelta(hours=3)), "Riyadh time, UTC+3"),
            "AE": (timezone(timedelta(hours=4)), "UAE time, UTC+4")}
BANNER = "**NOT FOR SUBMISSION: mandatory gaps are open. See the gap report.**"


def _ref(reference: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", reference).strip("-") or "tender"


def local_deadline(deadline: str, country: str) -> str:
    dt = parse_datetime(deadline)
    if dt is None:
        return deadline
    tz, label = BUYER_TZ.get(country, (timezone.utc, "UTC"))
    return f"{dt.astimezone(tz):%A %d %B %Y, %H:%M} ({label})"


def md_to_docx(markdown: str, path: Path, banner: bool) -> bool:
    try:
        import docx
    except ImportError:  # pragma: no cover
        return False
    doc = docx.Document()
    if banner:
        doc.add_paragraph().add_run(BANNER.strip("*")).bold = True
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("|"):
            block = []
            while i < len(lines) and lines[i].startswith("|"):
                if not re.match(r"^\|\s*:?-{2,}", lines[i]):
                    block.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            if block:
                table = doc.add_table(rows=len(block), cols=max(len(r) for r in block))
                table.style = "Table Grid"
                for r, cells in enumerate(block):
                    for c, value in enumerate(cells):
                        table.cell(r, c).text = value
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            doc.add_heading(m.group(2), level=min(len(m.group(1)), 4))
        elif line.startswith("> "):
            doc.add_paragraph(line[2:], style="Quote")
        elif re.match(r"^\s*[-*]\s+", line):
            doc.add_paragraph(re.sub(r"^\s*[-*]\s+(\[ \]\s*)?", "", line), style="List Bullet")
        elif line.strip():
            doc.add_paragraph(line.replace("**", ""))
        i += 1
    doc.save(str(path))
    return True


def _matrix_csv(matrix: dict, path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "location", "category", "mandatory", "scored", "weight", "status", "owner",
                    "evidence", "response_section", "gap_action", "gap_deadline", "risk_note", "text"])
        for r in matrix["rows"]:
            w.writerow([r["id"], r["source"]["location"], r["category"], r["mandatory"], r["scored"],
                        r.get("weight", ""), r["status"], r["owner"],
                        " ".join(e["library_id"] for e in r["evidence"]), r["response_section"],
                        r["gap_action"], r.get("gap_deadline", ""), r["risk_note"], r["text"]])


def _matrix_md(matrix: dict, banner: bool) -> str:
    t, s = matrix["tender"], matrix["summary"]
    out = [BANNER, ""] if banner else []
    out += [f"# Compliance matrix: {t['title']}", "",
            f"{t['buyer']}, {t['reference']}. {s['total']} clauses, {s['mandatory_total']} mandatory, "
            f"{s['mandatory_gaps']} mandatory gaps.", "",
            "| ID | Location | Requirement | M | Status | Evidence | Response |", "|---|---|---|---|---|---|---|"]
    for r in matrix["rows"]:
        out.append("| " + " | ".join([
            r["id"], md_cell(r["source"]["location"]), md_cell(first_words(r["text"], 140)),
            "yes" if r["mandatory"] else "", r["status"],
            md_cell(" ".join(e["library_id"] for e in r["evidence"])), md_cell(r["response_section"]),
        ]) + " |")
    return "\n".join(out) + "\n"


def _checklist(matrix: dict, lib: Library, sections_text: str, banner: bool) -> str:
    t, s, rows = matrix["tender"], matrix["summary"], matrix["rows"]
    out = [BANNER, ""] if banner else []
    out += [f"# Submission checklist: {t['title']}", "",
            f"- Buyer: {t['buyer']}", f"- Reference: {t['reference']}", f"- Portal: {t['portal']}",
            f"- Deadline: {local_deadline(t['deadline'], t['country'])}", f"- Data tier: {t['data_tier']}", "",
            "## Before submission", "",
            f"- [ ] Every mandatory gap closed ({s['mandatory_gaps']} open now)",
            f"- [ ] Every placeholder resolved ({len(TAGS.findall(sections_text))} in the draft)",
            "- [ ] The client's named signatory has approved every claim in the response",
            "- [ ] Human review checklist signed (templates/review-checklist.md)"]
    for r in rows:
        if r["category"] == "submission_format":
            out.append(f"- [ ] {r['id']}: {first_words(r['text'], 160)}")
    for r in rows:
        if re.search(r"\b(bid bond|performance bond|bank guarantee|bid security|tender bond)\b", r["text"], re.I):
            out.append(f"- [ ] {r['id']}: bond or guarantee: {first_words(r['text'], 140)}")
    for r in rows:
        if r["category"] == "form":
            out.append(f"- [ ] {r['id']}: forms signed and stamped: {first_words(r['text'], 140)}")
    if any("separately" in r["text"].lower() for r in rows if r["category"] == "commercial"):
        out.append("- [ ] Commercial proposal submitted separately, as the tender requires")
    out += ["", "## Attach from the client's tenant", "",
            "These are referenced by id. Their content never passed through this toolkit.", ""]
    for item in lib.attach_at_submission:
        out.append(f"- [ ] {item['id']}: {item['title']}")
    cited = sorted(set(CITATION.findall(sections_text)))
    for rid in cited:
        rec = lib.get(rid)
        if rec and rec.type in ("person", "certification", "registration", "financial", "form"):
            what = "CV original" if rec.type == "person" else "signed or certified copy"
            out.append(f"- [ ] {rid}: {what} of {rec.title}" + (f" (source: {rec.source})" if rec.source else ""))
    out += ["", "## Submission record", "", "- Submitted at:", "- Confirmation number:", "- Submitted by:", ""]
    return "\n".join(out)


def _annex_index(sections_text: str, lib: Library, banner: bool) -> str:
    out = [BANNER, ""] if banner else []
    out += ["# Annex index", "", "Library records cited in the response, by id. Source files stay in the client's tenant.", "",
            "| ID | Type | Title | Valid until | Source |", "|---|---|---|---|---|"]
    for rid in sorted(set(CITATION.findall(sections_text))):
        rec = lib.get(rid)
        if rec:
            out.append(f"| {rid} | {rec.type} | {md_cell(rec.title)} | {rec.valid_until or ''} | {md_cell(rec.source or '')} |")
    return "\n".join(out) + "\n"


def build_pack(out_dir: str | Path, matrix: dict, lib: Library, sections_dir: str | Path, index: dict) -> dict[str, Any]:
    out_dir, sections_dir = Path(out_dir), Path(sections_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    t = matrix["tender"]
    deliverable = matrix["summary"]["mandatory_gaps"] == 0
    banner = not deliverable
    ref = _ref(t["reference"])
    technical, commercial = [], []
    for sec in index["sections"]:
        text = (sections_dir / sec["file"]).read_text(encoding="utf-8")
        (commercial if sec["key"] == "commercial" else technical).append(text)
    all_text = "\n".join(technical + commercial)
    files: dict[str, str] = {}

    def put(name: str, content: str) -> None:
        (out_dir / name).write_text(content, encoding="utf-8")
        files[name] = "md" if name.endswith(".md") else name.rsplit(".", 1)[-1]

    put(f"{ref}_00_submission-checklist.md", _checklist(matrix, lib, all_text, banner))
    put(f"{ref}_01_compliance-matrix.md", _matrix_md(matrix, banner))
    _matrix_csv(matrix, out_dir / f"{ref}_01_compliance-matrix.csv")
    files[f"{ref}_01_compliance-matrix.csv"] = "csv"
    head = ([BANNER, ""] if banner else []) + [f"# {t['title']}", "", f"Response to {t['buyer']}, tender {t['reference']}.", ""]
    tech_md = "\n".join(head + ["# Technical response", ""] + technical)
    put(f"{ref}_02_technical-response.md", tech_md)
    if md_to_docx(tech_md, out_dir / f"{ref}_02_technical-response.docx", banner):
        files[f"{ref}_02_technical-response.docx"] = "docx"
    if commercial:
        com_md = "\n".join(head + ["# Commercial response", ""] + commercial)
        put(f"{ref}_03_commercial-response.md", com_md)
        if md_to_docx(com_md, out_dir / f"{ref}_03_commercial-response.docx", banner):
            files[f"{ref}_03_commercial-response.docx"] = "docx"
    put(f"{ref}_04_annex-index.md", _annex_index(all_text, lib, banner))
    manifest = {"generated_at": now_iso(), "deliverable": deliverable,
                "mandatory_gaps": matrix["summary"]["mandatory_gaps"], "files": sorted(files)}
    write_json(out_dir / "pack-manifest.json", manifest)
    return manifest
