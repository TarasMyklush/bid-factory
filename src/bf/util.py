"""Small shared helpers: JSON IO, hashing, text normalisation, numbers and dates."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

STOPWORDS = frozenset(
    """
    a an and are as at be been being by can could do does for from had has have how if in into is it its
    may might more most of on or other our over per such than that the their them then there these they
    this those through to under up upon was we were what when where which while who will with within
    without would you your all any each also both only own same so very via etc i e g
    """.split()
)

# Words every tender uses; they say nothing about which evidence answers a clause.
TENDER_STOPWORDS = frozenset(
    """
    bidder bidders supplier suppliers vendor vendors contractor contractors tenderer tenderers offeror
    shall must should required require requires requirement requirements mandatory provide provided providing
    submit submitted submission include including includes ensure demonstrate demonstrated evidence
    proposal proposals offer offers please describe details detailed valid hold holds authority ministry
    entity client buyer rfp tender tenders bid bids party parties applicable relevant appropriate
    """.split()
)

_NUM_RE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?![\w])")
_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "fifteen": 15, "twenty": 20,
}
_SCALE = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mn": 1e6, "million": 1e6, "bn": 1e9, "billion": 1e9}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path: str | Path, data: Any) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def slug(text: str, maxlen: int = 40) -> str:
    folded = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", folded).strip("-").lower()
    return (s[:maxlen].rstrip("-")) or "x"


def norm_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def tokenize(text: str, drop_tender_words: bool = True) -> list[str]:
    words = re.findall(r"\w+", (text or "").lower())
    out = []
    for w in words:
        if len(w) < 2 and not w.isdigit():
            continue
        if w in STOPWORDS or (drop_tender_words and w in TENDER_STOPWORDS):
            continue
        out.append(stem(w))
    return out


def stem(word: str) -> str:
    """Plural folding only: 'bonds' -> 'bond', 'policies' -> 'policy'. Keeps 'business', 'gross'."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def numbers_in(text: str) -> list[float]:
    """Every number in the text, commas removed. '4,200,000' -> 4200000.0, '99.9' -> 99.9."""
    out = []
    for m in _NUM_RE.finditer(text or ""):
        whole = m.group(1).replace(",", "")
        frac = m.group(2)
        out.append(float(f"{whole}.{frac}") if frac else float(whole))
    return out


def parse_count(token: str) -> int | None:
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    return _WORD_NUMBERS.get(token)


def parse_amount(number: str, scale: str | None = None) -> float | None:
    try:
        value = float(number.replace(",", ""))
    except ValueError:
        return None
    if scale:
        value *= _SCALE.get(scale.lower().rstrip("."), 1)
    return value


def md_cell(text: Any) -> str:
    return norm_space(str(text if text is not None else "")).replace("|", "\\|")


def first_words(text: str, limit: int = 110) -> str:
    t = norm_space(text)
    return t if len(t) <= limit else t[: limit - 1].rsplit(" ", 1)[0] + "…"


def unique(items: Iterable[Any]) -> list[Any]:
    seen, out = set(), []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
