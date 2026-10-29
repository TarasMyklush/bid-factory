"""The client's bid library: records, pseudonymisation and retrieval.

Layout of a library directory (it lives in the client's tenant; we read it, we do not copy it):

    <library>/records/*.json   one record object, or a list of records, per file
    <library>/pricing.json     optional default pricing sheet (a per-bid pricing.json in the tender dir wins)

Record fields: id, type, title, summary (required); text, valid_until, tags, permission, figures, role, source.
Person records are pseudonymised on load. Identity documents are never loaded; they are listed for
attachment at submission by the client.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from .util import parse_date, read_json, tokenize

RECORD_TYPES = {
    "company", "registration", "certification", "project", "product", "partner", "person",
    "policy", "boilerplate", "financial", "form", "commercial", "identity",
}
PERMISSIONS = {"public", "on_request", "no"}
PII_FIELDS = ("name", "full_name", "email", "phone", "mobile", "passport_number", "national_id",
              "iqama", "emirates_id", "address", "date_of_birth")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\w)\+?\d[\d\s()-]{7,}\d(?!\w)")


class LibraryError(ValueError):
    pass


@dataclass
class Record:
    id: str
    type: str
    title: str
    summary: str
    text: str = ""
    valid_until: date | None = None
    tags: list[str] = field(default_factory=list)
    permission: str = "public"
    figures: dict[str, Any] = field(default_factory=dict)
    role: str | None = None
    source: str | None = None

    def corpus(self) -> str:
        return " ".join([self.title, self.title, self.summary, self.text, " ".join(self.tags), " ".join(self.tags)])

    def brief(self, text_limit: int = 1200) -> dict[str, Any]:
        out = {"id": self.id, "type": self.type, "title": self.title, "summary": self.summary}
        if self.text:
            out["text"] = self.text[:text_limit]
        if self.valid_until:
            out["valid_until"] = self.valid_until.isoformat()
        if self.figures:
            out["figures"] = self.figures
        if self.type == "project":
            out["permission"] = self.permission
        return out


def content_tokens(text: str) -> list[str]:
    """Retrieval tokens. Short bare numbers ('1', '90', '24') match everything and are dropped."""
    return [t for t in tokenize(text) if not (t.isdigit() and len(t) <= 3)]


_REMOVED = "[contact removed]"


def _scrub(text: str, names: list[str], contacts: list[str], token: str) -> str:
    """Names become the role token. Contact details are removed with the sentence that carried them."""
    out = text or ""
    for c in sorted((x for x in contacts if x and len(x) >= 3), key=len, reverse=True):
        out = re.sub(re.escape(c), _REMOVED, out, flags=re.IGNORECASE)
    out = _EMAIL.sub(_REMOVED, out)
    out = _PHONE.sub(_REMOVED, out)
    for s in sorted((x for x in names if x and len(x) >= 3), key=len, reverse=True):
        out = re.sub(re.escape(s), token, out, flags=re.IGNORECASE)
    sentences = re.split(r"(?<=[.!?])\s+", out.strip())
    return " ".join(s for s in sentences if _REMOVED not in s).strip()


def _pseudonymise(raw: dict[str, Any]) -> dict[str, Any]:
    role = raw.get("role") or "Staff member"
    token = f"{role} ({raw['id']})"
    names: list[str] = []
    contacts: list[str] = []
    for key in PII_FIELDS:
        value = raw.get(key)
        if not isinstance(value, str):
            continue
        if key in ("name", "full_name"):
            # Strip annotations like "(fictional)" and also catch the bare name and its parts.
            bare = re.sub(r"\s*\([^)]*\)", "", value).strip()
            names += [value, bare] + [p for p in re.split(r"\s+", bare) if len(p) >= 4]
        else:
            contacts.append(value)
    clean = {k: v for k, v in raw.items() if k not in PII_FIELDS}
    clean["title"] = token
    clean["summary"] = _scrub(raw.get("summary", ""), names, contacts, token)
    clean["text"] = _scrub(raw.get("text", ""), names, contacts, token)
    clean["role"] = role
    return clean


class Library:
    def __init__(self, records: list[Record], attach_at_submission: list[dict[str, str]],
                 pricing: dict[str, Any] | None, root: Path | None = None):
        self.records = {r.id: r for r in records}
        self.attach_at_submission = attach_at_submission
        self.pricing = pricing
        self.root = root
        self._build_index()

    @classmethod
    def load(cls, root: str | Path) -> "Library":
        root = Path(root)
        rec_dir = root / "records"
        if not rec_dir.is_dir():
            raise LibraryError(f"library has no records/ directory: {root}")
        records: list[Record] = []
        attach: list[dict[str, str]] = []
        seen: set[str] = set()
        for path in sorted(rec_dir.glob("*.json")):
            data = read_json(path)
            items = data if isinstance(data, list) else [data]
            for raw in items:
                for key in ("id", "type", "title"):
                    if not raw.get(key):
                        raise LibraryError(f"{path.name}: record missing '{key}'")
                rid, rtype = str(raw["id"]), str(raw["type"])
                if rid in seen:
                    raise LibraryError(f"duplicate record id {rid} ({path.name})")
                seen.add(rid)
                if rtype not in RECORD_TYPES:
                    raise LibraryError(f"{rid}: unknown record type '{rtype}'")
                if rtype == "identity":
                    # Tier C: never indexed or sent anywhere. The client attaches it at submission.
                    attach.append({"id": rid, "title": "Identity document (attach from client tenant)"})
                    continue
                if not raw.get("summary"):
                    raise LibraryError(f"{rid}: record missing 'summary'")
                if rtype == "person":
                    raw = _pseudonymise(raw)
                permission = raw.get("permission", "public")
                if permission not in PERMISSIONS:
                    raise LibraryError(f"{rid}: permission must be one of {sorted(PERMISSIONS)}")
                records.append(Record(
                    id=rid, type=rtype, title=str(raw["title"]), summary=str(raw["summary"]),
                    text=str(raw.get("text", "")), valid_until=parse_date(raw.get("valid_until")),
                    tags=[str(t) for t in raw.get("tags", [])], permission=permission,
                    figures=dict(raw.get("figures", {})), role=raw.get("role"), source=raw.get("source"),
                ))
        pricing_path = root / "pricing.json"
        pricing = read_json(pricing_path) if pricing_path.exists() else None
        return cls(records, attach, pricing, root)

    def get(self, rid: str) -> Record | None:
        return self.records.get(rid)

    def by_type(self, *types: str) -> list[Record]:
        return [r for r in self.records.values() if r.type in types]

    # Retrieval: idf-weighted share of the query's content words found in the record, in [0, 1].
    def _build_index(self) -> None:
        self._tokens: dict[str, set[str]] = {rid: set(content_tokens(r.corpus())) for rid, r in self.records.items()}
        df: Counter[str] = Counter()
        for toks in self._tokens.values():
            df.update(toks)
        n = max(len(self._tokens), 1)
        self._idf = {t: math.log(1 + n / (1 + c)) for t, c in df.items()}
        self._default_idf = math.log(1 + n)

    def coverage(self, query: str, rid: str) -> tuple[float, list[str]]:
        q = set(content_tokens(query))
        if not q:
            return 0.0, []
        toks = self._tokens.get(rid, set())
        shared = q & toks
        total = sum(self._idf.get(t, self._default_idf) for t in q)
        got = sum(self._idf.get(t, self._default_idf) for t in shared)
        ranked = sorted(shared, key=lambda t: -self._idf.get(t, self._default_idf))
        return (got / total if total else 0.0), ranked

    def search(self, query: str, k: int = 5, prefer: tuple[str, ...] = ()) -> list[tuple[Record, float, list[str]]]:
        scored = []
        for rid, rec in self.records.items():
            cov, shared = self.coverage(query, rid)
            if cov <= 0:
                continue
            boost = 1.25 if prefer and rec.type in prefer else 1.0
            scored.append((rec, min(cov * boost, 1.0), shared))
        scored.sort(key=lambda x: (-x[1], x[0].id))
        return scored[:k]
