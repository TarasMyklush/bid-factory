"""bf ui: the local web interface. Runs a real server on a free port against synthetic fixtures."""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from bf import ui

from .helpers import CLEAN_ENV, LIBRARY, TENDER

TOKEN = "test-token"
ROOT = Path(__file__).resolve().parents[1]


class Client:
    def __init__(self, port: int):
        self.base = f"http://127.0.0.1:{port}"

    def call(self, method: str, path: str, body: object = None, *, cookie: bool = True, headers: dict | None = None,
             raw: bytes | None = None) -> tuple[int, dict, bytes]:
        h = {} if method in ("GET", "HEAD") else {"X-BF-Request": "1"}
        if cookie:
            h["Cookie"] = f"{ui.COOKIE}={TOKEN}"
        data = raw
        if body is not None:
            data = json.dumps(body).encode()
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        req = urllib.request.Request(self.base + path, data=data, method=method, headers=h)
        opener = urllib.request.build_opener(NoRedirect)
        try:
            with opener.open(req) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as e:
            with e:
                return e.code, dict(e.headers), e.read()

    def json(self, method: str, path: str, body: object = None, **kw) -> tuple[int, object]:
        status, _, data = self.call(method, path, body, **kw)
        return status, json.loads(data) if data else None

    def wait(self, job_id: str, timeout: float = 120) -> dict:
        end = time.time() + timeout
        while time.time() < end:
            _, job = self.json("GET", f"/api/jobs/{job_id}")
            if job["state"] != "running":
                return job
            time.sleep(0.2)
        raise AssertionError(f"job {job_id} did not finish")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D401 - urllib hook
        return None


class UiCase(unittest.TestCase):
    """One server and one demo bid for the whole class: each pipeline run takes a few seconds."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.env = mock.patch.dict(os.environ, CLEAN_ENV, clear=True)
        cls.env.start()
        cls.tmp = Path(tempfile.mkdtemp(prefix="bf-ui-test-"))
        cls.ws = ui.Workspace(cls.tmp / "ws")
        shutil.copytree(LIBRARY, cls.ws.libraries / "falcon")
        shutil.copytree(TENDER, cls.ws.tenders / "ndsa")
        cls.app = ui.App(cls.ws, TOKEN, "127.0.0.1", 0)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), ui.make_handler(cls.app))
        cls.app.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.c = Client(cls.app.port)
        status, job = cls.c.json("POST", "/api/jobs", {"tender_id": "ndsa", "library": "falcon", "client": "falcon"})
        assert status == 202, job
        cls.job = cls.c.wait(job["id"])
        cls.run_id = cls.job["run_id"]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)
        cls.env.stop()


class SecurityTests(UiCase):
    def test_api_needs_the_session_cookie(self):
        status, body = self.c.json("GET", "/api/runs", cookie=False)
        self.assertEqual(status, 401)
        self.assertIn("session locked", body["error"])

    def test_token_link_sets_an_http_only_strict_cookie(self):
        status, headers, _ = self.c.call("GET", f"/?token={TOKEN}", cookie=False)
        self.assertEqual(status, 303)
        cookie = headers["Set-Cookie"]
        self.assertIn(f"{ui.COOKIE}={TOKEN}", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertEqual(self.c.call("GET", "/?token=wrong", cookie=False)[0], 403)

    def test_foreign_host_header_is_refused(self):
        status, _ = self.c.json("GET", "/api/runs", headers={"Host": f"attacker.example:{self.app.port}"})
        self.assertEqual(status, 400)

    def test_state_changes_need_the_request_header_and_same_origin(self):
        status, _ = self.c.json("POST", "/api/tenders", {}, headers={"X-BF-Request": ""})
        self.assertEqual(status, 403)
        status, _ = self.c.json("POST", "/api/tenders", {}, headers={"Origin": "http://attacker.example"})
        self.assertEqual(status, 403)
        status, _ = self.c.json("POST", "/api/tenders", {}, headers={"Sec-Fetch-Site": "cross-site"})
        self.assertEqual(status, 403)

    def test_pages_carry_a_strict_content_security_policy(self):
        status, headers, body = self.c.call("GET", "/", cookie=False)
        self.assertEqual(status, 200)
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertNotRegex(body.decode(), r"https?://(?!www\.w3\.org)")  # nothing loads from the internet

    def test_static_files_are_limited_to_the_bundle(self):
        self.assertEqual(self.c.call("GET", "/app.js", cookie=False)[0], 200)
        self.assertEqual(self.c.call("GET", "/../ui.py", cookie=False)[0], 404)
        self.assertEqual(self.c.call("GET", "/ui.py", cookie=False)[0], 404)

    def test_downloads_are_limited_to_deliverables(self):
        base = f"/api/runs/{self.run_id}/download?path="
        self.assertEqual(self.c.call("GET", base + "run.json")[0], 403)
        self.assertEqual(self.c.call("GET", base + "../../../etc/passwd")[0], 403)
        self.assertEqual(self.c.call("GET", base + "pack/../run.json")[0], 403)
        self.assertEqual(self.c.call("GET", base + "pack/nothing.md")[0], 404)
        self.assertEqual(self.c.call("GET", base + "gap-report.md")[0], 200)

    def test_bad_names_are_refused(self):
        self.assertEqual(self.c.json("GET", "/api/runs/..%2F..%2Fetc")[0], 400)
        self.assertEqual(self.c.json("GET", "/api/libraries/..")[0], 400)


class PipelineTests(UiCase):
    def test_new_bid_runs_every_stage_and_blocks_on_the_planted_gaps(self):
        self.assertEqual(self.job["state"], "done")
        states = {s["name"]: s["state"] for s in self.job["stages"]}
        self.assertEqual(states["review"], "blocked")
        self.assertTrue(all(v == "done" for k, v in states.items() if k != "review"))
        _, d = self.c.json("GET", f"/api/runs/{self.run_id}")
        self.assertEqual(d["summary"]["recommendation"], "no_go")
        self.assertEqual(d["matrix_summary"]["mandatory_gaps"], 3)
        self.assertFalse(d["pack"]["deliverable"])
        self.assertEqual(d["attach_at_submission"][0]["id"], "ID-001")

    def test_bids_list_and_matrix_with_library_records(self):
        _, runs = self.c.json("GET", "/api/runs")
        self.assertIn(self.run_id, [r["run_id"] for r in runs])
        _, mx = self.c.json("GET", f"/api/runs/{self.run_id}/matrix")
        self.assertEqual(len(mx["matrix"]["rows"]), 35)
        self.assertIn("CERT-002", mx["records"])
        people = [r for r in mx["records"].values() if r["type"] == "person"]
        self.assertTrue(people)
        self.assertFalse(any("@" in json.dumps(p) for p in people), "person records must reach the UI pseudonymised")

    def test_pack_downloads_as_a_zip(self):
        status, headers, body = self.c.call("GET", f"/api/runs/{self.run_id}/download?path=pack.zip")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "application/zip")
        names = zipfile.ZipFile(io.BytesIO(body)).namelist()
        self.assertTrue(any(n.endswith("_02_technical-response.docx") for n in names))

    def test_sign_off_is_refused_while_review_is_blocked(self):
        status, body = self.c.json("POST", f"/api/runs/{self.run_id}/signoff", {"reviewer": "R", "checked": []})
        self.assertEqual(status, 409)
        self.assertIn("automated review", body["error"])

    def test_libraries_and_tenders(self):
        _, libs = self.c.json("GET", "/api/libraries")
        self.assertEqual(libs[0]["records"], 18)
        _, tenders = self.c.json("GET", "/api/tenders")
        ndsa = next(t for t in tenders if t["id"] == "ndsa")
        self.assertEqual(ndsa["meta"]["reference"], "NDSA-2026-ITSD-014")
        self.assertIn(self.run_id, ndsa["used_by"])
        self.assertEqual(self.c.json("DELETE", "/api/tenders/ndsa/files/rfp.md")[0], 409)


class EditingTests(UiCase):
    def test_edits_mark_the_review_stale_and_notes_survive_a_recheck(self):
        rid = self.run_id
        status, row = self.c.json("PATCH", f"/api/runs/{rid}/rows/C-006", {"reviewer_notes": "LCGPA certificate requested"})
        self.assertEqual(status, 200)
        self.assertEqual(row["reviewer_notes"], "LCGPA certificate requested")

        _, sec = self.c.json("GET", f"/api/runs/{rid}/sections/01-company.md")
        status, _ = self.c.json("PUT", f"/api/runs/{rid}/sections/01-company.md", {"text": sec["text"] + "\nWe have 400 staff.\n"})
        self.assertEqual(status, 200)
        _, d = self.c.json("GET", f"/api/runs/{rid}")
        self.assertTrue(d["summary"]["stale"])

        # Rebuilding the pack and review keeps the edit, and the review catches the uncited number.
        _, job = self.c.json("POST", f"/api/runs/{rid}/rerun", {"from": "pack"})
        self.assertEqual(self.c.wait(job["id"])["state"], "done")
        _, d = self.c.json("GET", f"/api/runs/{rid}")
        self.assertFalse(d["summary"]["stale"])
        self.assertTrue(any(f["code"] == "B2" and "400 staff" in f["message"] for f in d["review"]["findings"]))

        # A full re-check re-drafts (dropping the edit) and keeps reviewer notes.
        _, job = self.c.json("POST", f"/api/runs/{rid}/rerun", {"from": "matrix"})
        self.assertEqual(self.c.wait(job["id"])["state"], "done")
        _, mx = self.c.json("GET", f"/api/runs/{rid}/matrix")
        self.assertEqual(next(r for r in mx["matrix"]["rows"] if r["id"] == "C-006")["reviewer_notes"], "LCGPA certificate requested")
        _, sec = self.c.json("GET", f"/api/runs/{rid}/sections/01-company.md")
        self.assertNotIn("400 staff", sec["text"])
        self.assertIsNone(sec["edited_at"])

    def test_unknown_sections_and_rows(self):
        self.assertEqual(self.c.json("GET", f"/api/runs/{self.run_id}/sections/run.json")[0], 404)
        self.assertEqual(self.c.json("PATCH", f"/api/runs/{self.run_id}/rows/C-999", {"reviewer_notes": "x"})[0], 404)


class UploadAndTierTests(UiCase):
    def test_upload_accepts_documents_and_refuses_other_files(self):
        _, t = self.c.json("POST", "/api/tenders", {"label": "Upload test"})
        tid = t["id"]
        self.assertEqual(self.c.json("PUT", f"/api/tenders/{tid}/files/run.exe", raw=b"MZ")[0], 415)
        self.assertEqual(self.c.json("PUT", f"/api/tenders/{tid}/files/notes.json", raw=b"{}")[0], 400)
        self.assertEqual(self.c.json("PUT", f"/api/tenders/{tid}/files/tender.json", raw=b"{not json")[0], 400)
        status, t = self.c.json("PUT", f"/api/tenders/{tid}/files/RFP%20(final).md", raw=b"# RFP\n")
        self.assertEqual(status, 201)
        self.assertEqual([f["name"] for f in t["files"]], ["RFP (final).md"])
        status, t = self.c.json("DELETE", f"/api/tenders/{tid}/files/RFP%20(final).md")
        self.assertEqual(t["files"], [])

    def test_restricted_tender_with_claude_is_refused(self):
        status, job = self.c.json("POST", "/api/jobs", {"tender_id": "ndsa", "library": "falcon", "client": "t", "model": "anthropic", "tier": "B"})
        self.assertEqual(status, 202)
        job = self.c.wait(job["id"])
        self.assertEqual(job["state"], "refused")
        self.assertIn("non-resident", job["error"])

    def test_log_and_close_deletes_the_workspace_and_uploaded_tender(self):
        _, t = self.c.json("POST", "/api/tenders", {"label": "close test"})
        tid = t["id"]
        for name in ("rfp.md", "tender.json"):
            self.c.json("PUT", f"/api/tenders/{tid}/files/{name}", raw=(TENDER / name).read_bytes())
        _, job = self.c.json("POST", "/api/jobs", {"tender_id": tid, "library": "falcon", "client": "close", "public": True})
        rid = self.c.wait(job["id"])["run_id"]
        status, body = self.c.json("POST", f"/api/runs/{rid}/close", {})
        self.assertEqual(status, 400)
        self.assertIn("log the outcome first", body["error"])
        status, _ = self.c.json("POST", f"/api/runs/{rid}/outcome", {"outcome": "no_go", "notes": "local content too low"})
        self.assertEqual(status, 200)
        self.assertIn(rid, self.ws.outcome_log.read_text())
        status, body = self.c.json("POST", f"/api/runs/{rid}/close", {})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["tender_removed"], tid)
        self.assertFalse((self.ws.runs / rid).exists())
        self.assertFalse((self.ws.tenders / tid).exists())
        self.assertTrue((self.ws.delivered / rid / "pack").is_dir())


class DemoSeedTest(unittest.TestCase):
    def test_demo_adds_the_sample_tender_and_library_once(self):
        tmp = Path(tempfile.mkdtemp(prefix="bf-ui-seed-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        ws = ui.Workspace(tmp)
        self.assertEqual(sorted(ui.seed_demo(ws)), ["falcon-demo", "sample-ndsa-service-desk"])
        self.assertEqual(ui.seed_demo(ws), [])
        self.assertTrue((ws.libraries / "falcon-demo" / "records").is_dir())


class ChecklistTest(unittest.TestCase):
    def test_sign_off_checklist_matches_the_template(self):
        text = (ROOT / "templates" / "review-checklist.md").read_text()
        sections = re.findall(r"^## (.+)$", text, re.M)
        items = re.findall(r"^- \[ \] (.+)$", text, re.M)
        self.assertEqual([s for s, _ in ui.CHECKLIST], sections)
        self.assertEqual([i for _, group in ui.CHECKLIST for i in group], items)


if __name__ == "__main__":
    unittest.main()
