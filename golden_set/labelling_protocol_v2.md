# Labelling Protocol – ICT3113 Assignment 1, P2 Group 20

**Version:** v2 (final, frozen with the golden set)

> **What changed from v1:** v2 adds the rules and examples that came out of our disagreement resolution meeting (54 tickets discussed). Every change is listed in Section 7 with the ticket that triggered it. Changed or new text is marked **[v2]**.

---

## 1. Purpose

We are building a golden test set: 185 complaint tickets with labels we trust. Later, every model's accuracy will be checked against these labels. The original labels in the CSV were chosen by the consumers themselves and are often wrong, so we label the tickets ourselves using the rules below.

## 2. The tickets

- Taken from our team's rows: 20000 to 20999.
- 200 tickets picked at random, about 28–29 from each original category (random seed = 20), so that every category is represented.
- The original consumer labels are hidden from us while we label, so they cannot influence our decisions.
- Tickets that still can't be placed after discussion are removed (Rule 7). The final golden set must have at least 150 tickets.

## 3. Golden rule

> Read the whole ticket and ask: **"What is the customer mainly unhappy about, and which team would need to fix it?"**
> Classify by the **product or service causing the problem**, not by the company name or by keywords.

---

## 4. Category definitions

**CATEGORY: Credit reporting**
**Definition:** Complaints mainly about a consumer's credit report, credit history or credit score, or how a credit bureau (Equifax, Experian, TransUnion) handled their information or dispute.
**Typical examples:**
- An account wrongly appearing on the credit report
- An incorrect late payment being reported
- A dispute with the credit bureau that was not corrected or not properly investigated
- An unauthorised "hard inquiry" on the report
- Identity theft where the customer wants fraudulent items removed from the report

**Do NOT classify here when:** the customer is still fighting the lender's own mistake (for example card charges, a lost loan payment, or a collector calling). A report or score that is only mentioned in passing, or as a side effect, does not make it Credit reporting (see Rule 2).

---

**CATEGORY: Debt collection**
**Definition:** Complaints mainly about a debt collector or collection agency and how they are trying to collect money.
**Typical examples:**
- Harassing phone calls, threats or abusive language from a collector
- Being chased for a debt that is not theirs, or was already paid
- A collector refusing to provide proof (validation) of the debt
- Collection letters with wrong amounts

**Do NOT classify here when:** the complaint is about the original lender's normal billing, statements or fees on the account (use Credit card, Mortgage or Consumer loan instead; see Rule 3 for the one exception), or only about how the collection appears on the credit report (use Credit reporting).

---

**CATEGORY: Mortgage**
**Definition:** Complaints mainly about a home loan, from applying for it through to paying it off.
**Typical examples:**
- Problems with the mortgage servicer, such as lost payments or wrong balances
- Escrow problems (property tax or insurance, including force-placed insurance)
- Loan modification or refinancing issues
- Foreclosure, reinstatement or deed-in-lieu
- Home equity loans or HELOCs
- **[v2]** VA or FHA home loans, including loan assumptions

**Do NOT classify here when:** the loan is not secured on a home (for example a car loan or personal loan, which are Consumer loan).

---

**CATEGORY: Credit card**
**Definition:** Complaints mainly about using or managing a credit card account.
**Typical examples:**
- Unrecognised or disputed charges on the card
- Unfair fees, interest rate (APR) or late fees
- Rewards or points not credited
- Card closed, or credit limit lowered without notice
- Fraud on the credit card account
- **[v2]** Cash advance fees, or a purchase wrongly treated as a cash advance

**Do NOT classify here when:** the main problem is incorrect information about the card on the credit report and the card issue itself is settled (Credit reporting), the card is a **debit** card (Bank account or service), or the narrative never says it is a credit card (Rule 5).

---

**CATEGORY: Bank account or service**
**Definition:** Complaints mainly about a checking or savings account and the everyday services that come with it.
**Typical examples:**
- Overdraft or maintenance fees
- Deposits not credited, or withdrawals going wrong
- Account frozen, locked or closed by the provider
- Problems opening an account
- Debit card or ATM issues
- Money missing from the account, or unexplained discrepancies
- **[v2]** App-based accounts such as Chime or Credit Karma Money, for example an account or card being locked or deposits going missing

**Do NOT classify here when:** the problem is mainly about a transfer of money to another person or service, such as Zelle, a wire, PayPal or an unauthorized transfer (Money transfer or service; see Rule 6).

---

**CATEGORY: Consumer loan**
**Definition:** Complaints mainly about a loan that is **not** a mortgage or a credit card.
**Typical examples:**
- Auto (car) loans or vehicle leases
- Personal or installment loans
- Student loans *(in our dataset, student loans fall under this category)*
- Payday loans
- Problems with loan payments, statements, interest or the loan servicer
- **[v2]** Vehicle repossession, or being sued for the remaining balance after repossession

**Do NOT classify here when:** a separate debt collector is now chasing the debt and the complaint is about the collector (Debt collection), the loan is secured on a house (Mortgage), or the ticket only says "loan" with no clue what kind (Rule 7).

---

**CATEGORY: Money transfer or service**
**Definition:** Complaints mainly about sending or receiving money.
**Typical examples:**
- Wire transfers that went missing or were delayed
- Problems with Zelle, PayPal, Venmo, Cash App or Western Union
- Being scammed into sending money, and asking for it back
- Unauthorized transfers out of an account, and disputes about them
- Money orders, prepaid cards, international remittances

**Do NOT classify here when:** the transfer is only a side detail and the real problem is with the account itself, for example the provider freezing or locking the account (Bank account or service).

---

## 5. Edge-case rules

**RULE 1:** If multiple products are mentioned, classify according to the customer's **PRIMARY complaint**: the problem they spend the most time on, or what they are asking to be fixed.

**RULE 2 [v2 – updated]:** When a credit report is involved, classify by **what is still unresolved**:
- If the customer is **still fighting the lender's own mistake** (a lost payment, a wrong fee, an account they want closed), use the **original product**, even if their credit was damaged. *(G007, G017)*
- If the account problem is **already settled or admitted** by the lender, or the debt **didn't come from a financial product** (for example a residential lease), and the only thing left is to fix the report, use **Credit reporting**. *(G031, G049)*

**RULE 3 [v2 – updated]:** If a **separate debt collector** is involved after a loan or credit card was not paid, use **Debt collection** when the complaint is mainly about the **collector's actions**. If it is mainly about the original lender's billing or servicing, classify by the original product.
- **One exception:** if the **original company** is trying to collect a **separate charge that isn't part of the normal loan payments** (for example a tax or fee the customer says they don't owe), and the complaint is about the collecting (repeated calls, refusing to verify), use **Debt collection**. *(G053)*
- Normal statements, payments and fees on the loan stay under the original product. *(G104, G156)*

**RULE 4 [v2 – updated] (identity theft):** Classify by **what the customer wants fixed, and who they are disputing with**:
- fraudulent items on the credit report, or disputes sent to the credit bureaus → Credit reporting
- a fraudulent credit card account being disputed with the card issuer → Credit card
- a collector chasing a debt that came from identity theft → Debt collection
- **[v2]** if the identity theft involves **several accounts across different products** and the customer is disputing them with a credit bureau → **Credit reporting** *(G140)*

**RULE 5:** **Debit card = Bank account or service. Credit card = Credit card.** If the customer only says "card" and there are no other clues (see Rule 8), we cannot assume the type. Mark it AMBIGUOUS (Rule 7).

**RULE 6 [v2 – updated] (payment apps and transfers):** Classify by **the problem, not by whether the provider is a bank or an app**:
- The **transfer itself** is the problem (unauthorized, missing or reversed transfer, or a scam) → **Money transfer or service**, even on app-based accounts like Chime. *(G012)*
- **[v2]** **Impostor scams** where the customer is tricked into moving money to a scammer → **Money transfer or service**, even if the money was moved through an ATM cash deposit. *(G147)*
- The **account itself** is the problem (frozen, locked, overdraft fees, missing funds, unexplained discrepancies) → **Bank account or service**. *(G093, G110)*

**RULE 7 [v2 – updated]:** If the narrative **does not contain enough information** to decide, mark it **AMBIGUOUS** for later discussion. **Do not guess.** Write the reason in the notes column. For example, the narrative may be mostly "XXXX", too short, unreadable, or not a financial complaint. Also:
- **[v2]** If a ticket only says "loan" and gives no clue what kind (home, car, student, personal), mark it AMBIGUOUS. **Do not default to Consumer loan.** *(G089)*
- **[v2]** A ticket is **not** ambiguous just because the original debt is unknown. If the complaint is clearly about how a **collector is behaving**, label it Debt collection. *(G066)*
- If an AMBIGUOUS ticket still can't be placed after discussion, it is **removed** from the golden set.

**RULE 8 [v2 – updated] (masking and product clues):** Ignore "XXXX" (removed personal information) and do not guess what was removed. However, **clear product clues in the narrative can be used** to decide:
- **[v2]** Product-specific terms count as clues. For example: "statement balance" or "minimum payment" → Credit card; "reinstatement figure", "foreclosure" or "escrow" → Mortgage; "income-based repayment" → student loan (Consumer loan). *(G016, G198)*
- If there are no such clues, the ticket stays AMBIGUOUS (Rule 7).

**RULE 9:** Do not use the company name **on its own** to decide. For example, "Bank of America" can appear in a mortgage, credit card or bank account complaint, and "Credit Karma" is not automatically Credit reporting. A company name can only **support** other clues from Rule 8. *(G016, G110)*

---

## 6. How we label (procedure)

1. At least two team members (Annotator A and B) label **all 200 tickets on their own**. No discussing tickets with each other, and no AI tools.
2. For each ticket, fill in **label**, **confidence** (High, Medium or Low) and **notes**. Write in the notes which rule you used, or why you were unsure.
3. When finished, the raw sheets are committed to GitHub **unchanged**.
4. We run `compute_agreement.py` to calculate **Cohen's kappa** and list every disagreement and every AMBIGUOUS ticket.
5. We meet to discuss each one, decide the final label, and record the reason in `disagreements_to_resolve.xlsx`.
6. If a disagreement shows that a rule was missing or unclear, we update this protocol, change the version number, and record the change in Section 7.
7. We run `build_golden_set.py` and commit the final golden set and this protocol **before any model is run**.

---

## 7. Revision log

| Version | Date | What changed | Why (ticket ID) |
|---|---|---|---|
| v1 | | First version | – |
| v2 | | **Rule 2** rewritten: classify by what is still unresolved (the lender's mistake → product; only the report left → Credit reporting) | G007, G031, G049 |
| v2 | | **Rule 3** exception added: the original company collecting a separate disputed charge → Debt collection; normal loan servicing stays with the product | G053, G104 |
| v2 | | **Rule 4** bullet added: identity theft across several products disputed with a bureau → Credit reporting | G140 |
| v2 | | **Rule 6** rewritten: classify by the problem, not the provider type; impostor scams count as Money transfer, even via ATM | G012, G093, G147 |
| v2 | | **Rule 7** clarified: an unspecified "loan" is AMBIGUOUS; an unknown debt with clear collector behaviour is Debt collection | G066, G089 |
| v2 | | **Rule 8** extended: product-specific terms can be used as clues when names are masked | G016, G198 |
| v2 | | **Rule 9** clarified: a company name can support clues but never decides on its own | G016, G110 |
| v2 | | New examples: VA/FHA loans and assumptions (Mortgage); cash advance fees (Credit card); app-based accounts (Bank account); vehicle repossession (Consumer loan) | G135, G146, G110, G057 |