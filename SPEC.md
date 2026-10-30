# Bid Factory: MVP specification

Version 0.3, 29 October 2026. Owner: Taras Myklush. Status: draft for the 45-day test.

## 1. Summary

Bid Factory produces complete, compliant tender responses for mid-sized suppliers bidding on Saudi and UAE public-sector and semi-government tenders. The client forwards a tender. Within an agreed turnaround the client receives four artefacts: a compliance matrix mapping every clause to a response, a gap report naming what the client lacks, the drafted technical and commercial narrative built from the client's own bid library, and a portal-ready submission pack. A human reviews everything before it leaves. The client signs and submits under its own supplier registration.

The MVP is a service run on agents, not a software product. The only code is a small toolkit, with a command line and a local web interface for the bid writer, that turns a tender and a bid library into the four artefacts and logs the outcome. The asset being built is the per-client bid library plus the outcome data across bids, which later tells us which tender types are won on paperwork and price alone.

### Thesis, in three lines

1. Agents remove most of the drafting and clause-mapping labour in a bid. That labour is what a bid manager is paid for and what mid-sized suppliers cannot afford.
2. Bid quality is verifiable: every clause is either answered or not, and every bid is either shortlisted or not. Verifiable work is work agents can do at scale with provable quality.
3. No licence stands between us and the margin. The supplier signs. That is why this beat accounting, PRO services and audit in our earlier analysis.

## 2. Scope

### 2.1 First customer

IT and software suppliers, 20 to 300 staff, registered on at least one of: Saudi Etimad, the UAE federal Digital Procurement Platform, Dubai eSupply, Abu Dhabi government procurement, or a large semi-government buyer portal (ADNOC, Aramco, Emirates Group, telcos). They bid at least five times a year, have no dedicated bid manager, and have lost a bid in the last year on a compliance point.

Why IT and software first: paper-heavy, formulaic technical scoring, English-dominant documents, and the founder's own domain.

### 2.2 In scope for the MVP

- Public and semi-government tenders in Saudi Arabia and the UAE, in English, with Arabic cover letters and forms where the portal demands them.
- Response types: RFP and RFQ technical and commercial responses, prequalification questionnaires, vendor registration packs.
- One category (IT and software). A second category opens only after ten delivered bids.

### 2.3 Out of scope for the MVP

- Submitting on the client's behalf or holding any portal credential. The client submits.
- Pricing strategy beyond formatting the client's own numbers. We do not set prices.
- Legal review of contract terms. We flag, the client's lawyer decides.
- Arabic-only technical narratives. Translated cover material only, until an Arabic reviewer joins.
- Any tender classified above "restricted" or any buyer whose confidentiality clause prohibits third-party processing. See [docs/data-protection.md](docs/data-protection.md).
- Building a SaaS product, a client portal, or integrations with Etimad or any buyer system.

## 3. The offer and pricing

| Element | Price | What it covers |
|---|---|---|
| Onboarding | AED 5,000 one-off | Bid library build in one week: past bids, case studies, CVs, certificates, licences, local-content and Saudisation facts, pricing norms, boilerplate |
| Per bid, small | AED 3,000 | Up to 40 scored clauses, one lot, standard forms |
| Per bid, medium | AED 5,000 | 40 to 120 clauses, or two lots, or a technical approach section over 15 pages |
| Per bid, large | AED 8,000 | Over 120 clauses, multiple lots, consortium or subcontractor coordination |
| Success fee | 1 to 2% of contract value, capped at AED 50,000 per award | Where the client accepts it; offered in exchange for a lower per-bid fee |
| Retainer | AED 12,000 a month | Up to four small or medium bids a month, library kept current, tender watch in the client's category |

Turnaround: five working days for small, eight for medium, twelve for large, from receipt of the complete tender pack. Rush at 50% uplift.

Payment: onboarding and per-bid fees in advance for the first three bids with any client, then 15-day terms. Success fee invoiced on award notification.

What the price is compared against in the client's head: a bid manager at AED 15,000 to 30,000 a month, the one Dubai agency at AED 2,500-plus per bid with no matrix and no measurement, and the client's own staff writing bids at night.

## 4. The workflow

### 4.1 Onboarding, one week

1. Kick-off call, 60 minutes. Capture the client's categories, portals, target buyers, win and loss history, and the names of the people who will sign.
2. Collect the bid library inputs listed in [templates/bid-library.md](templates/bid-library.md). The client uploads to its own tenant and grants scoped access.
3. Agents normalise the library: one record per case study, CV, certificate, product, partner, policy, and boilerplate section, each with a source file reference, a date, and an owner. Personal data is pseudonymised at this step; see section 7.
4. Produce the library gap report: certificates about to expire, missing ISO or CMMI evidence, local-content certificate status, Saudisation standing, missing reference letters.
5. Client signs the data handling sheet and the engagement letter.

### 4.2 Per bid, the run

1. **Intake.** Client forwards the tender pack. We log it, classify the data tier, and confirm the deadline and the portal format.
2. **Triage, same day.** Agents produce a one-page go or no-go note: mandatory eligibility clauses the client fails, local-content or Saudisation thresholds, required certifications, bond and insurance requirements, and the evaluation weighting. The client decides to proceed within 24 hours. No fee for a no-go recommendation on a retainer; a flat AED 500 otherwise.
3. **Compliance matrix.** Every clause, requirement and evaluation criterion extracted into the schema in [templates/compliance-matrix.schema.json](templates/compliance-matrix.schema.json), each with a response owner (us, client, partner), a status, the library evidence that answers it, and a score weight where the tender publishes one.
4. **Gap report.** Everything the library cannot answer, grouped into: must-have and missing, must-have and expiring, scored and weak, and nice-to-have. Each gap has a proposed action and a deadline. Format in [templates/gap-report.md](templates/gap-report.md).
5. **Draft.** Technical approach, methodology, team, past performance, implementation plan, risk register, SLAs, and the commercial narrative, all drafted from library evidence only. Every factual claim carries a reference to a library record. Numbers come only from the client's pricing sheet. Anything without a source is marked `[CLIENT INPUT NEEDED]`, never invented.
6. **Pack.** Assembled in the buyer's template and order, forms pre-filled, annexes indexed, file names per the portal's rules, a submission checklist on top.
7. **Human review.** The review gate in [templates/review-checklist.md](templates/review-checklist.md). Target: under eight human hours per bid by bid ten. Nothing goes to the client without a signed-off checklist.
8. **Client sign-off and submission.** The client's named signatory approves, signs, and submits. We record the submission timestamp and confirmation.
9. **Outcome.** Shortlisting, clarification rounds, award or loss, and the buyer's scoring where released, logged in [templates/bid-outcome-log.csv](templates/bid-outcome-log.csv). Debrief requests sent on every loss.

### 4.3 Clarification rounds

Buyer questions during evaluation are handled as mini-runs: matrix of questions, drafted answers from the library, human review, client sends. Included in the per-bid fee for up to two rounds.

## 5. Agent design

### 5.1 Principles

- **Evidence-bound generation.** The drafting agent may only assert what a library record supports, and must cite the record. This is the rule that makes the output reviewable in hours rather than days and protects the client from an invented certification in a government bid.
- **Schema first.** The compliance matrix is a structured object validated against the schema before any prose is written. Prose is generated per matrix row, not per document.
- **Deterministic where possible.** Clause extraction, numbering, cross-references, file naming and checklist generation are code, not model calls, wherever the tender format allows.
- **Human at the gate, not in the loop.** Agents run end to end; the human reviews the finished pack against the checklist. During the first ten bids the human reads everything. After that, sampling is allowed only on sections with a clean record.

### 5.2 Agents and tools

| Agent | Input | Output | Notes |
|---|---|---|---|
| Intake classifier | Tender pack | Data tier, portal, deadline, document inventory | Rules plus one model call for tier edge cases |
| Clause extractor | Tender documents | Candidate clauses with location references | Model call per document section; dedup and numbering in code |
| Matrix builder | Clauses, library index | Compliance matrix rows with evidence links and status | Retrieval over the library; status `answered`, `partial`, `gap`, `client_decision` |
| Gap analyst | Matrix | Gap report | Groups and prioritises; proposes actions with deadlines |
| Section drafter | Matrix row group, library records, buyer template | Drafted section with inline evidence references | One call per section; style guide per buyer |
| Pack assembler | Sections, forms, annexes | Ordered pack, filenames, checklist | Code; Word and PDF via templates |
| Reviewer assistant | Pack, matrix | Review findings: unsupported claims, unanswered clauses, inconsistencies, number mismatches | Second model pass with a different prompt; findings go to the human, who decides |

Model use: Claude for Tier A work through an API with no-training and zero-retention terms. An in-country open-weight model for Tier B work. No model for Tier C. Tiers defined in [docs/data-protection.md](docs/data-protection.md).

### 5.3 Verification

- Matrix completeness: 100% of extracted clauses have a status before drafting starts. The run halts otherwise.
- Evidence coverage: every factual sentence in the draft resolves to a library record or is tagged for client input. Measured by the reviewer assistant and spot-checked by the human.
- Number integrity: every number in the commercial narrative matches the pricing sheet. Code check, not a model check.
- Form completeness: every mandatory form field is filled or tagged. Code check.
- Regression: each human correction is stored as a test case against the client's library and rerun on the next bid.

### 5.4 What agents do not do in the MVP

Decide go or no-go. Set prices. Sign anything. Submit anything. Contact the buyer. Translate the technical narrative into Arabic for scoring.

## 6. Architecture

The MVP is intentionally thin.

```
client tenant (SharePoint or Google Drive, in-region)
  └── bid-library/            records/*.json, pricing.json, source documents, owned by client
  └── bids/<tender-id>/       tender pack and tender.json in, artefacts out

our side (per run, local workspace, deleted at close)
  bf intake   <tender-dir>    -> run.json (tier, portal, deadline, file hashes)
  bf extract  <run>           -> clauses.json
  bf matrix   <run>           -> matrix.json (validated against schema)
  bf gaps     <run>           -> gap-report.md
  bf draft    <run>           -> sections/*.md with evidence refs
  bf pack     <run>           -> pack/ (md, docx, csv, checklist, manifest)
  bf review   <run>           -> review-findings.md, review.json
  bf log      <run> <outcome> -> appends to the outcome log CSV
  bf close    <run>           -> copies deliverables to the client folder, deletes the workspace
  bf run      <tender-dir>    -> intake through review
  bf ui                       -> the same workflow in a browser on the operator's machine
```

- Language: Python 3.11+. One package, one CLI, no hosted server, no database beyond JSON and the CSV log.
- Interface: `bf ui` serves a single-user web interface from the operator's machine, standard library only, with
  every asset bundled so it runs air-gapped. It runs the same CLI stages as subprocesses, so every tier rule
  applies unchanged. It adds the human review sign-off, section editing with a forced re-review, and reviewer
  notes on matrix rows. See docs/decisions.md.
- Library retrieval: idf-weighted lexical matching over normalised records, computed in memory per run from the
  client's library. No embedding service, so no library text leaves for indexing. See docs/decisions.md.
- Tender documents and the library are referenced by path and hash, never copied into the workspace. A change to a
  tender file after intake is reported at every later stage.
- Without a configured model, every stage runs on deterministic rules. The output is fully cited but reads as a
  structured answer list rather than prose; a model is what turns it into a narrative.
- Templates: per-buyer document templates and style notes in `templates/buyers/` as they are learned.
- Secrets and client data: never in this repository. The repository holds code, schemas, templates and synthetic
  fixtures only.
- Observability: every model call logged with tier, provider, model, token counts and run id; no prompt or
  completion content is logged for any tier.

Explicitly deferred: hosted web app, client login, portal integrations, payment integration, multi-user roles, Arabic generation.

## 7. Data residency and protection

Full design in [docs/data-protection.md](docs/data-protection.md). The rules that bind the MVP:

1. Every tender is tiered at intake. Tier A: public tender text and the client's own narrative. Tier B: material under a confidentiality clause or marked restricted. Tier C: classified or prohibited from third-party processing.
2. Tier A may use a frontier model via API under no-training and zero-retention terms with standard contractual clauses on file. Tier B uses an in-country model on sovereign infrastructure in that country, or runs inside the client's tenant. Tier C is handled by humans only and never uploaded.
3. Personal data is minimised before processing: CVs pseudonymised, identity documents never leave the client's tenant, the matrix references documents by id.
4. The client's library stays in the client's tenant. We are a processor under a data processing agreement; nothing accumulates on our side beyond the outcome log and the regression tests, which hold no personal data.
5. Saudi government tenders are served through a Saudi entity or a licensed Saudi partner that signs SDAIA's standard contractual clauses. Serving Saudi government data purely from the UAE is refused.
6. Every client receives and signs the data handling sheet in [templates/data-handling-sheet.md](templates/data-handling-sheet.md) before the first run.

## 8. Go-to-market for the first 45 days

1. **Warm list.** Suppliers known from the founder's own bid and RFP work. Target: five conversations in week one, two paying by week three.
2. **Tender-watch outreach.** Daily scan of Etimad and the UAE portals for IT and software tenders. For each, identify three to five registered suppliers in that category that have no visible bid function and send a one-page note: the tender, its three hardest compliance clauses, and an offer to run the triage free.
3. **Partners.** Saudi regional-headquarters and company-setup firms, which meet foreign suppliers the week they decide to bid; ICV and local-content certifiers; a Big Four alumni network for referrals.
4. **Proof asset.** After ten bids, publish an anonymised note on where IT suppliers lose Gulf tenders on compliance. This replaces advertising.

What we do not do: paid ads, a website beyond one page, a free tier, discounts below the price table.

## 9. The pitch

"You lost your last tender on a compliance point, not on capability. We turn your tender into a clause-by-clause matrix, tell you what you are missing while there is still time to fix it, draft the response from your own evidence, and hand you a pack ready for the portal. You sign and submit. Fixed fee per bid, and if you want, a success fee that means we win when you win."

Objections and answers in the sales notes, to be added after the first five conversations.

## 10. Metrics, pass and kill lines

Measured at day 45 from the first paid engagement.

| Metric | Pass | Kill |
|---|---|---|
| Paying clients | 3 or more | Under 3 |
| Bids delivered | 10 or more | Under 6 |
| Compliance disqualifications on delivered bids | 0 | Any |
| Human review hours per bid, bid 6 to 10 | Under 8 | Over 16 |
| Shortlist rate vs the client's own prior 12 months | Higher on at least half the clients with history | No client improves |
| Repeat rate | 2 of 3 clients commission a second bid | None do |
| Unsupported claims found at review, per bid | Falling across bids | Flat or rising |

Secondary: turnaround met, clarification-round volume, gap-report items the client acted on, success-fee acceptance rate.

Kill means stop, write up, and return to the alternatives in the research. It does not mean iterate.

## 11. Roadmap after the test

1. **Months 2 to 4.** Second category (facilities management or training and consultancy). Arabic reviewer. Success fee as the default pricing. Retainer clients to five.
2. **Months 4 to 9.** Outcome data across fifty bids. Identify tender types won on paperwork and price alone with low delivery complexity.
3. **Months 9 to 18.** Register as a supplier in both countries and bid as prime on those tender types, subcontracting delivery to existing clients. This is where the business stops earning fees and starts earning contract margin.
4. **Optional.** Productise the matrix and gap tooling for in-house bid teams at larger suppliers, priced per bid, once the service has proven the output.

## 12. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| An invented or unsupported claim reaches a government bid | Disqualification, blacklisting, reputational end | Evidence-bound generation, reviewer pass, human gate, client sign-off on every claim |
| Buyer confidentiality clause prohibits third-party processing | Breach by the client, liability to us | Tier C classification at intake, refusal, clause check in triage |
| Client submits late or wrong | Blamed on us | Submission checklist with timestamps, client signs it, we never hold credentials |
| Thin demand in IT and software | Fail the test | Warm list first; second category ready |
| Price pressure from the client's own ChatGPT | Margin | Sell the matrix, the gap report and the measured record, not the prose |
| Saudi data rules tighten | Tier B costs rise | Saudi partner entity, in-country model path from day one |
| Key person: the founder is the reviewer | No scale | Review checklist and regression tests make the second reviewer trainable; hire at bid 20 |
| Success fee disputes | Cash and relationships | Capped, written, triggered on award letter, never on delivery |

## 13. Open decisions

- [ ] Legal entity and name. UAE mainland commercial licence versus free zone for the first entity; Saudi partner versus own entity for Saudi work.
- [ ] Success fee: offer from day one or after the first three fixed-fee bids with a client.
- [ ] Tier B model and host for Saudi and for UAE. Candidates to verify: Oracle OneCloud UAE, e& and AWS Sovereign Launchpad, Core42, Humain, Azure Saudi East once live.
- [ ] Arabic: when to add a reviewer and whether to offer Arabic technical narratives at all in year one.
- [ ] Insurance: professional indemnity level and whether buyers' tenders require it from advisers.
- [ ] Whether to take equity or revenue share in client consortiums on large bids.
- [ ] Name and brand. "Bid Factory" is a working name.

## 14. Glossary

- **Etimad:** Saudi Arabia's government procurement platform; all government entities must publish tenders there and bidders must register.
- **Local content:** Saudi scoring and eligibility weight for in-Kingdom spend, employment and ownership, administered by the Local Content and Government Procurement Authority.
- **Saudisation, Nitaqat:** Saudi nationality quotas by sector and firm size that affect eligibility and scoring.
- **ICV:** In-Country Value, the UAE and Aramco programmes scoring local spend and employment, certified annually.
- **RHQ:** Saudi regional-headquarters programme; from 2024 government contracts favour firms with a licensed regional HQ in the Kingdom.
- **Tejari, eSupply, Digital Procurement Platform:** UAE buyer and government portals.
- **Tier A, B, C:** Our data-handling classes; see [docs/data-protection.md](docs/data-protection.md).
