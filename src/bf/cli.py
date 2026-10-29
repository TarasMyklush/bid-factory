"""bf: the Bid Factory command line. See SPEC.md section 6.

    bf intake  <tender-dir> --library DIR --client ID   -> runs/<run-id>/run.json
    bf extract <run>                                    -> clauses.json
    bf matrix  <run>                                    -> matrix.json
    bf gaps    <run>                                    -> gap-report.md
    bf draft   <run>                                    -> sections/*.md
    bf pack    <run>                                    -> pack/
    bf review  <run>                                    -> review-findings.md (exit 1 if blocking findings)
    bf log     <run> --outcome ...                      -> appends to the outcome log
    bf close   <run> --deliver-to DIR                   -> copies deliverables, deletes the workspace
    bf run     <tender-dir> --library DIR --client ID   -> intake through review in one go
"""
from __future__ import annotations

import argparse
import shutil
import sys
from datetime import date
from pathlib import Path

from . import __version__
from .documents import DocumentError, load_document, tender_files
from .draft import draft_all
from .extract import clauses_to_json, extract_clauses
from .gaps import render_gap_report
from .library import Library, LibraryError
from .matrix import MatrixError, build_matrix
from .models import CHOICES, ModelError, TierViolation, select_model
from .outcome import OUTCOMES, append_or_update, build_row, load_review
from .pack import build_pack
from .review import review, write_review
from .runs import Run, RunError
from .tiers import TierError, classify
from .util import now_iso, parse_datetime, read_json, sha256_file, sha256_text, slug, write_json

PORTALS = ("etimad", "uae_federal_dpp", "dubai_esupply", "abu_dhabi", "semi_government", "private", "other")
COUNTRIES = ("SA", "AE", "other")
META_FIELDS = ("buyer", "reference", "title", "portal", "country", "deadline")


def _pricing(run: Run) -> dict | None:
    p = run.data.get("pricing_path")
    return read_json(p) if p and Path(p).exists() else None


def _model(run: Run, choice: str):
    model = select_model(choice, run.tier, run.model_log)
    label = model.provider if model else "rules"
    if choice == "auto" and model is None:
        print("note: no model configured for this tier; running on deterministic rules", file=sys.stderr)
    return model, label


# ---------------------------------------------------------------- commands

def cmd_intake(a: argparse.Namespace) -> int:
    tender_dir = Path(a.tender_dir).resolve()
    meta_path = tender_dir / "tender.json"
    meta = read_json(meta_path) if meta_path.exists() else {}
    for key in META_FIELDS:
        value = getattr(a, key, None)
        if value:
            meta[key] = value
    missing = [k for k in META_FIELDS if not meta.get(k)]
    if missing:
        raise RunError(f"tender metadata missing: {', '.join(missing)} (put them in tender.json or pass flags)")
    if meta["portal"] not in PORTALS:
        raise RunError(f"portal must be one of {', '.join(PORTALS)}")
    if meta["country"] not in COUNTRIES:
        raise RunError(f"country must be one of {', '.join(COUNTRIES)}")
    dl = parse_datetime(meta["deadline"])
    if dl is None or dl.tzinfo is None:
        raise RunError("deadline must be an ISO date-time with a UTC offset, e.g. 2026-12-15T13:00:00+03:00")
    meta["deadline"] = dl.isoformat()

    files, skipped = tender_files(tender_dir)
    if not files:
        raise RunError(f"no readable tender documents in {tender_dir}")
    docs = [load_document(p) for p in files]
    text = "\n".join(d.text for d in docs)
    tr = classify(text, declared_public=bool(a.public or meta.get("public") is True), requested=a.tier)

    library_dir = Path(a.library).resolve()
    stamp = now_iso()
    run_id = f"{date.today():%Y%m%d}-{slug(meta['reference'], 24)}-{sha256_text(meta['reference'] + a.client + stamp)[:6]}"
    run_dir = Path(a.runs_dir).resolve() / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    pricing = tender_dir / "pricing.json"
    if not pricing.exists():
        pricing = library_dir / "pricing.json"
    tender = {k: meta[k] for k in META_FIELDS}
    tender["data_tier"] = tr.tier
    for k in ("evaluation_method", "technical_weight_pct", "commercial_weight_pct", "pass_mark_pct"):
        if meta.get(k) is not None:
            tender[k] = meta[k]
    data = {
        "run_id": run_id, "client_id": a.client, "created_at": stamp,
        "buyer_type": meta.get("buyer_type", ""), "category": meta.get("category", a.category or ""),
        "tender_dir": str(tender_dir), "library_dir": str(library_dir),
        "pricing_path": str(pricing) if pricing.exists() else None,
        "tender": tender,
        "tier": {"tier": tr.tier, "detected": tr.detected, "reasons": tr.reasons,
                 "residency_mentions": tr.residency_mentions},
        "inventory": [{"file": p.name, "sha256": sha256_file(p), "pages": len(d.pages), "chars": len(d.text)}
                      for p, d in zip(files, docs)],
        "skipped_files": skipped,
        "stages": {},
    }
    run = Run(run_dir, data)
    a._run_dir = str(run_dir)
    if tr.tier == "C":
        data["status"] = "refused: Tier C, humans only"
        run.save()
        print(f"{run_dir}\nTier C: {'; '.join(tr.reasons)}\nThis tender is handled by humans only. Nothing was processed.")
        return 3
    lib = Library.load(library_dir)
    run.mark("intake", records=len(lib.records), attach_at_submission=len(lib.attach_at_submission))
    print(run_dir)
    print(f"tier {tr.tier} ({'; '.join(tr.reasons)}); {len(files)} document(s); library {len(lib.records)} records")
    for w in skipped:
        print(f"warning: skipped unsupported file {w}", file=sys.stderr)
    return 0


def cmd_extract(a: argparse.Namespace) -> int:
    run = Run.load(a.run)
    run.require("intake")
    run.verify_inventory()
    files = [Path(run.data["tender_dir"]) / i["file"] for i in run.data["inventory"]]
    clauses = extract_clauses([load_document(p) for p in files])
    if not clauses:
        raise RunError("no clauses found; check the tender documents are text, not scanned images")
    write_json(run.path("clauses.json"), clauses_to_json(clauses))
    run.mark("extract", clauses=len(clauses), mandatory=sum(c.mandatory for c in clauses))
    print(f"{len(clauses)} clauses ({sum(c.mandatory for c in clauses)} mandatory) -> {run.path('clauses.json')}")
    return 0


def cmd_matrix(a: argparse.Namespace) -> int:
    run = Run.load(a.run)
    run.require("extract")
    lib = Library.load(run.data["library_dir"])
    model, label = _model(run, a.model)
    clauses = read_json(run.path("clauses.json"))
    matrix = build_matrix(run.id, run.tender, clauses, lib, _pricing(run), model)
    write_json(run.path("matrix.json"), matrix)
    s = matrix["summary"]
    run.mark("matrix", model=label, mandatory_gaps=s["mandatory_gaps"], go_no_go=s["go_no_go"]["recommendation"])
    print(f"matrix: {s['total']} rows, {s['mandatory_gaps']} mandatory gaps, "
          f"recommendation {s['go_no_go']['recommendation']} -> {run.path('matrix.json')}")
    return 0


def cmd_gaps(a: argparse.Namespace) -> int:
    run = Run.load(a.run)
    run.require("matrix")
    report = render_gap_report(read_json(run.path("matrix.json")))
    run.path("gap-report.md").write_text(report, encoding="utf-8")
    run.mark("gaps")
    print(run.path("gap-report.md"))
    return 0


def cmd_draft(a: argparse.Namespace) -> int:
    run = Run.load(a.run)
    run.require("matrix")
    lib = Library.load(run.data["library_dir"])
    model, label = _model(run, a.model)
    index = draft_all(run.path("sections"), read_json(run.path("matrix.json")), lib, _pricing(run), model)
    invalid = sum(len(s["invalid_citations"]) for s in index["sections"])
    run.mark("draft", model=label, sections=len(index["sections"]), invalid_citations=invalid)
    print(f"{len(index['sections'])} sections drafted by {label}; invalid citations replaced: {invalid} -> {run.path('sections')}")
    return 0


def cmd_pack(a: argparse.Namespace) -> int:
    run = Run.load(a.run)
    run.require("draft")
    lib = Library.load(run.data["library_dir"])
    manifest = build_pack(run.path("pack"), read_json(run.path("matrix.json")), lib, run.path("sections"),
                          read_json(run.path("sections") / "index.json"))
    run.mark("pack", deliverable=manifest["deliverable"])
    state = "deliverable" if manifest["deliverable"] else f"NOT FOR SUBMISSION ({manifest['mandatory_gaps']} mandatory gaps)"
    print(f"pack: {len(manifest['files'])} files, {state} -> {run.path('pack')}")
    return 0


def cmd_review(a: argparse.Namespace) -> int:
    run = Run.load(a.run)
    run.require("draft")
    lib = Library.load(run.data["library_dir"])
    model, label = _model(run, a.model) if a.model != "rules" else (None, "rules")
    matrix = read_json(run.path("matrix.json"))
    result = review(matrix, read_json(run.path("clauses.json")), lib, run.path("sections"),
                    read_json(run.path("sections") / "index.json"), _pricing(run), run.model_log, model)
    write_review(run.dir, result, matrix)
    run.mark("review", result=result["result"], **result["counts"])
    c = result["counts"]
    print(f"review: {result['result']}; blocking {c['blocking']}, advisory {c['advisory']}, "
          f"client actions {c['client_action']} -> {run.path('review-findings.md')}")
    return 1 if result["result"] == "blocked" else 0


def cmd_log(a: argparse.Namespace) -> int:
    run = Run.load(a.run)
    run.require("pack")
    fields = {k: getattr(a, k) for k in ("outcome", "buyer_type", "category", "fee_aed", "success_fee_pct",
                                         "human_review_hours", "clarification_rounds", "submitted_on_time",
                                         "contract_value_aed", "buyer_score_pct", "loss_reason",
                                         "debrief_received", "notes", "shortlisted", "awarded")}
    row = build_row(run, read_json(run.path("matrix.json")), load_review(run.dir), fields)
    action = append_or_update(a.log_file, row)
    run.mark("log", outcome=a.outcome, log_file=str(Path(a.log_file).resolve()))
    print(f"outcome log {action}: {run.id} -> {a.log_file}")
    return 0


def cmd_close(a: argparse.Namespace) -> int:
    run = Run.load(a.run)
    if "log" not in run.data.get("stages", {}) and not a.force:
        raise RunError("log the outcome first (bf log), or pass --force")
    dest = Path(a.deliver_to).resolve() / run.id
    dest.mkdir(parents=True, exist_ok=False)
    for name in ("pack", "sections"):
        if run.path(name).exists():
            shutil.copytree(run.path(name), dest / name)
    for name in ("matrix.json", "gap-report.md", "review-findings.md", "review.json"):
        if run.path(name).exists():
            shutil.copy2(run.path(name), dest / name)
    shutil.rmtree(run.dir)
    print(f"delivered to {dest}; workspace {run.dir} deleted")
    return 0


def cmd_run(a: argparse.Namespace) -> int:
    code = cmd_intake(a)
    if code:
        return code
    step = argparse.Namespace(run=a._run_dir, model=a.model)
    for fn in (cmd_extract, cmd_matrix, cmd_gaps, cmd_draft, cmd_pack):
        fn(step)
    return cmd_review(step)


# ---------------------------------------------------------------- parser

def _intake_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("tender_dir", help="directory with the tender documents and an optional tender.json")
    p.add_argument("--library", required=True, help="the client's bid library directory")
    p.add_argument("--client", required=True, help="client id")
    p.add_argument("--runs-dir", default="runs", help="workspace root (default: ./runs)")
    p.add_argument("--public", action="store_true", help="declare the tender public (allows Tier A)")
    p.add_argument("--tier", choices=("A", "B", "C"), help="raise the data tier; it can never be lowered")
    p.add_argument("--category", help="client bid category, e.g. it_software")
    for key in META_FIELDS:
        p.add_argument(f"--{key}", help=f"override tender.json {key}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bf", description="Bid Factory tender response toolkit")
    parser.add_argument("--version", action="version", version=f"bf {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("intake", help="classify the data tier and open a run")
    _intake_args(p)
    p.set_defaults(fn=cmd_intake)

    for name, fn, helptext, uses_model in (
        ("extract", cmd_extract, "extract clauses", False),
        ("matrix", cmd_matrix, "build the compliance matrix", True),
        ("gaps", cmd_gaps, "render the gap report", False),
        ("draft", cmd_draft, "draft the response sections", True),
        ("pack", cmd_pack, "assemble the submission pack", False),
        ("review", cmd_review, "run the automated review", True),
    ):
        p = sub.add_parser(name, help=helptext)
        p.add_argument("run", help="run directory")
        if uses_model:
            p.add_argument("--model", choices=CHOICES, default="auto" if name != "review" else "rules",
                           help="model routing (default: auto; review defaults to rules)")
        p.set_defaults(fn=fn)

    p = sub.add_parser("log", help="record the outcome in the outcome log")
    p.add_argument("run")
    p.add_argument("--outcome", required=True, choices=OUTCOMES)
    p.add_argument("--log-file", default="bid-outcome-log.csv")
    for key in ("buyer_type", "category", "fee_aed", "success_fee_pct", "human_review_hours", "clarification_rounds",
                "contract_value_aed", "buyer_score_pct", "loss_reason", "notes"):
        p.add_argument(f"--{key.replace('_', '-')}", dest=key)
    for key in ("submitted_on_time", "debrief_received", "shortlisted", "awarded"):
        p.add_argument(f"--{key.replace('_', '-')}", dest=key, choices=("yes", "no"))
    p.set_defaults(fn=cmd_log)

    p = sub.add_parser("close", help="deliver artefacts and delete the workspace")
    p.add_argument("run")
    p.add_argument("--deliver-to", required=True, help="directory synced to the client's tenant")
    p.add_argument("--force", action="store_true", help="close without an outcome log entry")
    p.set_defaults(fn=cmd_close)

    p = sub.add_parser("run", help="intake, extract, matrix, gaps, draft, pack and review")
    _intake_args(p)
    p.add_argument("--model", choices=CHOICES, default="auto")
    p.set_defaults(fn=cmd_run)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.fn(args)
    except (TierViolation, TierError) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 3
    except (RunError, MatrixError, LibraryError, DocumentError, ModelError, FileExistsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
