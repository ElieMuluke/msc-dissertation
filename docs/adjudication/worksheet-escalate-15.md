# Blind adjudication worksheet — escalate-labelled cases

**What this is.** 15 benchmark cases. You decide each one against the rulebook; the
benchmark author's label is hidden. We then measure how often an independent reader
applying the documented rules reaches the same verdict. This tests the *labels*, not
any model.

**How to answer.** For each case: pick **E** (escalate), **D** (dismiss) or **I**
(investigate); note which rule drove it (the fired rules are listed — pick one, or write
your own); rate confidence H/M/L. ~2 minutes each.

**Fired rules are mechanical lookups, not recommendations.** They are the rules whose
trigger conditions objectively match this case's fields. Several may point different ways;
choosing between them is the judgement, and that is yours.

---

## Case 1 of 15  ·  `TXN-2025-002`

**125,000 USD** from **New Customer LLC** to **Shadow Corp**, destination **Belarus**.
Described as: *First transaction from new customer to high-risk jurisdiction*

Rules whose triggers fire:
- **CDD-1** — A new relationship triggers full customer due diligence.
- **MON-4** — A counterparty in a high-risk jurisdiction requires enhanced scrutiny.
- **EDD-7** — Unusually large transactions require examination of purpose and background.

Tool evidence available to an analyst: sanctions screen **MATCHES Shadow Corp**; customer profile **on file**; precedent search returns **nothing relevant**.

> **Your decision:**  E / D / I  → `____`
> **Rule applied:** `________`   **Confidence:** H / M / L  → `____`

---

## Case 2 of 15  ·  `TXN-2025-004`

**9,999 USD** from **Cash Business LLC** to **Personal Account**, destination **USA**.
Described as: *Just under $10K reporting threshold*

Rules whose triggers fire:
- **MON-2** — Payments sized to stay under a reporting threshold are a structuring red flag.

Tool evidence available to an analyst: sanctions screen returns **no match**; customer profile **not on file** (unknown, KYC incomplete); precedent search returns **nothing relevant**.

> **Your decision:**  E / D / I  → `____`
> **Rule applied:** `________`   **Confidence:** H / M / L  → `____`

---

## Case 3 of 15  ·  `TXN-2025-006`

**75,000 USD** from **Unknown Entity** to **Shell Company Inc**, destination **Panama**.
Described as: *Payment from unknown source to suspected shell*

Rules whose triggers fire:
- **CDD-3** — If the originator cannot be identified, CDD has failed.
- **CDD-1** — Unclear beneficial ownership means customer due diligence is incomplete.
- **MON-4** — Offshore/secrecy jurisdictions raise the risk band.
- **EDD-7** — Unusually large transactions require examination of purpose and background.

Tool evidence available to an analyst: sanctions screen returns **no match**; customer profile **not on file** (unknown, KYC incomplete); precedent search returns **nothing relevant**.

> **Your decision:**  E / D / I  → `____`
> **Rule applied:** `________`   **Confidence:** H / M / L  → `____`

---

## Case 4 of 15  ·  `TXN-2025-011`

**1,000,000 USD** from **PEP Family Member** to **Real Estate LLC**, destination **USA**.
Described as: *Large real estate purchase by PEP family*

Rules whose triggers fire:
- **EDD-3** — Politically exposed persons require enhanced due diligence and senior sign-off.
- **EDD-7** — Unusually large transactions require examination of purpose and background.

Tool evidence available to an analyst: sanctions screen returns **no match**; customer profile **not on file** (unknown, KYC incomplete); precedent search returns **nothing relevant**.

> **Your decision:**  E / D / I  → `____`
> **Rule applied:** `________`   **Confidence:** H / M / L  → `____`

---

## Case 5 of 15  ·  `TXN-2025-015`

**175,000 USD** from **Sanctioned Entity Sub** to **Trading Company**, destination **Russia**.
Described as: *Payment from entity with sanctioned ownership*

Rules whose triggers fire:
- **SAN-1** — Ownership/control links to sanctioned parties count as sanctions exposure.
- **MON-4** — A counterparty in a high-risk jurisdiction requires enhanced scrutiny.
- **EDD-7** — Unusually large transactions require examination of purpose and background.

Tool evidence available to an analyst: sanctions screen returns **no match**; customer profile **not on file** (unknown, KYC incomplete); precedent search returns **nothing relevant**.

> **Your decision:**  E / D / I  → `____`
> **Rule applied:** `________`   **Confidence:** H / M / L  → `____`

---

## Case 6 of 15  ·  `TXN-2025-019`

**350,000 USD** from **Art Gallery** to **Anonymous Buyer**, destination **Switzerland**.
Described as: *High-value art sale to anonymous buyer*

Rules whose triggers fire:
- **CDD-3** — An unidentifiable counterparty means CDD has failed.
- **EDD-7** — Unusually large transactions require examination of purpose and background.

Tool evidence available to an analyst: sanctions screen returns **no match**; customer profile **not on file** (unknown, KYC incomplete); precedent search returns **nothing relevant**.

> **Your decision:**  E / D / I  → `____`
> **Rule applied:** `________`   **Confidence:** H / M / L  → `____`

---

## Case 7 of 15  ·  `TXN-2025-023`

**220,000 USD** from **Defense Contractor** to **Foreign Agent**, destination **UAE**.
Described as: *Payment to foreign sales agent*

Rules whose triggers fire:
- **EDD-3** — Third-party agents in high-risk sectors carry corruption risk.
- **EDD-7** — Unusually large transactions require examination of purpose and background.

Tool evidence available to an analyst: sanctions screen returns **no match**; customer profile **not on file** (unknown, KYC incomplete); precedent search returns **nothing relevant**.

> **Your decision:**  E / D / I  → `____`
> **Rule applied:** `________`   **Confidence:** H / M / L  → `____`

---

## Case 8 of 15  ·  `TXN-2025-027`

**450,000 USD** from **Casino Operator** to **VIP Customer**, destination **Macau**.
Described as: *Large payout to casino VIP*

Rules whose triggers fire:
- **EDD-7** — Unusually large transactions require examination of purpose and background.
- **MON-4** — A counterparty in a high-risk jurisdiction requires enhanced scrutiny.

Tool evidence available to an analyst: sanctions screen returns **no match**; customer profile **not on file** (unknown, KYC incomplete); precedent search returns **nothing relevant**.

> **Your decision:**  E / D / I  → `____`
> **Rule applied:** `________`   **Confidence:** H / M / L  → `____`

---

## Case 9 of 15  ·  `TXN-2025-029`

**82,000 USD** from **Mining Company** to **Extraction Services**, destination **DRC**.
Described as: *Payment for mining services in conflict zone*

Rules whose triggers fire:
- **MON-4** — Conflict-zone exposure raises the risk band.
- **EDD-7** — Unusually large transactions require examination of purpose and background.

Tool evidence available to an analyst: sanctions screen returns **no match**; customer profile **not on file** (unknown, KYC incomplete); precedent search returns **nothing relevant**.

> **Your decision:**  E / D / I  → `____`
> **Rule applied:** `________`   **Confidence:** H / M / L  → `____`

---

## Case 10 of 15  ·  `TXN-2025-033`

**580,000 USD** from **Pharmaceutical Co** to **Unlicensed Distributor**, destination **India**.
Described as: *Payment to unlicensed pharmaceutical distributor*

Rules whose triggers fire:
- **CDD-1** — An unlicensed counterparty raises regulatory and CDD concerns.
- **EDD-7** — Unusually large transactions require examination of purpose and background.

Tool evidence available to an analyst: sanctions screen returns **no match**; customer profile **not on file** (unknown, KYC incomplete); precedent search returns **nothing relevant**.

> **Your decision:**  E / D / I  → `____`
> **Rule applied:** `________`   **Confidence:** H / M / L  → `____`

---

## Case 11 of 15  ·  `TXN-2025-035`

**92,000 USD** from **Energy Trading** to **Venezuelan Entity**, destination **Venezuela**.
Described as: *Energy sector payment to Venezuela*

Rules whose triggers fire:
- **SAN-1** — Sanctions exposure must be screened and cleared before proceeding.
- **EDD-7** — Unusually large transactions require examination of purpose and background.

Tool evidence available to an analyst: sanctions screen returns **no match**; customer profile **not on file** (unknown, KYC incomplete); precedent search returns **nothing relevant**.

> **Your decision:**  E / D / I  → `____`
> **Rule applied:** `________`   **Confidence:** H / M / L  → `____`

---

## Case 12 of 15  ·  `TXN-2025-039`

**310,000 USD** from **Weapons Dealer** to **Arms Manufacturer**, destination **Czech Republic**.
Described as: *Weapons procurement payment*

Rules whose triggers fire:
- **SAN-1** — Arms trade requires export-licence verification.
- **EDD-7** — Unusually large transactions require examination of purpose and background.
- **SAN-1** — Export-controlled goods require licence verification.

Tool evidence available to an analyst: sanctions screen returns **no match**; customer profile **not on file** (unknown, KYC incomplete); precedent search returns **nothing relevant**.

> **Your decision:**  E / D / I  → `____`
> **Rule applied:** `________`   **Confidence:** H / M / L  → `____`

---

## Case 13 of 15  ·  `TXN-2025-041`

**88,000 USD** from **Telecom Company** to **Government Official**, destination **Kenya**.
Described as: *Payment to government official*

Rules whose triggers fire:
- **EDD-3** — Payments involving public officials carry bribery/PEP risk.
- **EDD-3** — Corruption exposure requires enhanced due diligence.
- **EDD-7** — Unusually large transactions require examination of purpose and background.

Tool evidence available to an analyst: sanctions screen returns **no match**; customer profile **not on file** (unknown, KYC incomplete); precedent search returns **nothing relevant**.

> **Your decision:**  E / D / I  → `____`
> **Rule applied:** `________`   **Confidence:** H / M / L  → `____`

---

## Case 14 of 15  ·  `TXN-2025-045`

**425,000 USD** from **Luxury Car Dealer** to **Cash Buyer**, destination **USA**.
Described as: *Cash purchase of luxury vehicle*

Rules whose triggers fire:
- **EDD-7** — Large cash settlement requires examination of source of funds.
- **EDD-7** — Unusually large transactions require examination of purpose and background.

Tool evidence available to an analyst: sanctions screen returns **no match**; customer profile **not on file** (unknown, KYC incomplete); precedent search returns **nothing relevant**.

> **Your decision:**  E / D / I  → `____`
> **Rule applied:** `________`   **Confidence:** H / M / L  → `____`

---

## Case 15 of 15  ·  `TXN-2025-049`

**285,000 USD** from **Crypto Mixer Service** to **Exchange Account**, destination **Estonia**.
Described as: *Funds from cryptocurrency mixer*

Rules whose triggers fire:
- **MON-5** — Cryptoasset exposure requires enhanced monitoring.
- **MON-5** — Mixer/anonymisation services are a high-risk cryptoasset indicator.
- **EDD-7** — Unusually large transactions require examination of purpose and background.
- **MON-5** — Deliberate anonymisation is a high-risk indicator.

Tool evidence available to an analyst: sanctions screen returns **no match**; customer profile **not on file** (unknown, KYC incomplete); precedent search returns **nothing relevant**.

> **Your decision:**  E / D / I  → `____`
> **Rule applied:** `________`   **Confidence:** H / M / L  → `____`

---
