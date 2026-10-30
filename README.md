# Bid Factory

A done-for-you tender and bid response service for mid-sized suppliers bidding on Saudi and UAE government and semi-government tenders. Agents do the drafting, compliance mapping and gap analysis; one human reviews; the client signs and submits under its own supplier registration.

Status: **MVP toolkit built, untested on a live model or a real tender.** The `bf` toolkit runs the whole per-bid workflow from SPEC.md section 4.2, from a browser (`bf ui`) or the command line, on deterministic rules, and routes model calls by data tier when a model is configured. The test suite runs on synthetic fixtures only.

## Why this exists

- Saudi government tenders on Etimad reached SAR 336 billion in 2024; SMEs took roughly a fifth of awards. The UAE federal supplier register alone has about 25,000 suppliers, with separate Dubai and Abu Dhabi portals.
- Most suppliers that bid five or more times a year cannot justify a bid manager (AED 15,000 to 30,000 a month) and lose on compliance, not on capability.
- The global RFP software (Loopio, Responsive, Arphie, Tribble, AutogenAI) is English-first, seat-priced and assumes the client has a proposal team. The one Gulf agency with public prices sells fixed-fee writing with no success fee and no measurement.
- Bid work needs no professional licence. The supplier signs. Every regulated service business we looked at before this one required a licensed human at the centre; this one does not.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[anthropic]'
.venv/bin/bf ui --demo
```

`bf ui` opens the interface in your browser with a fictional tender and supplier library loaded. Choose **New bid**,
pick the sample tender, and start. The same run from the command line, and the tests:

```bash
.venv/bin/bf run tests/fixtures/tender_sa --library tests/fixtures/library_falcon --client demo --runs-dir /tmp/bf-runs
.venv/bin/python -m unittest discover -s tests -t .
```

The demo tender and supplier are fictional. The run finishes with exit code 1 on purpose: the supplier's ISO 27001
certificate expires before the deadline, its local content score is 32% against 40% required, and only two of its
three similar projects may be cited. The gap report, the draft and the pack all say so.

## The interface

`bf ui [--workspace DIR] [--libraries DIR]` serves a web interface from this machine. Nothing is hosted and nothing
loads from the internet, so it runs on an air-gapped company laptop with no extra dependencies.

| Screen | What the bid writer does there |
|---|---|
| Bids | Every tender in the workspace, nearest deadline first, with recommendation, review state and progress |
| New bid | Drop the tender documents (details fill in from `tender.json`), pick the client library, declare how sensitive the documents are, see which model will be used, start. Progress is live |
| Overview | Go, no-go or go-with-partner with the reasons, scored points evidenced, data tier and why, next steps |
| Requirements | Every extracted clause with filters and search; a side panel shows the source, the evidence records with expiry against the deadline, and reviewer notes |
| Gaps | Client actions and our actions, each with the action and the date it must close by; the gap report to send the client |
| Draft | Each section with cited records you can click, placeholders highlighted; edit and save, which forces a rebuild of the pack and review |
| Review | Automated findings linked to the requirement or section, and the human sign-off checklist, which unlocks only when the review passes |
| Pack | The files, download one or all, the submission checklist, and what the client attaches from its own systems |
| Close out | Log the outcome, then deliver to the client folder and delete the workspace and uploaded documents |
| Libraries | Each client's records as the toolkit sees them, pseudonymised, with expired and expiring evidence flagged |

The workspace (default `~/BidFactory`) holds uploaded tenders, run workspaces, deliveries and the outcome log. It holds
client data, so keep it out of this repository. Access needs the one-time link printed at start-up. See
[docs/decisions.md](docs/decisions.md) for the security model.

## The commands

| Command | Output | Notes |
|---|---|---|
| `bf intake <tender-dir> --library DIR --client ID` | `runs/<run-id>/run.json` | Reads `tender.json` for buyer, reference, title, portal, country and deadline. Classifies the data tier. Tier C stops here. |
| `bf extract <run>` | `clauses.json` | Numbered clauses, bullets, requirement sentences and evaluation tables from `.md`, `.txt`, `.pdf`, `.docx` |
| `bf matrix <run> [--model ...]` | `matrix.json` | Validated against the schema. Deterministic checks first, then an optional model judgement |
| `bf gaps <run>` | `gap-report.md` | Go, no-go or go with a partner, and every gap with an action and a date |
| `bf draft <run> [--model ...]` | `sections/*.md` | Every factual sentence cites a library record or the pricing sheet |
| `bf pack <run>` | `pack/` | Checklist, matrix, technical and commercial responses as Markdown and Word, annex index. Marked NOT FOR SUBMISSION while mandatory gaps are open |
| `bf review <run>` | `review-findings.md` | Exit code 1 when anything blocks delivery. The human still signs the checklist |
| `bf log <run> --outcome ...` | outcome CSV | Columns match `templates/bid-outcome-log.csv`; the tender reference is stored as a hash |
| `bf close <run> --deliver-to DIR` | | Copies the deliverables to the client's folder and deletes the workspace |
| `bf run <tender-dir> ...` | | Intake through review in one go |
| `bf ui` | | The same workflow in the browser |

## Models and data tiers

`--model auto` (the default) picks a model the tier allows, or falls back to rules:

| Tier | Model used by `auto` | Configure |
|---|---|---|
| A, declared public | Claude, if `ANTHROPIC_API_KEY` is set; otherwise the in-country endpoint; otherwise rules | `BF_MODEL` overrides the default `claude-opus-5-5` |
| B, the default | The in-country endpoint, if configured; otherwise rules | `BF_TIER_B_URL`, `BF_TIER_B_MODEL`, `BF_TIER_B_KEY` for any OpenAI-compatible server on in-country infrastructure |
| C | Nothing. The toolkit refuses | |

`--model anthropic` on Tier B material is refused with exit code 3. See [docs/data-protection.md](docs/data-protection.md).

## The bid library

A client's library is a folder in the client's tenant with `records/*.json` and an optional `pricing.json`. The fields
are described in [templates/bid-library.md](templates/bid-library.md) and in `src/bf/library.py`; the fixture in
`tests/fixtures/library_falcon` is a complete example. Person records are pseudonymised on load. Identity documents
are never loaded and only listed for the client to attach at submission.

## How to read this repo

| File | What it is |
|---|---|
| [SPEC.md](SPEC.md) | The MVP specification: scope, offer, workflow, agent design, architecture, go-to-market, metrics, kill lines, roadmap, risks, open decisions |
| [docs/data-protection.md](docs/data-protection.md) | Data residency and protection design for UAE and Saudi work, with the legal position as of October 2026 |
| [docs/market-and-competition.md](docs/market-and-competition.md) | Market sizing and competitor notes with sources |
| [templates/bid-library.md](templates/bid-library.md) | The onboarding schema: what we collect from a client in week one |
| [templates/compliance-matrix.schema.json](templates/compliance-matrix.schema.json) | The structured output every bid run must produce |
| [templates/gap-report.md](templates/gap-report.md) | Gap report format |
| [templates/review-checklist.md](templates/review-checklist.md) | The human review gate before anything goes to the client |
| [templates/data-handling-sheet.md](templates/data-handling-sheet.md) | The one-page per-client sheet on where data is processed |
| [templates/bid-outcome-log.csv](templates/bid-outcome-log.csv) | The outcome log that decides whether this becomes a business |
| [docs/decisions.md](docs/decisions.md) | Decision log |
| [CLAUDE.md](CLAUDE.md) | Working rules for anyone, human or agent, changing the code |

## The 45-day test

Three paying clients and ten delivered bids with zero compliance disqualifications: continue. Fewer than three clients, or no measurable shortlist improvement after ten bids: stop. Details in [SPEC.md](SPEC.md#10-metrics-pass-and-kill-lines).
