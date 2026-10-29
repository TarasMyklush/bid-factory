# Data residency and protection design

Status as of 29 October 2026. This is a design document, not legal advice. Items marked **verify** must be confirmed with a UAE and a Saudi lawyer before the first government client.

## 1. What we handle and which rule applies

| Data | Examples | Governing rules |
|---|---|---|
| Tender documents from government buyers | RFP text, specifications, draft contracts, Q&A | Buyer confidentiality clause; Saudi cloud and cybersecurity frameworks for public-authority data (**verify** current CST and NCA texts); UAE buyer terms |
| Client bid library | Past bids, case studies, pricing, certificates | Commercial confidentiality; client's own policies |
| Personal data inside the library | Staff CVs, passports, Emirates IDs, Iqamas, reference contacts | UAE PDPL (Federal Decree-Law 45/2021); Saudi PDPL and SDAIA Transfer Regulation; DIFC or ADGM laws if the client sits there |
| Our own records | Outcome log, regression tests, model-call logs | Kept free of personal data by design |

## 2. The legal position

### United Arab Emirates

- The federal PDPL is in force. Its executive regulations were still unpublished as of September 2026 according to most practitioner sources, and no adequacy list has been published. Cross-border transfers therefore rely on contractual safeguards or consent under Articles 22 and 23. **Verify** whether the regulations have since been issued.
- DIFC Regulation 10 (in force 1 September 2023) is the only enacted AI-specific processing rule in the UAE and applies to DIFC entities only. It requires deployer notices, explainability, a use-case register and human-intervention triggers. We follow it voluntarily as good practice.
- Sector rules localise some data in the UAE (central bank licensees, health). Not our clients in the MVP.

### Saudi Arabia

- The PDPL is in force, with SDAIA as regulator. The Regulation on Personal Data Transfer Outside the Kingdom was issued in August 2024 and amended in September 2024.
- No adequacy list has been published. Transfers to non-adequate countries need SDAIA's standard contractual clauses (version 1.0, September 2024), binding common rules (intra-group only, so not available to us), or an accreditation certificate.
- SDAIA's SCCs are governed by Saudi law and the importer submits to Saudi jurisdiction.
- A transfer risk assessment is required under SDAIA's February 2025 guidelines before relying on SCCs.
- Government data: the original CST Cloud Computing Regulatory Framework barred Level 3 public-authority data from leaving the Kingdom without authorisation; the revised framework reportedly moved localisation to the National Data Management Office, and the National Cybersecurity Authority's controls still point to in-Kingdom hosting for covered entities. One vendor reading says hosting in Bahrain does not satisfy Saudi residency. **Verify** the current texts and how they bind a supplier's adviser rather than the supplier.

### Model hosting reality

- Claude on AWS Bedrock in the UAE (me-central-1) and Bahrain (me-south-1) regions is served only through global cross-region inference: the request originates in the Gulf and is processed elsewhere. It is not data-resident. Do not describe it as such to clients.
- In-country options that exist: Oracle OneCloud in the UAE, the e& and AWS Sovereign Launchpad, and open-weight models on in-country GPU capacity. Core42's sovereign cloud, Azure's Saudi East region (announced for Q4 2026) and Humain's in-Kingdom model catalogue are plausible Tier B hosts whose current model availability must be **verified** before use.

## 3. Tiering

Decided at intake, before any model call, recorded in `run.json`.

| Tier | Definition | Processing | Model |
|---|---|---|---|
| A | Public tender text; the client's own narrative and non-personal library records | Frontier model via API under no-training and zero-retention terms; SCCs and transfer risk assessment on file | Claude |
| B | Documents under a confidentiality clause, marked restricted, or from a buyer that requires in-country processing | In-country model on sovereign infrastructure in the same country as the buyer, or processing inside the client's tenant | Open-weight model, in-country |
| C | Classified material; any buyer whose terms prohibit third-party processing; identity documents | Humans only; never uploaded to any model or to our workspace | None |

Default when unsure: Tier B. Escalate to Tier C on any explicit prohibition.

## 4. Controls

### Personal data minimisation

- CVs are pseudonymised before indexing: names replaced by role tokens, contact details removed, nationality kept only where a tender scores it.
- Passports, Emirates IDs and Iqamas never leave the client's tenant. The pack references them by document id; the client attaches them at submission.
- Reference contacts are stored as organisation and role only until the client confirms the bid is going ahead.

### Data location

- The bid library lives in the client's tenant, in-region. We hold scoped, revocable access.
- Our workspace per run is local, encrypted at rest, and deleted at run close except for the artefacts delivered to the client's tenant and the outcome log entry.
- Model-call logs record tier, model, token counts and run id. For Tier B runs no prompt or completion content is logged.

### Contracts

- Data processing agreement with every client naming us as processor, the tiers, the sub-processors (model providers, hosting), retention and deletion.
- SDAIA SCCs signed by the Saudi entity or partner for any Saudi personal data that crosses a border. UAE contractual safeguards for UAE data.
- No-training and zero-retention terms with every model provider, confirmed in writing.
- Non-disclosure agreement before any tender document is received.

### Entities

- UAE entity for UAE work.
- Saudi entity or licensed Saudi partner for Saudi government tenders. The partner signs the SCCs and submits to Saudi jurisdiction. Serving Saudi government data purely from the UAE is refused.

### People

- One named person accountable for data handling, listed on every data handling sheet.
- Access to client tenants is per person, logged, and removed at the end of each engagement.

## 5. The data handling sheet

Every client receives [templates/data-handling-sheet.md](../templates/data-handling-sheet.md) completed for their engagement before the first run: tiers, processing locations, models, retention, sub-processors, access list, accountable person, and the legal bases relied on. It is a sales document as much as a compliance one. The global bid-software vendors cannot produce it for the Gulf.

## 6. Costs and trade-offs

- Tier B capacity is slower and dearer than frontier APIs, and open-weight models draft worse. Tier B bids take more human review. Price them one band higher.
- Keeping the library in the client's tenant means every run starts with a rebuild of the index. Acceptable at MVP volumes; revisit at twenty clients.
- Refusing Tier C work loses some government bids. That is the correct outcome.

## 7. Before the first government client, verify

1. The current Saudi CST cloud framework and NCA control texts and how they apply to a supplier's adviser.
2. Whether the UAE PDPL executive regulations and adequacy list have been issued.
3. Each target buyer's confidentiality clause on third-party processing.
4. Model availability and terms on the chosen Tier B hosts in each country.
5. Professional indemnity cover that includes data incidents.
