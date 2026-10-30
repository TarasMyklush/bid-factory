# Decision log

Newest first. One entry per decision, with the alternatives rejected.

## 2026-10-29: A local web interface (`bf ui`)

Decision: add a browser interface for the bid writer, served from the operator's own machine. This reverses the
spec's "web app deferred" for an internal, single-user tool; a hosted app and client logins stay deferred.

- **Standard library server, no framework, no build step.** `http.server` plus plain ES modules and CSS, all bundled
  in the package. Rejected: Streamlit, NiceGUI, Gradio (extra wheels, websocket runtimes and telemetry to switch
  off), FastAPI with a React build (a Node toolchain for a single-user tool). Reason: it must install and run on an
  air-gapped company machine with nothing but the existing three dependencies, and load nothing from the internet.
- **The UI runs the CLI.** Each stage is a `python -m bf.cli` subprocess. Rejected: calling the stage functions in
  the server process. Reason: one implementation of every tier rule and refusal, and a crash in a stage cannot take
  the server down.
- **Security as if it were exposed.** Binds to 127.0.0.1 by default; a one-time link sets an HttpOnly, SameSite=Strict
  session cookie; the Host header is checked against an allowlist (DNS rebinding); state-changing requests need a
  custom header, a same-origin `Origin` and `Sec-Fetch-Site` (CSRF); strict CSP with `script-src 'self'`. Inline
  `style` attributes are allowed (`style-src 'unsafe-inline'`) for progress bars and widths; script stays strict and
  every value is HTML-escaped. `--host` beyond localhost prints a warning to put it behind a TLS proxy.
- **Edits force a re-review.** Saving a draft section marks the review stale and clears sign-off; sign-off is refused
  until the pack and review are rebuilt and pass. A full re-check re-drafts and discards edits; reviewer notes on
  matrix rows are kept across re-checks.
- **Closing deletes uploaded tender documents** from the workspace as well as the run, matching the
  delete-at-close rule for workspaces.
- **The sign-off checklist is a copy of templates/review-checklist.md** kept in step by a test.

## 2026-10-29: MVP toolkit choices

Decisions taken while building the `bf` toolkit, where the spec left room or the build deviated:

- **Lexical retrieval instead of embeddings.** Idf-weighted matching with plural folding, computed per run.
  Rejected: an embedding API. Reason: it would send every library record to a third party for indexing, which
  breaks the Tier B rule for most clients; libraries are small enough that lexical matching plus deterministic
  checks is adequate. Revisit when libraries pass a few hundred records.
- **Deterministic checks before any model.** Certificate names and expiry, turnover, local content, Saudisation,
  Nitaqat band, years in business, project counts and annexes are checked in code. A model judgement can only
  choose among retrieved candidates; invented record ids are dropped and an "answered" without valid evidence
  becomes "partial".
- **Rules mode is a complete fallback.** Every stage runs without a model. The draft is a fully cited answer
  list rather than prose. This keeps Tier B work possible before an in-country model is contracted.
- **In-country model through any OpenAI-compatible endpoint.** Rejected: a vendor-specific SDK. Reason: the
  candidate hosts (vLLM on sovereign cloud, Core42, Humain, Oracle) differ, and the chat-completions shape is the
  common denominator. Whether a host is genuinely in-country is recorded on the client's data handling sheet.
- **No prompt or completion content logged for any tier.** Stricter than the spec, which only required it for
  Tier B. Reason: there is no debugging need that justifies the risk.
- **`bf close` added.** The spec required workspaces to be deleted at run close but named no command for it.
- **Fixed buyer time zones (UTC+3 Saudi Arabia, UTC+4 UAE).** Neither country observes daylight saving.

## 2026-10-29: Service first, product never in the MVP

Decision: run Bid Factory as a done-for-you service on a thin CLI toolkit. No SaaS, no client portal, no portal integrations.
Rejected: building bid software for in-house teams. Reason: the global tools already exist, the Gulf segment has no in-house teams, and the margin sits in the fee and later in prime bidding, not in seats.

## 2026-10-29: IT and software suppliers as the first category

Decision: one category for the first ten bids.
Rejected: facilities management, training, medical supplies as first category. Reason: founder's domain, English-dominant documents, formulaic technical scoring. Second category opens after ten delivered bids.

## 2026-10-29: Client submits, we never hold credentials

Decision: the client signs and submits under its own supplier registration.
Rejected: acting as the client's registered agent on portals. Reason: liability, portal terms, UAE Pass and Etimad accounts are personal, and the human signature is the one thing that must stay with the client.

## 2026-10-29: Evidence-bound generation

Decision: every factual claim in a draft resolves to a library record or is tagged for client input. No exceptions.
Rejected: free drafting with human fact-check. Reason: an invented certification in a government bid ends the business; evidence binding is also what makes review take hours rather than days.

## 2026-10-29: Three-tier data handling, Tier B default when unsure

Decision: tier at intake; frontier model only for public and non-personal material; in-country model for restricted; humans only for classified. Saudi government work only through a Saudi entity or partner.
Rejected: "Claude in the UAE region" as a residency story. Reason: Bedrock in the Middle East regions uses global cross-region inference and is not resident.

## 2026-10-29: Kill means stop

Decision: at day 45, failing the kill lines means stopping and writing up, not iterating.
Reason: the previous three ideas in this programme died by iteration. The test is cheap; the time is not.
