# Bid Factory

A done-for-you tender and bid response service for mid-sized suppliers bidding on Saudi and UAE government and semi-government tenders. Agents do the drafting, compliance mapping and gap analysis; one human reviews; the client signs and submits under its own supplier registration.

Status: **specification only**. Nothing is built. This repository holds the MVP spec, the templates the service runs on, and the decision log.

## Why this exists

- Saudi government tenders on Etimad reached SAR 336 billion in 2024; SMEs took roughly a fifth of awards. The UAE federal supplier register alone has about 25,000 suppliers, with separate Dubai and Abu Dhabi portals.
- Most suppliers that bid five or more times a year cannot justify a bid manager (AED 15,000 to 30,000 a month) and lose on compliance, not on capability.
- The global RFP software (Loopio, Responsive, Arphie, Tribble, AutogenAI) is English-first, seat-priced and assumes the client has a proposal team. The one Gulf agency with public prices sells fixed-fee writing with no success fee and no measurement.
- Bid work needs no professional licence. The supplier signs. Every regulated service business we looked at before this one required a licensed human at the centre; this one does not.

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

## The 45-day test

Three paying clients and ten delivered bids with zero compliance disqualifications: continue. Fewer than three clients, or no measurable shortlist improvement after ten bids: stop. Details in [SPEC.md](SPEC.md#10-metrics-pass-and-kill-lines).
