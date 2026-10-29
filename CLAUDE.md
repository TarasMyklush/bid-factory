# Bid Factory: working rules

Read SPEC.md and docs/data-protection.md before changing behaviour. The spec is the source of truth; if code and
spec disagree, fix one of them in the same change and log it in docs/decisions.md.

## Non-negotiable rules

- **No client data in this repository.** Only synthetic fixtures under tests/fixtures. Never commit tender
  documents, bid libraries, pricing sheets, run directories or outcome logs. Cloud sessions run outside the UAE and
  Saudi Arabia; under our own data rules only public or synthetic material belongs there.
- **Evidence-bound drafting.** Every factual sentence in a draft cites `[LIB:<id>]` or `[PRICING]`, or is replaced
  by `[CLIENT INPUT NEEDED: ...]`. Never weaken the citation validator, the unsupported-claim check (B2) or the
  number check (C1) to make a test pass.
- **Tiers are enforced in code.** Tier C is never processed. Tier B never reaches a non-resident model
  (`AnthropicModel` is Tier A only). The tier can be raised, never lowered. Any change to `tiers.py` or
  `models.select_model` needs a test for the refusal path.
- **No prompt or completion content in logs.** `model-calls.jsonl` holds task, tier, provider, model and token counts.
- **The client submits.** The toolkit never holds portal credentials or submits anything.
- **Deterministic first.** Facts that can be checked in code (expiry dates, thresholds, counts, numbers, annexes)
  are checked in code. Model output is post-validated and can only lower a status, never invent evidence.

## Commands

```bash
python3 -m venv .venv && .venv/bin/pip install -e '.[anthropic]'
.venv/bin/python -m unittest discover -s tests -t .
.venv/bin/bf run tests/fixtures/tender_sa --library tests/fixtures/library_falcon --client demo --runs-dir /tmp/bf-runs
```

Tests must pass without network or API keys. Model paths are tested with `FakeModel` and mocked clients.

## Layout

- `src/bf/cli.py` commands; `runs.py` run workspace and stage order
- `tiers.py` data tier classification; `models.py` model clients and the tier-enforcing router
- `documents.py` loaders; `extract.py` clause extraction; `library.py` bid library, pseudonymisation, retrieval
- `matrix.py` compliance matrix and deterministic checks; `gaps.py` gap report
- `draft.py` evidence-bound drafting; `pack.py` pack assembly; `review.py` automated review; `outcome.py` outcome log
- `schemas/compliance-matrix.schema.json` must stay identical to `templates/compliance-matrix.schema.json` (tested)

## Style

Python 3.11+, standard library first. New runtime dependencies need a reason in docs/decisions.md.
