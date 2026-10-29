# Data handling sheet

Client: <legal name>. Engagement: <reference>. Effective: <date>. Accountable person at Bid Factory: <name, role>.

This sheet records where and how your data is processed. It forms part of the data processing agreement.

## 1. Roles

- Controller: <client>.
- Processor: <Bid Factory entity>, <jurisdiction>.
- Sub-processors: listed in section 4.

## 2. What we process

| Data | Tier | Where it lives | What we do with it |
|---|---|---|---|
| Tender documents from buyers | A, B or C per tender, decided at intake | Your tenant | Extract clauses, build the matrix, draft responses |
| Bid library (non-personal) | A | Your tenant | Index, retrieve, cite |
| Staff CVs | A after pseudonymisation | Your tenant; pseudonymised copies in the run workspace | Role profiles for team sections |
| Identity documents | C | Your tenant only | Never processed by us or by any model |
| Pricing sheets | A or B per your instruction | Your tenant | Number checks and commercial narrative |

## 3. Where processing happens

| Tier | Processing location | Model | Retention on our side |
|---|---|---|---|
| A | <provider, region> via API under no-training and zero-retention terms | <model> | Run workspace deleted at run close; artefacts delivered to your tenant |
| B | <in-country host, country> | <open-weight model> | As above; no prompt or completion content logged |
| C | None. Humans only, inside your tenant | None | None |

## 4. Sub-processors

| Name | Purpose | Location | Terms |
|---|---|---|---|
| <model provider> | Tier A model inference | <region> | No training, zero retention, SCCs <ref> |
| <in-country host> | Tier B model inference | <country> | <ref> |
| <storage, if any outside your tenant> | <purpose> | <location> | <ref> |

## 5. Legal bases and transfer mechanisms

- UAE: contractual safeguards under Articles 22 and 23 of Federal Decree-Law 45/2021; data processing agreement <ref>.
- Saudi: SDAIA standard contractual clauses version 1.0 signed by <Saudi entity or partner>; transfer risk assessment <ref> dated <date>.
- Buyer confidentiality clauses reviewed at intake for every tender; any prohibition on third-party processing moves the tender to Tier C.

## 6. Access

| Person | Role | Access to your tenant | Granted | Revoked |
|---|---|---|---|---|

## 7. Retention and deletion

- Run workspaces: deleted at run close.
- Delivered artefacts: in your tenant, under your retention policy.
- Our outcome log: tender reference, dates, outcome, hours. No personal data.
- Regression tests: anonymised corrections. No personal data.
- On termination: all access revoked within 2 working days; written confirmation of deletion within 10.

## 8. Incidents

Any suspected incident involving your data is reported to <client contact> within 24 hours of our becoming aware, with what happened, what data, and what we are doing.

## 9. Your signatory

Name, role, date, signature: ____________________
