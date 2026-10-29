"""Outcome log. One row per run in a CSV whose columns match templates/bid-outcome-log.csv.

The tender reference is stored as a hash. No personal data is written.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .util import read_json, sha256_text

COLUMNS = [
    "run_id", "client_id", "country", "portal", "buyer_type", "category", "tender_reference_hash", "data_tier",
    "received_date", "deadline", "delivered_date", "bid_size", "fee_aed", "success_fee_pct", "clauses_total",
    "clauses_mandatory", "mandatory_gaps_at_delivery", "scored_points_available", "scored_points_evidenced",
    "human_review_hours", "unsupported_claims_found", "clarification_rounds", "submitted_on_time", "outcome",
    "shortlisted", "awarded", "contract_value_aed", "buyer_score_pct", "loss_reason", "debrief_received", "notes",
]
OUTCOMES = ("delivered", "submitted", "shortlisted", "awarded", "lost", "withdrawn", "disqualified", "no_go")


def bid_size(clauses: int) -> str:
    return "small" if clauses <= 40 else "medium" if clauses <= 120 else "large"


def build_row(run: Any, matrix: dict, review: dict | None, fields: dict[str, Any]) -> dict[str, str]:
    t, s = matrix["tender"], matrix["summary"]
    stages = run.data.get("stages", {})
    outcome = fields.get("outcome", "")
    shortlisted = fields.get("shortlisted")
    awarded = fields.get("awarded")
    if outcome == "awarded":
        shortlisted, awarded = shortlisted or "yes", "yes"
    elif outcome == "shortlisted":
        shortlisted = "yes"
    elif outcome in ("lost", "disqualified"):
        awarded = awarded or "no"
    row = {
        "run_id": run.id,
        "client_id": run.data.get("client_id", ""),
        "country": t["country"],
        "portal": t["portal"],
        "buyer_type": fields.get("buyer_type") or run.data.get("buyer_type", ""),
        "category": fields.get("category") or run.data.get("category", ""),
        "tender_reference_hash": sha256_text(t["reference"])[:16],
        "data_tier": t["data_tier"],
        "received_date": stages.get("intake", {}).get("at", "")[:10],
        "deadline": t["deadline"],
        "delivered_date": stages.get("pack", {}).get("at", "")[:10],
        "bid_size": bid_size(s["total"]),
        "clauses_total": s["total"],
        "clauses_mandatory": s["mandatory_total"],
        "mandatory_gaps_at_delivery": s["mandatory_gaps"],
        "scored_points_available": s["scored_points_available"],
        "scored_points_evidenced": s["scored_points_evidenced"],
        "unsupported_claims_found": (review or {}).get("unsupported_claims", ""),
        "outcome": outcome,
        "shortlisted": shortlisted or "",
        "awarded": awarded or "",
    }
    for key in ("fee_aed", "success_fee_pct", "human_review_hours", "clarification_rounds", "submitted_on_time",
                "contract_value_aed", "buyer_score_pct", "loss_reason", "debrief_received", "notes"):
        if fields.get(key) not in (None, ""):
            row[key] = fields[key]
    return {k: "" if row.get(k) is None else str(row.get(k, "")) for k in COLUMNS}


def append_or_update(log_path: str | Path, row: dict[str, str]) -> str:
    """Insert the row, or merge it into the existing row with the same run_id. Returns 'added' or 'updated'."""
    path = Path(log_path)
    rows: list[dict[str, str]] = []
    if path.exists() and path.stat().st_size:
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames != COLUMNS:
                raise ValueError(f"{path} has unexpected columns; expected the template header")
            rows = list(reader)
    action = "added"
    for existing in rows:
        if existing["run_id"] == row["run_id"]:
            existing.update({k: v for k, v in row.items() if v != ""})
            action = "updated"
            break
    else:
        rows.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    return action


def load_review(run_dir: Path) -> dict | None:
    p = run_dir / "review.json"
    return read_json(p) if p.exists() else None
