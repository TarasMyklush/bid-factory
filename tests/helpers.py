"""Shared test helpers. All fixtures are synthetic; no client data is used anywhere in the tests."""
from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bf import cli

FIXTURES = Path(__file__).parent / "fixtures"
TENDER = FIXTURES / "tender_sa"
LIBRARY = FIXTURES / "library_falcon"
CLEAN_ENV = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "BF_TIER_B_URL", "BF_MODEL")}


def run_cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with mock.patch.dict(os.environ, CLEAN_ENV, clear=True), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(list(argv))
    return code, out.getvalue(), err.getvalue()


def make_pdf(lines: list[str]) -> bytes:
    """A minimal one-page PDF with Helvetica text, built by hand so tests need no PDF writer."""
    content = "BT /F1 11 Tf 50 750 Td 14 TL " + " ".join(f"({line}) Tj T*" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        "/Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = b"%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


class TempDirCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="bf-test-"))
        self.runs = self.tmp / "runs"
        env = mock.patch.dict(os.environ, CLEAN_ENV, clear=True)
        env.start()
        self.addCleanup(env.stop)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def only_run(self) -> Path:
        runs = sorted(self.runs.iterdir())
        self.assertEqual(len(runs), 1)
        return runs[0]

    def copy_library(self, edits: dict[str, dict] | None = None) -> Path:
        """Copy the fixture library and apply {record_id: {field: value}} edits."""
        dest = self.tmp / "library"
        shutil.copytree(LIBRARY, dest)
        for path in (dest / "records").glob("*.json"):
            data = json.loads(path.read_text())
            changed = False
            for rec in data:
                if edits and rec["id"] in edits:
                    for k, v in edits[rec["id"]].items():
                        if isinstance(v, dict) and isinstance(rec.get(k), dict):
                            rec[k].update(v)
                        else:
                            rec[k] = v
                    changed = True
            if changed:
                path.write_text(json.dumps(data, indent=2))
        return dest

    def write_tender(self, text: str, meta: dict | None = None) -> Path:
        d = self.tmp / "tender"
        d.mkdir()
        (d / "rfp.md").write_text(text)
        base = json.loads((TENDER / "tender.json").read_text())
        base.update(meta or {})
        (d / "tender.json").write_text(json.dumps(base))
        return d
