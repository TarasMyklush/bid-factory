import json
import unittest
from pathlib import Path

from bf.documents import load_document
from bf.draft import draft_all
from bf.extract import clauses_to_json, extract_clauses
from bf.library import Library, Record
from bf.matrix import MatrixError, build_matrix, check_turnover, validate
from bf.models import FakeModel
from bf.review import review
from bf.util import read_json

from .helpers import LIBRARY, TENDER, TempDirCase

TENDER_META = {**read_json(TENDER / "tender.json"), "data_tier": "A"}


def build(lib=None, model=None):
    lib = lib or Library.load(LIBRARY)
    clauses = clauses_to_json(extract_clauses([load_document(TENDER / "rfp.md")]))
    return clauses, build_matrix("test-run", TENDER_META, clauses, lib, lib.pricing, model), lib


def row(matrix, needle):
    return next(r for r in matrix["rows"] if needle in r["text"])


class MatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.clauses, cls.m, cls.lib = build()

    def test_schema_valid(self):
        validate(self.m)
        with self.assertRaises(MatrixError):
            validate({"run_id": "x"})

    def test_planted_gaps_are_caught(self):
        iso27001 = row(self.m, "ISO/IEC 27001")
        self.assertEqual(iso27001["status"], "gap")
        self.assertIn("expire", iso27001["risk_note"])
        lc = row(self.m, "local content score of 40%")
        self.assertEqual(lc["status"], "gap")
        self.assertIn("32%", lc["risk_note"])
        projects = row(self.m, "three similar projects")
        self.assertEqual(projects["status"], "gap")
        self.assertIn("2 citable", projects["risk_note"])
        self.assertIn("PRJ-003", projects["gap_action"])
        self.assertNotIn("PRJ-003", [e["library_id"] for e in projects["evidence"]])

    def test_facts_that_meet_requirements(self):
        for needle in ("ISO 9001", "8 years of experience", "SAR 30 million", "Nitaqat", "Saudi nationals",
                       "Commercial Registration"):
            self.assertEqual(row(self.m, needle)["status"], "answered", needle)

    def test_expiry_soon_and_missing_annex_are_partial(self):
        gosi = row(self.m, "GOSI")
        self.assertEqual(gosi["status"], "partial")
        self.assertIn("REG-004", gosi["risk_note"])
        forms = row(self.m, "Annex C")
        self.assertEqual(forms["status"], "partial")
        self.assertIn("Annex C", forms["gap_action"])

    def test_rule_categories(self):
        self.assertEqual(row(self.m, "Liquidated damages")["status"], "client_decision")
        self.assertEqual(row(self.m, "submitted electronically")["owner"], "bid_factory")
        self.assertEqual(row(self.m, "evaluated out of 100 points")["status"], "not_applicable")

    def test_summary(self):
        s = self.m["summary"]
        self.assertEqual(s["mandatory_gaps"], 3)
        self.assertEqual(s["go_no_go"]["recommendation"], "no_go")
        self.assertEqual(s["scored_points_available"], 100)
        self.assertEqual(s["total"], len(self.clauses))
        self.assertTrue(all(r.get("gap_deadline") for r in self.m["rows"] if r["status"] == "gap"))

    def test_turnover_below_requirement(self):
        lib = Library([Record(id="CO-9", type="company", title="Co", summary="Co.",
                              figures={"annual_turnover": 20_000_000, "turnover_currency": "SAR"})], [], None)
        j = check_turnover("an annual turnover of not less than SAR 30 million", lib)
        self.assertEqual(j.status, "gap")
        j = check_turnover("an annual turnover of not less than AED 10 million", lib)
        self.assertEqual(j.status, "partial")


class ModelPathTests(TempDirCase):
    def test_invented_evidence_is_dropped(self):
        def responder(task, system, user, schema):
            payload = json.loads(user)
            return {"judgements": [{"clause_id": c["clause_id"], "status": "answered", "evidence_ids": ["FAKE-999"],
                                    "relevance": "made up", "gap_action": "", "risk_note": ""}
                                   for c in payload["clauses"]]}

        model = FakeModel(responder)
        _, m, _ = build(model=model)
        judged = [r for r in m["rows"] if r["judged_by"] == "model"]
        self.assertTrue(judged)
        for r in judged:
            self.assertEqual(r["status"], "partial")
            self.assertEqual(r["evidence"], [])
            self.assertIn("FAKE-999", r["risk_note"])

    def test_model_draft_is_validated_and_reviewed(self):
        clauses, m, lib = build()

        def responder(task, system, user, schema):
            payload = json.loads(user)
            title = payload["section_title"]
            first = payload["requirements"][0]["id"]
            body = (f"## {title}\n\n### {first}: answer\n\n> quoted\n\n"
                    "We have 500 certified engineers on site.\n\n"
                    "Our platform is ITIL 4 aligned [LIB:NOPE-1].\n")
            if task == "draft_commercial":
                body += "\nThe total price is SAR 9,999,999 [PRICING].\n"
            return body

        out = self.tmp / "sections"
        index = draft_all(out, m, lib, lib.pricing, FakeModel(responder))
        self.assertTrue(any("NOPE-1" in s["invalid_citations"] for s in index["sections"]))
        solution = next(s for s in index["sections"] if s["key"] == "solution")
        text = (out / solution["file"]).read_text()
        for rid in solution["rows"]:  # rows the model skipped are appended, never dropped
            self.assertRegex(text, rf"(?m)^### {rid}\b")
        result = review(m, clauses, lib, out, index, lib.pricing)
        codes = {f["code"] for f in result["findings"] if f["severity"] == "blocking"}
        self.assertTrue({"B1", "B2", "C1", "A2"} <= codes, codes)
        c1 = [f for f in result["findings"] if f["code"] == "C1"]
        self.assertTrue(any("9999999" in f["message"] for f in c1))

    def test_non_resident_model_use_on_tier_b_is_flagged(self):
        clauses, m, lib = build()
        out = self.tmp / "sections"
        index = draft_all(out, m, lib, lib.pricing)
        log = self.tmp / "calls.jsonl"
        log.write_text(json.dumps({"task": "draft_solution", "tier": "B", "provider": "anthropic"}) + "\n")
        result = review(m, clauses, lib, out, index, lib.pricing, model_log=log)
        self.assertIn("F1", {f["code"] for f in result["findings"]})


class RulesDraftTests(TempDirCase):
    def test_rules_draft_is_fully_cited_and_free_of_pii(self):
        clauses, m, lib = build()
        out = self.tmp / "sections"
        index = draft_all(out, m, lib, lib.pricing)
        result = review(m, clauses, lib, out, index, lib.pricing)
        self.assertEqual([f for f in result["findings"] if f["code"] in ("B1", "B2", "B3", "B5", "C1")], [])
        allt = "\n".join(p.read_text() for p in Path(out).glob("*.md"))
        self.assertNotIn("Khalid", allt)
        self.assertNotIn("@", allt)
        self.assertIn("has 10 years in business", allt)
        self.assertNotIn("[LIB:PRJ-003]", allt)
        self.assertNotIn("Contact", allt)


if __name__ == "__main__":
    unittest.main()
