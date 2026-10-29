"""A run: one tender for one client. All artefacts live in the run directory.

The run directory is our ephemeral workspace. Tender documents and the library are referenced by path and
hash, not copied. `bf close` delivers the artefacts and deletes the workspace.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import TierViolation
from .util import now_iso, read_json, sha256_file, write_json

STAGES = ("intake", "extract", "matrix", "gaps", "draft", "pack", "review", "log")


class RunError(RuntimeError):
    pass


@dataclass
class Run:
    dir: Path
    data: dict[str, Any]

    @classmethod
    def load(cls, run_dir: str | Path) -> "Run":
        d = Path(run_dir)
        meta = d / "run.json"
        if not meta.exists():
            raise RunError(f"not a run directory (no run.json): {d}")
        return cls(d, read_json(meta))

    def save(self) -> None:
        write_json(self.dir / "run.json", self.data)

    @property
    def id(self) -> str:
        return self.data["run_id"]

    @property
    def tier(self) -> str:
        return self.data["tender"]["data_tier"]

    @property
    def tender(self) -> dict[str, Any]:
        return self.data["tender"]

    def path(self, name: str) -> Path:
        return self.dir / name

    @property
    def model_log(self) -> Path:
        return self.dir / "model-calls.jsonl"

    def mark(self, stage: str, **info: Any) -> None:
        self.data.setdefault("stages", {})[stage] = {"at": now_iso(), **info}
        self.save()

    def require(self, *stages: str) -> None:
        if self.tier == "C":
            raise TierViolation("Tier C run: humans only. The toolkit will not process this tender.")
        done = self.data.get("stages", {})
        missing = [s for s in stages if s not in done]
        if missing:
            raise RunError(f"run {self.id}: run these stages first: {', '.join(missing)}")

    def verify_inventory(self) -> list[str]:
        """Warn if tender files changed since intake. Returns the warnings."""
        warnings = []
        root = Path(self.data["tender_dir"])
        for item in self.data.get("inventory", []):
            p = root / item["file"]
            if not p.exists():
                warnings.append(f"tender file missing since intake: {item['file']}")
            elif sha256_file(p) != item["sha256"]:
                warnings.append(f"tender file changed since intake: {item['file']}")
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        return warnings
