"""bf ui: a local web interface over the same pipeline the command line runs.

Standard library only (http.server), no CDN, no build step, so it installs and runs on an air-gapped machine.
Pipeline stages run as `python -m bf.cli` subprocesses: the CLI stays the single implementation, and every tier
rule it enforces applies to the UI unchanged.

Security model (the server holds client data, so it is treated as sensitive even on localhost):
- binds to 127.0.0.1 unless --host says otherwise;
- every API call needs the session cookie, set only by opening the one-time link printed at start-up;
- the Host header must name this server (DNS rebinding), and state-changing requests must carry the
  X-BF-Request header and a same-origin Origin (CSRF);
- strict Content-Security-Policy, no inline script, no third-party requests of any kind.

Workspace layout (outside the repository; it holds client data):

    <workspace>/tenders/<id>/     uploaded tender documents, deleted when the bid is closed
    <workspace>/libraries/<name>/ client bid libraries (or --libraries DIR, e.g. a folder synced to the client tenant)
    <workspace>/runs/<run-id>/    run workspaces, as for the CLI
    <workspace>/delivered/        what `bf close` delivers
    <workspace>/bid-outcome-log.csv
"""
from __future__ import annotations

import http.cookies
import importlib.util
import io
import json
import mimetypes
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import webbrowser
import zipfile
from datetime import date, datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from . import __version__
from .library import Library, LibraryError
from .matrix import MatrixError, validate
from .outcome import OUTCOMES
from .runs import STAGES
from .util import now_iso, read_json, slug, write_json

PIPELINE = ("extract", "matrix", "gaps", "draft", "pack", "review")
MODEL_STAGES = {"matrix", "draft"}
TENDER_SUFFIXES = {".pdf", ".docx", ".md", ".txt", ".json"}
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._()-]{0,150}$")
COOKIE = "bf_session"
MAX_UPLOAD = 100 * 1024 * 1024
MAX_JSON = 1024 * 1024
STAGE_TIMEOUT = 30 * 60
DOWNLOADABLE = ("pack/", "sections/", "gap-report.md", "review-findings.md", "matrix.json")
EXPIRY_WARNING_DAYS = 90

# The human review gate, templates/review-checklist.md sections A to G. A test keeps the two in step.
CHECKLIST: list[tuple[str, list[str]]] = [
    ("A. Matrix", [
        "Every extracted clause has a status. The run would have halted otherwise; confirm the halt was not overridden.",
        "Mandatory gaps are zero, or the pack is explicitly marked \"not for submission\" and the client has been told why.",
        "Spot-check ten clauses against the tender text: verbatim, correct location, correct mandatory flag.",
        "Evaluation weights and pass marks match the tender.",
    ]),
    ("B. Evidence", [
        "Reviewer assistant findings read in full. Every unsupported claim resolved: evidence added, claim removed, or tagged `[CLIENT INPUT NEEDED]`.",
        "Every certification, accreditation and partner status named in the draft exists in the library with a valid date at submission.",
        "Every past-performance reference has permission to cite at the level used.",
        "No name, contact or identity detail appears that the client has not approved for this bid.",
    ]),
    ("C. Numbers", [
        "Every number in the commercial narrative matches the client's pricing sheet. Code check passed; re-run if the sheet changed.",
        "Headcount, turnover, years in business, team sizes and project values match library records.",
        "Dates and durations in the implementation plan are internally consistent and match the tender's timeline.",
    ]),
    ("D. Compliance of the pack itself", [
        "Buyer's template, section order and headings followed.",
        "Every mandatory form present, filled or tagged, signatures and stamps marked.",
        "File names, formats and size limits meet the portal's rules.",
        "Bonds, guarantees, originals and in-person steps listed on the submission checklist with dates.",
        "Arabic cover material present where required.",
    ]),
    ("E. Quality", [
        "The response answers the question asked in each clause, not a neighbouring one.",
        "No boilerplate contradicts a tender-specific statement.",
        "Risks and assumptions are stated where the client is exposed.",
        "Tone matches the buyer and the client's house style.",
    ]),
    ("F. Data handling", [
        "Data tier recorded at intake is correct for what the tender actually contained.",
        "No Tier C material was processed by a model. No Tier B material went to a non-resident model.",
        "Run workspace scheduled for deletion at close.",
    ]),
    ("G. Hand-off", [
        "Submission checklist on top of the pack with the deadline in the buyer's time zone.",
        "Client sign-off request sent to the named signatory with the list of claims they are attesting to.",
        "Outcome log entry created with status `delivered`.",
    ]),
]


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


# ---------------------------------------------------------------- workspace

class Workspace:
    def __init__(self, root: Path, libraries: Path | None = None):
        self.root = root.resolve()
        self.tenders = self.root / "tenders"
        self.libraries = (libraries or self.root / "libraries").resolve()
        self.runs = self.root / "runs"
        self.delivered = self.root / "delivered"
        self.outcome_log = self.root / "bid-outcome-log.csv"
        for d in (self.tenders, self.libraries, self.runs, self.delivered):
            d.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _child(parent: Path, name: str) -> Path:
        if not SAFE_NAME.match(name) or name in (".", ".."):
            raise ApiError(400, f"invalid name: {name!r}")
        p = (parent / name).resolve()
        if p.parent != parent.resolve():
            raise ApiError(400, f"invalid name: {name!r}")
        return p

    def run_dir(self, run_id: str) -> Path:
        d = self._child(self.runs, run_id)
        if not (d / "run.json").exists():
            raise ApiError(404, f"no such bid: {run_id}")
        return d

    def tender_dir(self, tender_id: str) -> Path:
        d = self._child(self.tenders, tender_id)
        if not d.is_dir():
            raise ApiError(404, f"no such tender: {tender_id}")
        return d

    def library_dir(self, name: str) -> Path:
        d = self._child(self.libraries, name)
        if not (d / "records").is_dir():
            raise ApiError(404, f"no such library: {name}")
        return d


def seed_demo(ws: Workspace) -> list[str]:
    """Copy the synthetic fixtures from a source checkout into the workspace. Returns what was added."""
    fixtures = Path(__file__).resolve().parents[2] / "tests" / "fixtures"
    added = []
    for src, dest in ((fixtures / "library_falcon", ws.libraries / "falcon-demo"),
                      (fixtures / "tender_sa", ws.tenders / "sample-ndsa-service-desk")):
        if not src.is_dir():
            raise SystemExit("--demo needs a source checkout of bid-factory (tests/fixtures not found)")
        if not dest.exists():
            shutil.copytree(src, dest)
            added.append(dest.name)
    return added


# ---------------------------------------------------------------- read models

def _days_left(deadline: str | None) -> int | None:
    if not deadline:
        return None
    try:
        dl = datetime.fromisoformat(deadline)
    except ValueError:
        return None
    return (dl - datetime.now(timezone.utc)).days if dl.tzinfo else None


def _maybe_json(path: Path) -> Any:
    try:
        return read_json(path) if path.exists() else None
    except (OSError, ValueError):
        return None


def run_summary(d: Path, busy: bool) -> dict[str, Any]:
    data = read_json(d / "run.json")
    stages = data.get("stages", {})
    matrix_stage = stages.get("matrix", {})
    review = stages.get("review", {})
    pack = stages.get("pack", {})
    tender = data.get("tender", {})
    stale = bool(data.get("ui", {}).get("review_stale"))
    return {
        "run_id": data["run_id"], "client_id": data.get("client_id"), "created_at": data.get("created_at"),
        "tender": tender, "tier": tender.get("data_tier"),
        "status": data.get("status"),
        "stages": [s for s in STAGES if s in stages],
        "recommendation": matrix_stage.get("go_no_go"), "mandatory_gaps": matrix_stage.get("mandatory_gaps"),
        "review": review.get("result"), "blocking": review.get("blocking"),
        "deliverable": pack.get("deliverable"), "days_left": _days_left(tender.get("deadline")),
        "signed_off": bool(data.get("ui", {}).get("signoff")), "logged": stages.get("log", {}).get("outcome"),
        "stale": stale, "busy": busy,
    }


def library_summary(d: Path) -> dict[str, Any]:
    out: dict[str, Any] = {"name": d.name, "path": str(d)}
    try:
        lib = Library.load(d)
    except (LibraryError, ValueError, OSError) as exc:
        out["error"] = str(exc)
        return out
    today = date.today()
    soon = today + timedelta(days=EXPIRY_WARNING_DAYS)
    types: dict[str, int] = {}
    for r in lib.records.values():
        types[r.type] = types.get(r.type, 0) + 1
    out.update({
        "records": len(lib.records), "types": types,
        "expired": sum(1 for r in lib.records.values() if r.valid_until and r.valid_until < today),
        "expiring": sum(1 for r in lib.records.values() if r.valid_until and today <= r.valid_until <= soon),
        "attach_at_submission": len(lib.attach_at_submission), "has_pricing": lib.pricing is not None,
        "company": next((r.title for r in lib.by_type("company")), None),
    })
    return out


def library_records(lib: Library) -> dict[str, dict[str, Any]]:
    out = {}
    for r in lib.records.values():
        b = r.brief(text_limit=4000)
        b["tags"] = r.tags
        if r.role:
            b["role"] = r.role
        out[r.id] = b
    return out


def model_status() -> dict[str, Any]:
    sdk = importlib.util.find_spec("anthropic") is not None
    url = os.environ.get("BF_TIER_B_URL", "")
    return {
        "anthropic_key": bool(os.environ.get("ANTHROPIC_API_KEY")), "anthropic_sdk": sdk,
        "anthropic_model": os.environ.get("BF_MODEL", "claude-opus-5-5"),
        "tier_b_endpoint": urlsplit(url).netloc if url else "", "tier_b_model": os.environ.get("BF_TIER_B_MODEL", ""),
    }


# ---------------------------------------------------------------- jobs

class Jobs:
    """Pipeline jobs, one thread each. A run is busy while a job holds it; mutations on a busy run are refused."""

    def __init__(self, ws: Workspace):
        self.ws = ws
        self.lock = threading.Lock()
        self.jobs: dict[str, dict[str, Any]] = {}
        self.busy: set[str] = set()

    def get(self, job_id: str) -> dict[str, Any]:
        with self.lock:
            job = self.jobs.get(job_id)
            if job is None:
                raise ApiError(404, "no such job")
            return json.loads(json.dumps(job))

    def is_busy(self, run_id: str) -> bool:
        with self.lock:
            return run_id in self.busy

    def active(self, run_id: str) -> str | None:
        with self.lock:
            return next((j["id"] for j in self.jobs.values() if j["run_id"] == run_id and j["state"] == "running"), None)

    def _new(self, kind: str, stages: list[str], run_id: str | None) -> dict[str, Any]:
        job = {"id": secrets.token_hex(6), "kind": kind, "state": "running", "run_id": run_id, "error": None,
               "started_at": now_iso(), "stages": [{"name": s, "state": "pending", "message": ""} for s in stages]}
        with self.lock:
            if run_id and run_id in self.busy:
                raise ApiError(409, "this bid is already being processed")
            if run_id:
                self.busy.add(run_id)
            self.jobs[job["id"]] = job
        return job

    def _set(self, job: dict, **kw: Any) -> None:
        with self.lock:
            job.update(kw)

    def _stage(self, job: dict, i: int, **kw: Any) -> None:
        with self.lock:
            job["stages"][i].update(kw)

    def _cli(self, *args: str) -> tuple[int, str, str]:
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([str(Path(__file__).resolve().parents[1]), env.get("PYTHONPATH", "")])
        p = subprocess.run([sys.executable, "-m", "bf.cli", *args], capture_output=True, text=True,
                           timeout=STAGE_TIMEOUT, env=env, cwd=self.ws.root)
        return p.returncode, p.stdout.strip(), p.stderr.strip()

    @staticmethod
    def _message(out: str, err: str) -> str:
        lines = [l for l in (out.splitlines() + err.splitlines()) if l.strip()]
        return lines[-1] if lines else ""

    def start_new(self, req: dict[str, Any]) -> dict[str, Any]:
        tender = self.ws.tender_dir(_req_str(req, "tender_id"))
        library = self.ws.library_dir(_req_str(req, "library"))
        client = _req_str(req, "client")
        model = req.get("model") or "auto"
        args = ["intake", str(tender), "--library", str(library), "--client", client, "--runs-dir", str(self.ws.runs)]
        if req.get("public"):
            args.append("--public")
        if req.get("tier") in ("B", "C"):
            args += ["--tier", req["tier"]]
        for key in ("buyer", "reference", "title", "portal", "country", "deadline", "category"):
            if req.get(key):
                args += [f"--{key}", str(req[key])]
        job = self._new("new", ["intake", *PIPELINE], None)
        threading.Thread(target=self._run_new, args=(job, args, model), daemon=True).start()
        return job

    def start_rerun(self, run_id: str, start: str, model: str) -> dict[str, Any]:
        if start not in PIPELINE:
            raise ApiError(400, f"cannot restart from {start!r}")
        run_dir = self.ws.run_dir(run_id)
        job = self._new("rerun", list(PIPELINE[PIPELINE.index(start):]), run_id)
        threading.Thread(target=self._run_stages, args=(job, run_dir, 0, model), daemon=True).start()
        return job

    def _run_new(self, job: dict, args: list[str], model: str) -> None:
        self._stage(job, 0, state="running")
        try:
            code, out, err = self._cli(*args)
        except Exception as exc:  # pragma: no cover - subprocess failure
            code, out, err = 2, "", str(exc)
        first = out.splitlines()[0] if out else ""
        run_dir = Path(first) if first and Path(first).joinpath("run.json").exists() else None
        if run_dir:
            self._set(job, run_id=run_dir.name)
        if code == 3:
            self._stage(job, 0, state="refused", message=self._message(out, err))
            self._set(job, state="refused", error=self._message(out, err))
            return
        if code != 0 or run_dir is None:
            self._stage(job, 0, state="failed", message=self._message(out, err))
            self._set(job, state="failed", error=self._message(out, err) or "intake failed")
            return
        self._stage(job, 0, state="done", message=out.splitlines()[-1] if out else "")
        with self.lock:
            if run_dir.name in self.busy:  # pragma: no cover - run ids are unique
                job["state"] = "failed"
                return
            self.busy.add(run_dir.name)
        self._run_stages(job, run_dir, 1, model)

    def _run_stages(self, job: dict, run_dir: Path, offset: int, model: str) -> None:
        notes = _reviewer_notes(run_dir)
        try:
            _clear_ui(run_dir, "signoff")
            for i in range(offset, len(job["stages"])):
                name = job["stages"][i]["name"]
                self._stage(job, i, state="running")
                args = [name, str(run_dir)]
                if name in MODEL_STAGES:
                    args += ["--model", model]
                try:
                    code, out, err = self._cli(*args)
                except subprocess.TimeoutExpired:
                    code, out, err = 2, "", f"{name} timed out"
                msg = self._message(out, err)
                if code == 3:
                    self._stage(job, i, state="refused", message=msg)
                    self._set(job, state="refused", error=msg)
                    return
                if name == "review" and code in (0, 1):
                    _clear_ui(run_dir, "review_stale")
                if name == "review" and code == 1:
                    self._stage(job, i, state="blocked", message=msg)
                    continue
                if code != 0:
                    self._stage(job, i, state="failed", message=msg)
                    self._set(job, state="failed", error=msg)
                    return
                if name == "matrix" and notes:
                    _restore_reviewer_notes(run_dir, notes)
                if name == "draft":
                    _clear_ui(run_dir, "edits")
                self._stage(job, i, state="done", message=msg)
            self._set(job, state="done")
        finally:
            with self.lock:
                self.busy.discard(run_dir.name)


def _reviewer_notes(run_dir: Path) -> dict[str, str]:
    m = _maybe_json(run_dir / "matrix.json")
    return {r["id"]: r["reviewer_notes"] for r in (m or {}).get("rows", []) if r.get("reviewer_notes")}


def _restore_reviewer_notes(run_dir: Path, notes: dict[str, str]) -> None:
    path = run_dir / "matrix.json"
    m = read_json(path)
    for r in m["rows"]:
        if r["id"] in notes:
            r["reviewer_notes"] = notes[r["id"]]
    validate(m)
    write_json(path, m)


def _clear_ui(run_dir: Path, key: str) -> None:
    """Drop UI state a pipeline stage invalidates: section edits after a re-draft, sign-off after any re-run,
    the stale-review flag once the review has run on the current text."""
    data = read_json(run_dir / "run.json")
    if data.get("ui", {}).pop(key, None) is not None:
        write_json(run_dir / "run.json", data)


def _req_str(req: dict, key: str, required: bool = True) -> str:
    v = req.get(key)
    if v is None or (isinstance(v, str) and not v.strip()):
        if required:
            raise ApiError(400, f"{key} is required")
        return ""
    if not isinstance(v, (str, int, float)):
        raise ApiError(400, f"{key} must be text")
    return str(v).strip()


# ---------------------------------------------------------------- HTTP

class App:
    def __init__(self, ws: Workspace, token: str, host: str, port: int, allow_hosts: tuple[str, ...] = ()):
        self.ws = ws
        self.token = token
        self.port = port
        self.jobs = Jobs(ws)
        hosts = {"127.0.0.1", "localhost", "[::1]", *allow_hosts}
        if host not in ("0.0.0.0", "::", ""):
            hosts.add(host if ":" not in host else f"[{host}]")
        self.allowed_hosts = {h.lower() for h in hosts}
        self.static = resources.files("bf") / "web"
        self.lock = threading.Lock()

    # ------------------------------------------------ routing

    def route(self, method: str, path: str, query: dict[str, list[str]], body: bytes) -> tuple[int, Any]:
        parts = [unquote(p) for p in path.split("/") if p][1:]  # drop "api"
        j = lambda: _json_body(body)  # noqa: E731
        match method, parts:
            case "GET", ["status"]:
                return 200, self.status()
            case "GET", ["runs"]:
                return 200, self.list_runs()
            case "GET", ["runs", rid]:
                return 200, self.run_detail(rid)
            case "GET", ["runs", rid, "matrix"]:
                return 200, self.run_matrix(rid)
            case "PATCH", ["runs", rid, "rows", row_id]:
                return 200, self.patch_row(rid, row_id, j())
            case "GET", ["runs", rid, "sections", name]:
                return 200, self.get_section(rid, name)
            case "PUT", ["runs", rid, "sections", name]:
                return 200, self.put_section(rid, name, j())
            case "POST", ["runs", rid, "rerun"]:
                req = j()
                return 202, self.jobs.start_rerun(rid, req.get("from", "matrix"), req.get("model") or "auto")
            case "POST", ["runs", rid, "signoff"]:
                return 200, self.signoff(rid, j())
            case "POST", ["runs", rid, "outcome"]:
                return 200, self.outcome(rid, j())
            case "POST", ["runs", rid, "close"]:
                return 200, self.close(rid, j())
            case "GET", ["tenders"]:
                return 200, self.list_tenders()
            case "POST", ["tenders"]:
                return 201, self.new_tender(j())
            case "GET", ["tenders", tid]:
                return 200, self.tender_detail(tid)
            case "DELETE", ["tenders", tid, "files", name]:
                return 200, self.delete_tender_file(tid, name)
            case "GET", ["libraries"]:
                return 200, [library_summary(d) for d in sorted(self.ws.libraries.iterdir())
                             if (d / "records").is_dir()]
            case "GET", ["libraries", name]:
                return 200, self.library_detail(name)
            case "POST", ["jobs"]:
                return 202, self.jobs.start_new(j())
            case "GET", ["jobs", job_id]:
                return 200, self.jobs.get(job_id)
        raise ApiError(404, "not found")

    # ------------------------------------------------ handlers

    def status(self) -> dict[str, Any]:
        return {
            "version": __version__, "workspace": str(self.ws.root), "libraries": str(self.ws.libraries),
            "delivered": str(self.ws.delivered), "outcome_log": str(self.ws.outcome_log),
            "models": model_status(), "outcomes": list(OUTCOMES),
            "checklist": [{"section": s, "items": items} for s, items in CHECKLIST],
        }

    def list_runs(self) -> list[dict[str, Any]]:
        out = []
        for d in self.ws.runs.iterdir():
            if (d / "run.json").exists():
                try:
                    out.append(run_summary(d, self.jobs.is_busy(d.name)))
                except (OSError, ValueError, KeyError):
                    continue
        out.sort(key=lambda r: (r["days_left"] is None, r["days_left"] if r["days_left"] is not None else 0))
        return out

    def run_detail(self, rid: str) -> dict[str, Any]:
        d = self.ws.run_dir(rid)
        data = read_json(d / "run.json")
        matrix = _maybe_json(d / "matrix.json")
        gap_report = d / "gap-report.md"
        pack_dir = d / "pack"
        files = []
        if pack_dir.is_dir():
            for p in sorted(pack_dir.iterdir()):
                if p.is_file() and p.name != "pack-manifest.json":
                    files.append({"name": p.name, "path": f"pack/{p.name}", "bytes": p.stat().st_size})
        attach = []
        try:
            attach = Library.load(data["library_dir"]).attach_at_submission
        except (LibraryError, OSError, ValueError, KeyError):
            pass
        return {
            "summary": run_summary(d, self.jobs.is_busy(rid)), "run": data, "job": self.jobs.active(rid),
            "matrix_summary": (matrix or {}).get("summary"),
            "review": _maybe_json(d / "review.json"),
            "sections": _maybe_json(d / "sections" / "index.json"),
            "pack": _maybe_json(pack_dir / "pack-manifest.json"), "pack_files": files,
            "attach_at_submission": attach,
            "gap_report": gap_report.read_text(encoding="utf-8") if gap_report.exists() else None,
            "library_name": Path(data.get("library_dir", "")).name,
        }

    def run_matrix(self, rid: str) -> dict[str, Any]:
        d = self.ws.run_dir(rid)
        matrix = _maybe_json(d / "matrix.json")
        if matrix is None:
            raise ApiError(404, "the compliance matrix has not been built yet")
        records: dict[str, Any] = {}
        try:
            records = library_records(Library.load(read_json(d / "run.json")["library_dir"]))
        except (LibraryError, OSError, ValueError, KeyError):
            pass
        return {"matrix": matrix, "records": records}

    def _mutable(self, rid: str) -> Path:
        d = self.ws.run_dir(rid)
        if self.jobs.is_busy(rid):
            raise ApiError(409, "this bid is being processed; try again when it finishes")
        return d

    def patch_row(self, rid: str, row_id: str, req: dict) -> dict[str, Any]:
        d = self._mutable(rid)
        notes = req.get("reviewer_notes")
        if not isinstance(notes, str) or len(notes) > 4000:
            raise ApiError(400, "reviewer_notes must be text of at most 4000 characters")
        with self.lock:
            m = read_json(d / "matrix.json")
            row = next((r for r in m["rows"] if r["id"] == row_id), None)
            if row is None:
                raise ApiError(404, f"no such requirement: {row_id}")
            row["reviewer_notes"] = notes.strip()
            try:
                validate(m)
            except MatrixError as exc:
                raise ApiError(400, str(exc))
            write_json(d / "matrix.json", m)
        return row

    def _section_path(self, d: Path, name: str) -> Path:
        index = _maybe_json(d / "sections" / "index.json") or {}
        if name not in {s["file"] for s in index.get("sections", [])}:
            raise ApiError(404, f"no such section: {name}")
        return d / "sections" / name

    def get_section(self, rid: str, name: str) -> dict[str, Any]:
        d = self.ws.run_dir(rid)
        p = self._section_path(d, name)
        edits = read_json(d / "run.json").get("ui", {}).get("edits", {})
        return {"file": name, "text": p.read_text(encoding="utf-8"), "edited_at": edits.get(name)}

    def put_section(self, rid: str, name: str, req: dict) -> dict[str, Any]:
        d = self._mutable(rid)
        p = self._section_path(d, name)
        text = req.get("text")
        if not isinstance(text, str) or len(text) > 500_000:
            raise ApiError(400, "text must be at most 500,000 characters")
        with self.lock:
            p.write_text(text.replace("\r\n", "\n"), encoding="utf-8")
            data = read_json(d / "run.json")
            stamp = now_iso()
            data.setdefault("ui", {}).setdefault("edits", {})[name] = stamp
            data["ui"]["review_stale"] = True
            data["ui"].pop("signoff", None)
            write_json(d / "run.json", data)
        return {"file": name, "edited_at": stamp}

    def signoff(self, rid: str, req: dict) -> dict[str, Any]:
        d = self._mutable(rid)
        summary = run_summary(d, False)
        if summary["review"] != "ready_for_human_review":
            raise ApiError(409, "the automated review must pass before sign-off")
        if summary["stale"]:
            raise ApiError(409, "the draft was edited after the last review; rebuild the pack and review first")
        reviewer = _req_str(req, "reviewer")
        checked = req.get("checked")
        total = sum(len(items) for _, items in CHECKLIST)
        if not isinstance(checked, list) or len(set(map(str, checked))) != total:
            raise ApiError(400, "every checklist item must be confirmed")
        hours = req.get("hours")
        with self.lock:
            data = read_json(d / "run.json")
            data.setdefault("ui", {})["signoff"] = {"reviewer": reviewer[:120], "at": now_iso(),
                                                    "hours": hours if isinstance(hours, (int, float)) else None}
            write_json(d / "run.json", data)
        return data["ui"]["signoff"]

    def outcome(self, rid: str, req: dict) -> dict[str, Any]:
        d = self._mutable(rid)
        outcome = _req_str(req, "outcome")
        if outcome not in OUTCOMES:
            raise ApiError(400, f"outcome must be one of {', '.join(OUTCOMES)}")
        args = ["log", str(d), "--outcome", outcome, "--log-file", str(self.ws.outcome_log)]
        signoff = read_json(d / "run.json").get("ui", {}).get("signoff") or {}
        if signoff.get("hours") is not None and not req.get("human_review_hours"):
            req["human_review_hours"] = signoff["hours"]
        for key in ("fee_aed", "success_fee_pct", "human_review_hours", "clarification_rounds",
                    "contract_value_aed", "buyer_score_pct", "loss_reason", "notes"):
            v = req.get(key)
            if v not in (None, ""):
                args += [f"--{key.replace('_', '-')}", str(v)[:500]]
        for key in ("submitted_on_time", "debrief_received", "shortlisted", "awarded"):
            if req.get(key) in ("yes", "no"):
                args += [f"--{key.replace('_', '-')}", req[key]]
        code, out, err = self.jobs._cli(*args)
        if code != 0:
            raise ApiError(400, Jobs._message(out, err) or "could not log the outcome")
        return {"message": out, "log_file": str(self.ws.outcome_log)}

    def close(self, rid: str, req: dict) -> dict[str, Any]:
        d = self._mutable(rid)
        data = read_json(d / "run.json")
        args = ["close", str(d), "--deliver-to", str(self.ws.delivered)]
        if req.get("force"):
            args.append("--force")
        code, out, err = self.jobs._cli(*args)
        if code != 0:
            raise ApiError(400, Jobs._message(out, err) or "could not close the bid")
        removed = None
        tender = Path(data.get("tender_dir", "")).resolve()
        if tender.parent == self.ws.tenders.resolve() and tender.is_dir():
            in_use = any(_maybe_json(r / "run.json") and read_json(r / "run.json").get("tender_dir") == str(tender)
                         for r in self.ws.runs.iterdir() if r.is_dir())
            if not in_use:
                shutil.rmtree(tender)
                removed = tender.name
        return {"message": out, "delivered_to": str(self.ws.delivered / rid), "tender_removed": removed}

    def list_tenders(self) -> list[dict[str, Any]]:
        out = []
        for d in sorted(self.ws.tenders.iterdir()):
            if d.is_dir():
                out.append(self._tender(d))
        return out

    def _tender(self, d: Path) -> dict[str, Any]:
        files = [{"name": p.name, "bytes": p.stat().st_size} for p in sorted(d.iterdir())
                 if p.is_file() and not p.name.startswith(".")]
        meta = _maybe_json(d / "tender.json")
        return {"id": d.name, "files": files, "meta": meta if isinstance(meta, dict) else None,
                "used_by": [r.name for r in self.ws.runs.iterdir()
                            if (r / "run.json").exists() and (_maybe_json(r / "run.json") or {}).get("tender_dir") == str(d)]}

    def new_tender(self, req: dict) -> dict[str, Any]:
        label = slug(str(req.get("label") or "tender"), 40) or "tender"
        tid = f"{date.today():%Y%m%d}-{label}-{secrets.token_hex(3)}"
        (self.ws.tenders / tid).mkdir()
        return self._tender(self.ws.tenders / tid)

    def tender_detail(self, tid: str) -> dict[str, Any]:
        return self._tender(self.ws.tender_dir(tid))

    def put_tender_file(self, tid: str, name: str, body: bytes) -> dict[str, Any]:
        d = self.ws.tender_dir(tid)
        p = self.ws._child(d, name)
        if p.suffix.lower() not in TENDER_SUFFIXES:
            raise ApiError(415, f"{name}: only PDF, Word (.docx), Markdown, text and JSON files are accepted")
        if p.suffix.lower() == ".json":
            if p.name not in ("tender.json", "pricing.json"):
                raise ApiError(400, "JSON files must be named tender.json or pricing.json")
            try:
                json.loads(body.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                raise ApiError(400, f"{name} is not valid JSON")
        p.write_bytes(body)
        return self._tender(d)

    def delete_tender_file(self, tid: str, name: str) -> dict[str, Any]:
        d = self.ws.tender_dir(tid)
        p = self.ws._child(d, name)
        if self._tender(d)["used_by"]:
            raise ApiError(409, "this tender is used by a bid; its files cannot change")
        if p.is_file():
            p.unlink()
        return self._tender(d)

    def library_detail(self, name: str) -> dict[str, Any]:
        d = self.ws.library_dir(name)
        summary = library_summary(d)
        if "error" in summary:
            return {"summary": summary, "records": [], "attach_at_submission": []}
        lib = Library.load(d)
        return {"summary": summary, "records": list(library_records(lib).values()),
                "attach_at_submission": lib.attach_at_submission}

    # ------------------------------------------------ files

    def download(self, rid: str, rel: str) -> tuple[bytes, str, str]:
        d = self.ws.run_dir(rid)
        if rel == "pack.zip":
            pack = d / "pack"
            if not pack.is_dir():
                raise ApiError(404, "the pack has not been built yet")
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for p in sorted(pack.iterdir()):
                    if p.is_file():
                        z.write(p, p.name)
            return buf.getvalue(), "application/zip", f"{rid}-pack.zip"
        root = d.resolve()
        p = (root / rel).resolve()
        if root not in p.parents:
            raise ApiError(403, "that file is not downloadable")
        rel = p.relative_to(root).as_posix()
        if not any(rel == a or (a.endswith("/") and rel.startswith(a)) for a in DOWNLOADABLE):
            raise ApiError(403, "that file is not downloadable")
        if not p.is_file():
            raise ApiError(404, "no such file")
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        if p.suffix in (".md", ".csv"):
            ctype = "text/plain; charset=utf-8" if p.suffix == ".md" else "text/csv; charset=utf-8"
        return p.read_bytes(), ctype, p.name


def _json_body(body: bytes) -> dict[str, Any]:
    if not body:
        return {}
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ApiError(400, "request body must be JSON")
    if not isinstance(data, dict):
        raise ApiError(400, "request body must be a JSON object")
    return data


SECURITY_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                               "connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
                               "form-action 'self'",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def make_handler(app: App) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "bf-ui"
        sys_version = ""
        protocol_version = "HTTP/1.0"

        def log_message(self, fmt: str, *args: Any) -> None:  # request lines only; never bodies
            if os.environ.get("BF_UI_ACCESS_LOG"):
                sys.stderr.write(f"{self.address_string()} {fmt % args}\n")

        # ---------------------------------------- helpers

        def _send(self, status: int, body: bytes, ctype: str, extra: dict[str, str] | None = None) -> None:
            self.send_response(status)
            for k, v in SECURITY_HEADERS.items():
                self.send_header(k, v)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, data: Any) -> None:
            self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _error(self, status: int, message: str) -> None:
            self._json(status, {"error": message})

        def _host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").lower()
            if host.startswith("["):
                name, _, port = host.partition("]")
                name += "]"
                port = port.lstrip(":")
            else:
                name, _, port = host.partition(":")
            return name in app.allowed_hosts and (port == "" or port == str(app.port))

        def _authed(self) -> bool:
            jar = http.cookies.SimpleCookie()
            try:
                jar.load(self.headers.get("Cookie") or "")
            except http.cookies.CookieError:
                return False
            c = jar.get(COOKIE)
            return bool(c) and secrets.compare_digest(c.value, app.token)

        def _same_origin(self) -> bool:
            if self.headers.get("X-BF-Request") != "1":
                return False
            site = self.headers.get("Sec-Fetch-Site")
            if site and site not in ("same-origin", "none"):
                return False
            origin = self.headers.get("Origin")
            if origin:
                o = urlsplit(origin)
                return f"{o.hostname}".lower() in {h.strip("[]") for h in app.allowed_hosts} and o.port == app.port
            return True

        def _read_body(self, limit: int) -> bytes:
            length = int(self.headers.get("Content-Length") or 0)
            if length > limit:
                raise ApiError(413, f"request too large (limit {limit // (1024 * 1024)} MB)")
            return self.rfile.read(length) if length else b""

        # ---------------------------------------- dispatch

        def _handle(self) -> None:
            if not self._host_ok():
                self._error(400, "unexpected Host header")
                return
            url = urlsplit(self.path)
            query = parse_qs(url.query)
            if not url.path.startswith("/api/"):
                if self.command not in ("GET", "HEAD"):
                    self._error(405, "method not allowed")
                    return
                self._static(url.path, query)
                return
            if not self._authed():
                self._error(401, "session locked: open the link printed by `bf ui`")
                return
            if self.command not in ("GET", "HEAD") and not self._same_origin():
                self._error(403, "cross-site request refused")
                return
            try:
                parts = [p for p in url.path.split("/") if p]
                if self.command == "GET" and len(parts) == 4 and parts[1] == "runs" and parts[3] == "download":
                    rel = (query.get("path") or [""])[0]
                    body, ctype, fname = app.download(parts[2], rel)
                    disp = "inline" if ctype.startswith("text/plain") and query.get("inline") else "attachment"
                    safe = re.sub(r"[^A-Za-z0-9._-]", "_", fname)
                    self._send(200, body, ctype, {"Content-Disposition": f'{disp}; filename="{safe}"'})
                    return
                is_upload = self.command == "PUT" and len(parts) == 5 and parts[1] == "tenders"
                body = self._read_body(MAX_UPLOAD if is_upload else MAX_JSON)
                if is_upload:
                    status, data = 201, app.put_tender_file(parts[2], unquote(parts[4]), body)
                else:
                    status, data = app.route(self.command, url.path, query, body)
                self._json(status, data)
            except ApiError as exc:
                self._error(exc.status, exc.message)
            except (LibraryError, MatrixError) as exc:
                self._error(400, str(exc))
            except Exception as exc:  # pragma: no cover - last resort; never leak a traceback to the page
                sys.stderr.write(f"bf ui: internal error on {self.command} {url.path}: {type(exc).__name__}: {exc}\n")
                self._error(500, "internal error; see the terminal running bf ui")

        def _static(self, path: str, query: dict[str, list[str]]) -> None:
            token = (query.get("token") or [""])[0]
            if token:
                if secrets.compare_digest(token, app.token):
                    cookie = f"{COOKIE}={app.token}; HttpOnly; SameSite=Strict; Path=/"
                    self._send(303, b"", "text/plain", {"Location": "/", "Set-Cookie": cookie})
                else:
                    self._error(403, "invalid token")
                return
            name = "index.html" if path in ("/", "/index.html") else path.lstrip("/")
            if not re.fullmatch(r"[a-z0-9-]+\.(html|js|css|svg)", name):
                self._error(404, "not found")
                return
            res = app.static / name
            if not res.is_file():
                self._error(404, "not found")
                return
            ctype = {"html": "text/html", "js": "text/javascript", "css": "text/css",
                     "svg": "image/svg+xml"}[name.rsplit(".", 1)[1]] + "; charset=utf-8"
            self._send(200, res.read_bytes(), ctype)

        do_GET = do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = _handle

    return Handler


def serve(workspace: str, host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True,
          demo: bool = False, libraries: str | None = None, allow_hosts: tuple[str, ...] = ()) -> int:
    ws = Workspace(Path(workspace).expanduser(), Path(libraries).expanduser() if libraries else None)
    if demo:
        for name in seed_demo(ws):
            print(f"demo: added {name}")
    token = os.environ.get("BF_UI_TOKEN") or secrets.token_urlsafe(24)
    app = App(ws, token, host, port, allow_hosts)
    httpd = ThreadingHTTPServer((host, port), make_handler(app))
    app.port = httpd.server_address[1]
    shown = "127.0.0.1" if host in ("0.0.0.0", "::", "") else (f"[{host}]" if ":" in host else host)
    url = f"http://{shown}:{app.port}/?token={token}"
    print(f"Bid Factory UI {__version__}\n  workspace  {ws.root}\n  libraries  {ws.libraries}\n  open       {url}", flush=True)
    if host not in ("127.0.0.1", "localhost", "::1"):
        print("warning: listening beyond this machine over plain HTTP. Put it behind a TLS reverse proxy "
              "on the company network, and share the link only with the reviewer.", file=sys.stderr)
    print("Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0
