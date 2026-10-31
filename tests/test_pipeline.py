import csv
import json
import unittest
from pathlib import Path

from bf.outcome import COLUMNS
from bf.util import read_json

from .helpers import LIBRARY, TENDER, TempDirCase, run_cli

ROOT = Path(__file__).resolve().parents[1]


class PipelineTests(TempDirCase):
    def test_full_run_with_gaps_is_blocked_and_marked(self):
        code, out, err = run_cli("run", str(TENDER), "--library", str(LIBRARY), "--client", "falcon",
                                 "--runs-dir", str(self.runs))
        self.assertEqual(code, 1, err)
        run = self.only_run()
        manifest = read_json(run / "pack" / "pack-manifest.json")
        self.assertFalse(manifest["deliverable"])
        checklist = next((run / "pack").glob("*_00_submission-checklist.md")).read_text()
        self.assertTrue(checklist.startswith("**NOT FOR SUBMISSION"))
        self.assertIn("Riyadh time, UTC+3", checklist)
        self.assertIn("ID-001", checklist)
        self.assertNotIn("guarantee service desk availability", checklist)
        import docx

        doc = docx.Document(str(next((run / "pack").glob("*_02_technical-response.docx"))))
        self.assertTrue(any("NOT FOR SUBMISSION" in p.text for p in doc.paragraphs))
        result = read_json(run / "review.json")
        self.assertEqual(sorted(f["code"] for f in result["findings"] if f["severity"] == "blocking"), ["A2"] * 3)
        self.assertTrue((run / "gap-report.md").read_text().startswith("# Gap report"))

    def test_clean_library_gives_deliverable_pack(self):
        lib = self.copy_library({
            "CO-001": {"figures": {"local_content_pct": 45}},
            "CERT-002": {"valid_until": "2027-11-20"},
            "PRJ-003": {"permission": "public"},
        })
        code, out, err = run_cli("run", str(TENDER), "--library", str(lib), "--client", "falcon",
                                 "--runs-dir", str(self.runs))
        self.assertEqual(code, 0, err + out)
        run = self.only_run()
        self.assertTrue(read_json(run / "pack" / "pack-manifest.json")["deliverable"])
        self.assertEqual(read_json(run / "review.json")["result"], "ready_for_human_review")
        self.assertFalse(next((run / "pack").glob("*_00_*")).read_text().startswith("**NOT FOR"))

    def test_tier_b_refuses_non_resident_model(self):
        tender = self.write_tender((TENDER / "rfp.md").read_text(), {"public": False})
        code, out, _ = run_cli("intake", str(tender), "--library", str(LIBRARY), "--client", "c",
                               "--runs-dir", str(self.runs))
        self.assertEqual(code, 0)
        run = self.only_run()
        self.assertEqual(read_json(run / "run.json")["tender"]["data_tier"], "B")
        self.assertEqual(run_cli("extract", str(run))[0], 0)
        code, _, err = run_cli("matrix", str(run), "--model", "anthropic")
        self.assertEqual(code, 3)
        self.assertIn("non-resident", err)

    def test_tier_c_is_refused_at_intake_and_after(self):
        tender = self.write_tender("1.1 The bidder must hold ISO 9001.\n\nThird-party processing is strictly prohibited.\n")
        code, out, _ = run_cli("intake", str(tender), "--library", str(LIBRARY), "--client", "c",
                               "--runs-dir", str(self.runs))
        self.assertEqual(code, 3)
        run = self.only_run()
        data = read_json(run / "run.json")
        self.assertEqual(data["tender"]["data_tier"], "C")
        self.assertEqual(data["stages"], {})
        self.assertEqual(run_cli("extract", str(run))[0], 3)
        self.assertFalse((run / "clauses.json").exists())

    def test_missing_metadata_and_naive_deadline_rejected(self):
        tender = self.write_tender("1.1 The bidder must hold ISO 9001.\n", {"deadline": "2026-12-15T13:00:00"})
        code, _, err = run_cli("intake", str(tender), "--library", str(LIBRARY), "--client", "c",
                               "--runs-dir", str(self.runs))
        self.assertEqual(code, 2)
        self.assertIn("UTC offset", err)

    def test_stage_order_enforced(self):
        run_cli("intake", str(TENDER), "--library", str(LIBRARY), "--client", "c", "--runs-dir", str(self.runs))
        code, _, err = run_cli("matrix", str(self.only_run()))
        self.assertEqual(code, 2)
        self.assertIn("extract", err)

    def test_log_and_close(self):
        run_cli("run", str(TENDER), "--library", str(LIBRARY), "--client", "falcon", "--runs-dir", str(self.runs))
        run = self.only_run()
        log = self.tmp / "outcomes.csv"
        self.assertEqual(run_cli("close", str(run), "--deliver-to", str(self.tmp / "out"))[0], 2)
        self.assertEqual(run_cli("log", str(run), "--outcome", "delivered", "--log-file", str(log),
                                 "--fee-aed", "5000", "--human-review-hours", "6")[0], 0)
        self.assertEqual(run_cli("log", str(run), "--outcome", "awarded", "--log-file", str(log),
                                 "--contract-value-aed", "13000000")[0], 0)
        with log.open() as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual((r["outcome"], r["awarded"], r["shortlisted"], r["fee_aed"]), ("awarded", "yes", "yes", "5000"))
        self.assertEqual(r["mandatory_gaps_at_delivery"], "3")
        self.assertNotIn("NDSA", log.read_text())
        code, out, _ = run_cli("close", str(run), "--deliver-to", str(self.tmp / "out"))
        self.assertEqual(code, 0)
        self.assertFalse(run.exists())
        delivered = self.tmp / "out" / run.name
        self.assertTrue((delivered / "pack" / "pack-manifest.json").exists())
        self.assertTrue((delivered / "matrix.json").exists())


class ContractTests(unittest.TestCase):
    def test_outcome_columns_match_template(self):
        header = (ROOT / "templates" / "bid-outcome-log.csv").read_text().splitlines()[0].split(",")
        self.assertEqual(header, COLUMNS)

    def test_packaged_schema_matches_template(self):
        a = json.loads((ROOT / "templates" / "compliance-matrix.schema.json").read_text())
        b = json.loads((ROOT / "src" / "bf" / "schemas" / "compliance-matrix.schema.json").read_text())
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
