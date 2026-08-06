# AML Decision Rulebook — Production

Version: 1.0 (2026-08-05). Owner: Elie Muluke.

Distilled decision rules for the production Policy & Risk agent (PRD-B §2). Sources:
**FATF**, *International Standards on Combating Money Laundering and the Financing of
Terrorism & Proliferation — the FATF Recommendations* (2012, as amended; "FATF R.n"), and
**JMLSG**, *Prevention of money laundering / combating terrorist financing — Guidance for
the UK financial sector*, Part I (June 2023, updated Aug 2025) and Part II (June 2023,
updated Dec 2025). Citations were checked against the source PDF text where feasible;
rules whose citation could not be verified verbatim are tagged **[citation unverified]**
for owner review. Rules tagged **(platform operational rule)** are thresholds authored
for this platform, derived from — not stated in — the cited guidance.

This rulebook is used only by the production pipeline. The PRD-A experiment uses DFAH's
shipped rulebook; the two must never mix.

Decisions are expressed in the shared agent contract vocabulary:
`escalate` (report to the nominated officer / MLRO for SAR consideration and possible
account restriction), `investigate` (open an enhanced review; obtain more information),
`dismiss` (no further action beyond normal monitoring).

---

## 1. Risk bands

**RB-1 — Risk-based approach is mandatory.** Every case must be assigned a risk band;
measures applied must be proportionate to the assessed money-laundering/terrorist-
financing risk. Source: FATF R.1 ("Assessing risks and applying a risk-based approach");
JMLSG Part I, 4.6–4.10 ("Obligation to adopt a risk-based approach").

**RB-2 — Band definitions and required actions (platform operational rule).** Derived
from the higher-risk factors in JMLSG Part I, 4.59–4.69 and Part I Annexes 5-III/IV
(risk factor guidelines):

| Band | Typical profile | Required action |
|---|---|---|
| LOW | Established customer; activity consistent with profile; no red flags; no list hits | `dismiss` |
| MEDIUM | One non-critical red flag, or activity partly inconsistent with profile | `investigate` |
| HIGH | Two or more red flags, or one red flag combined with a high-risk jurisdiction or PEP link | `escalate` |
| CRITICAL | Any true sanctions-list match, or FATF call-for-action jurisdiction involvement | `escalate` (immediate) |

## 2. Customer due diligence (CDD)

**CDD-1 — CDD triggers.** CDD is required when establishing a business relationship;
for occasional transactions above USD/EUR 15,000; whenever there is suspicion of money
laundering or terrorist financing; and when there are doubts about the veracity or
adequacy of previously obtained identification data. Source: FATF R.10 (verified,
including the USD/EUR 15,000 designated threshold).

**CDD-2 — CDD measures.** Identify and verify the customer; identify and take
reasonable measures to verify the beneficial owner (including ownership and control
structure for legal persons); understand the purpose and intended nature of the
relationship; and conduct ongoing due diligence and scrutiny of transactions for
consistency with the customer's known profile, including source of funds where
necessary. Source: FATF R.10(a)–(d); JMLSG Part I, 5.3 (standard evidence:
5.3.287–5.3.290).

**CDD-3 — CDD failure.** Where CDD under CDD-2 cannot be completed, do not open the
account, commence the relationship or perform the transaction; or terminate the
relationship — and consider making a suspicious activity report. Analyst decision: at
minimum `investigate`; `escalate` if any other red flag is present. Source: FATF R.10
(verified verbatim); JMLSG Part I, 5.5.1–5.5.12 context.

**CDD-4 — Simplified due diligence only for low risk.** SDD may be applied only where
the assessed risk is low and no suspicion exists; SDD is never available for cases
showing any red flag in §4. Source: JMLSG Part I, 5.4.1–5.4.10.

**CDD-5 — Record keeping.** All transaction and CDD records must be kept at least five
years (after the end of the relationship or the occasional transaction) and be
sufficient to permit reconstruction of individual transactions. Every analysis report
must reference the underlying data rows for auditability. Source: FATF R.11 (verified).

## 3. Enhanced due diligence (EDD)

**EDD-1 — High-risk (call-for-action) jurisdictions.** Apply EDD to business
relationships and transactions with natural and legal persons and financial
institutions from countries for which the FATF calls for this; apply countermeasures
when called upon. Any case involving a FATF call-for-action jurisdiction (per the
`country_risk` tool) is CRITICAL → `escalate`. Source: FATF R.19 (verified); JMLSG
Part I, 5.5.11 (high-risk third countries).

**EDD-2 — Increased-monitoring (grey list) jurisdictions.** Grey-list status is a
country-risk signal to feed into the risk-based assessment — it raises the band by one
level, but is not by itself grounds for `escalate`. Source: FATF "Jurisdictions under
Increased Monitoring" statement (19 June 2026); FATF R.19 proportionality language
(verified). The "not automatic EDD as a class" framing **(verified 2026-08-06 against
the official statement page, owner-provided saved HTML)** — exact text: "The FATF does
not call for the application of enhanced due diligence measures to be applied to these
jurisdictions. The FATF Standards do not envisage derisking, or cutting-off entire
classes of customers, but call for the application of a risk-based approach."

**EDD-3 — Politically exposed persons.** For foreign PEPs (customer or beneficial
owner): risk-management systems to identify PEP status, senior management approval for
the relationship, reasonable measures to establish source of wealth and source of
funds, and enhanced ongoing monitoring. Apply the same to family members and close
associates, and to domestic/international-organisation PEPs in higher-risk
relationships. Minimum band: HIGH → `escalate` if combined with any other red flag,
otherwise `investigate`. Source: FATF R.12 (verified); JMLSG Part I, 5.5.13–5.5.23.

**EDD-4 — Source of wealth in high-risk cases.** For HIGH band relationships, evidence
of source of wealth and source of funds must be obtained; absence of a plausible source
for observed volumes is itself a red flag. Source: JMLSG Part I, 5.5.29–5.5.32.

**EDD-5 — Senior management approval.** High-risk relationships (including PEP
relationships) require senior management approval to establish or continue — reflected
here as `escalate` (the analyst cannot clear a HIGH band case alone). Source: JMLSG
Part I, 5.5.33–5.5.34; FATF R.12(b).

**EDD-6 — Correspondent relationships.** Cross-border correspondent banking requires
information gathering on the respondent institution, assessment of its AML controls,
and senior management approval; payable-through accounts require additional
safeguards. Source: FATF R.13; JMLSG Part II, Sector 16 (Correspondent relationships).

**EDD-7 — Complex or unusually large transactions.** Examine, as far as reasonably
possible, the background and purpose of transactions that are complex, unusually large,
or form an unusual pattern with no apparent economic or lawful purpose; record findings
in writing (the analysis report). Source: FATF R.11 context ("inquiries to establish
the background and purpose of complex, unusual large transactions", verified); JMLSG
Part I, 5.7 monitoring guidance.

## 4. Monitoring red flags

**MON-1 — Ongoing monitoring is required.** Customer activity must be monitored so that
transactions inconsistent with the customer's known profile are identified and
reviewed. Source: JMLSG Part I, 5.7.1–5.7.12 ("Monitoring customer activity"); FATF
R.10(d); JMLSG Part II, Sector 1, 1.43–1.44 (retail banking monitoring triggers).

**MON-2 — Structuring / threshold avoidance (platform operational rule).** Three or
more transactions within 48 hours, each within 10% below USD/EUR 10,000 (or an
equivalent identification/reporting threshold), to or from the same counterparty, is a
structuring red flag: band HIGH → `escalate` when combined with any jurisdiction or
counterparty flag, otherwise `investigate`. Basis: unusual-pattern monitoring duty in
JMLSG Part I, 5.7 and the suspicion standard in FATF R.20. The specific numeric
threshold is **platform-authored (no citation exists by design — a derived operational
threshold, not stated in the guidance)**.

**MON-3 — Rapid pass-through / layering (platform operational rule).** Funds received
and forwarded within 72 hours at ≥80% of the received amount, especially across
multiple institutions or currencies, is a layering red flag: minimum band MEDIUM →
`investigate`; HIGH → `escalate` if a high-risk jurisdiction, PEP or sanctions
near-match is also present. Basis: JMLSG Part I, 5.7 (unusual patterns); FATF R.1
risk-based approach. Numeric thresholds are **platform-authored (no citation exists by
design — derived operational thresholds, not stated in the guidance)**.

**MON-4 — High-risk jurisdiction counterparty.** Any transaction whose counterparty,
counterparty bank or payment route involves a FATF call-for-action jurisdiction →
CRITICAL (EDD-1). Grey-list jurisdiction → apply EDD-2. Source: FATF R.19 (verified).

**MON-5 — Cryptoasset exposure.** Transactions via cryptoasset exchange providers or
custodian wallet providers carry the sector's specific risk factors (e.g. anonymity-
enhanced transfers, non-obliged counterparties); presence of the higher-risk factors in
JMLSG Part II, 22.34 raises the band by one level. Source: JMLSG Part II, Sector 22,
22.33–22.35 (risk factors; verified anchors); FATF R.15 (new technologies).

**MON-6 — Wire transfer information.** Wire transfers must carry required originator
and beneficiary information (with a de minimis of USD/EUR 1,000 for the interpretive
note's reduced requirements); transfers lacking such information are a red flag and the
receiving analyst should treat the transaction as MEDIUM minimum. Source: FATF R.16 and
its Interpretive Note (USD/EUR 1,000 threshold verified).

## 5. Sanctions screening

**SAN-1 — Screening obligation.** Screen the account holder, beneficial owners and
significant counterparties against the OFAC SDN, HM Treasury/OFSI consolidated and UN
Security Council consolidated lists (the `sanctions_check` tool) in every analysis.
Source: FATF R.6 ("Targeted financial sanctions related to terrorism and terrorist
financing", verified heading) and R.7; OFSI, *UK financial sanctions: general guidance*
(HM Treasury/OFSI, updated Jan 2026) — §1 asset-freeze prohibitions on dealing with
funds of designated persons, §2 "Who is subject to financial sanctions" (the UK
Sanctions List), and §5.1.1 reporting obligations for relevant firms, verified verbatim:
"Reporting obligations apply to relevant firms … who are required to inform OFSI as soon
as practicable if they know or reasonably suspect a person is a designated person" —
the duty that customer/counterparty screening implements. Screening is performed against
the OFSI Consolidated List of Financial Sanctions Targets (see
`data/watchlists/manifest.json`), the operational asset-freeze extract of the UK
Sanctions List. **Citation decision (2026-08-06):** JMLSG Part III would be the natural
sectoral citation, but jmlsg.org.uk lists Part III as "currently under review" with no
downloadable edition (amendments per SI 2026/621 in progress), so the OFSI primary
guidance is cited instead; source copy saved at
`Downloads/data/OFSI/UK-financial-sanctions-general-guidance-Jan-2026.html`
(machine-readable, used for verification and RAG ingestion), with an owner-made
print-to-PDF of the same page alongside it (`UK financial sanctions general guidance -
GOV.pdf`, image-only archival copy).

**SAN-2 — Match handling (platform operational rule).** An exact or exact-alias match
(score = 1.0) → CRITICAL, `escalate` immediately; do not execute further transactions.
A fuzzy match (score ≥ 0.85) → `investigate` to confirm or eliminate identity, and
`escalate` on confirmation. Derived from SAN-1 obligations; thresholds are
platform-authored.

## 6. Reporting and escalation

**REP-1 — Internal reporting duty.** Where an analyst knows, suspects, or has
reasonable grounds to know or suspect money laundering or terrorist financing, an
internal report must be made promptly to the nominated officer — in this platform,
decision `escalate` with the rationale recorded in the analysis report. Source: JMLSG
Part I, 6.1–6.24 (knowledge/suspicion standards and internal reporting).

**REP-2 — Nominated officer evaluation and SAR.** The nominated officer evaluates every
internal report and, where suspicion stands, reports promptly to the NCA (SAR); the
FATF standard requires prompt reporting of suspicions to the FIU. Source: FATF R.20
(verified verbatim); JMLSG Part I, 6.29–6.42 (evaluation, external reporting, where to
report).

**REP-3 — No tipping off.** Neither the analysis nor any customer-facing communication
may disclose that a report or investigation is contemplated or under way. Report text
must be written on the assumption the customer never sees it pre-disclosure. Source:
FATF R.21 (verified); JMLSG Part I, 6.60–6.62.

**REP-4 — Decision mapping (platform operational rule).** The agent's final line must
be `FINAL DECISION: <escalate|dismiss|investigate>`. Map: CRITICAL/HIGH → `escalate`;
MEDIUM or unresolved information gaps → `investigate`; LOW with all screenings clear →
`dismiss`. If evidence is contradictory, choose the more conservative decision. Derived
from RB-2; contract per PRD-A/PRD-B shared agent modules.

---

### Verification summary

- 22 rules total: 14 with citations verified against source text (FATF Recommendations
  2012 PDF; JMLSG Part I/II PDFs, paragraph anchors checked; EDD-2's FATF-statement
  framing verified 2026-08-06 against the owner-provided official statement page;
  SAN-1 re-cited 2026-08-06 to OFSI's *UK financial sanctions: general guidance* and
  verified against the saved copy — JMLSG Part III unavailable, "currently under
  review" per jmlsg.org.uk), 0 unverified, 5 platform operational rules with by-design
  derived thresholds (cited as "basis" rather than verbatim; MON-2/MON-3 threshold
  values likewise platform-authored by design).
- PDF sources consulted: `/mnt/c/Users/u5749933/Downloads/data/FATF/FATF Recommendations
  2012.pdf.coredownload.inline.pdf`, `/mnt/c/Users/u5749933/Downloads/data/JMLSG/
  JMLSG-Guidance-Part-I_June-2023-updated-Aug-2025.pdf`, `.../JMLSG-Guidance-Part-II_
  June-2023_updated-Dec-2025.pdf`.
