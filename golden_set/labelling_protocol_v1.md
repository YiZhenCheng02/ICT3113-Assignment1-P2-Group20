# Labelling Protocol – ICT3113 Assignment 1, P2 Group 20

**Version:** v1

**Date:** 14/09/2026

---

## 1. Purpose

We are building a golden test set: 200 complaint tickets with labels we trust. Later, every model's accuracy will be checked against these labels. The original labels in the CSV were chosen by the consumers themselves and are often wrong, so we label the tickets ourselves using the rules below.

## 2. The tickets

- Taken from our team's rows: 20000 to 20999.
- 200 tickets picked at random, about 28–29 from each original category (random seed = 20), so that every category is represented.
- The original consumer labels are hidden from us while we label, so they cannot influence our decisions.

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

**Do NOT classify here when:** the main problem is with the account itself (for example card charges, loan payments, or a collector calling). A report or score that is only mentioned in passing does not make it Credit reporting.

---

**CATEGORY: Debt collection**
**Definition:** Complaints mainly about a debt collector or collection agency and how they are trying to collect money.
**Typical examples:**
- Harassing phone calls, threats or abusive language from a collector
- Being chased for a debt that is not theirs, or was already paid
- A collector refusing to provide proof (validation) of the debt
- Collection letters with wrong amounts

**Do NOT classify here when:** the complaint is about the original lender's own billing or servicing (use Credit card, Mortgage or Consumer loan instead), or only about how the collection appears on the credit report (use Credit reporting).

---

**CATEGORY: Mortgage**
**Definition:** Complaints mainly about a home loan, from applying for it through to paying it off.
**Typical examples:**
- Problems with the mortgage servicer, such as lost payments or wrong balances
- Escrow problems (property tax or insurance)
- Loan modification or refinancing issues
- Foreclosure
- Home equity loans or HELOCs

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

**Do NOT classify here when:** the main problem is incorrect information about the card appearing on the credit report (Credit reporting), or the card is a **debit** card (Bank account or service).

---

**CATEGORY: Bank account or service**
**Definition:** Complaints mainly about a checking or savings account and the everyday services that come with it.
**Typical examples:**
- Overdraft or maintenance fees
- Deposits not credited, or withdrawals going wrong
- Account frozen or closed by the bank
- Problems opening an account
- Debit card or ATM issues

**Do NOT classify here when:** the problem is mainly about a transfer of money to another person or service, such as Zelle, a wire or PayPal (Money transfer or service).

---

**CATEGORY: Consumer loan**
**Definition:** Complaints mainly about a loan that is **not** a mortgage or a credit card.
**Typical examples:**
- Auto (car) loans or vehicle leases
- Personal or installment loans
- Student loans *(in our dataset, student loans fall under this category)*
- Payday loans
- Problems with loan payments, interest or the loan servicer

**Do NOT classify here when:** a debt collector is now chasing the debt and the complaint is about the collector (Debt collection), or the loan is secured on a house (Mortgage).

---

**CATEGORY: Money transfer or service**
**Definition:** Complaints mainly about sending or receiving money.
**Typical examples:**
- Wire transfers that went missing or were delayed
- Problems with Zelle, PayPal, Venmo, Cash App or Western Union
- Being scammed into sending money, and asking for it back
- Money orders, prepaid cards, international remittances

**Do NOT classify here when:** the transfer is only a side detail and the real problem is with the bank account itself, for example the bank freezing the account (Bank account or service).

---

## 5. Edge-case rules

**RULE 1:** If multiple products are mentioned, classify according to the customer's **PRIMARY complaint**: the problem they spend the most time on, or what they are asking to be fixed.

**RULE 2:** If the complaint involves a credit card, loan or other account but the main problem is **incorrect information on the credit report**, classify as **Credit reporting**.

**RULE 3:** If a debt collector is involved after a loan or credit card was not paid, classify as **Debt collection** when the complaint is mainly about the **collector's actions**. If it is mainly about the original lender (for example wrong interest charged before the account went to collection), classify by the original product.

**RULE 4 (identity theft):** Classify by **what the customer wants fixed**:
- fraudulent items on the credit report → Credit reporting
- a fraudulent credit card account → Credit card
- a collector chasing a debt that came from identity theft → Debt collection

**RULE 5:** **Debit card = Bank account or service. Credit card = Credit card.** Read carefully, because customers sometimes just say "card".

**RULE 6 (payment apps):** If the problem is the **transfer itself** (money didn't arrive, a scam, a reversal refused), classify as **Money transfer or service**. If the problem is how the **bank handled the account** (frozen, overdraft fees), classify as **Bank account or service**.

**RULE 7:** If the narrative **does not contain enough information** to decide, for example it is mostly "XXXX", it is too short, or it is not a financial complaint, mark it as **AMBIGUOUS** for later discussion. **Do not guess.** Write the reason in the notes column.

**RULE 8:** Ignore "XXXX" (removed personal information). Do not try to guess what was removed.

**RULE 9:** Do not use the company name to decide. For example, "Bank of America" can appear in a mortgage, credit card or bank account complaint.

---

## 6. How we label (procedure)

1. At least two team members (Annotator A and B) label **all 200 tickets on their own**. No discussing tickets with each other, and no AI tools.
2. For each ticket, fill in **label**, **confidence** (High, Medium or Low) and **notes**. Write in the notes which rule you used, or why you were unsure.
3. When finished, the raw sheets are committed to GitHub **unchanged**.
4. We run `compute_agreement.py` to calculate **Cohen's kappa** and list every disagreement and every AMBIGUOUS ticket.
5. We meet to discuss each one, decide the final label, and record the reason.
   - If an AMBIGUOUS ticket still cannot be placed in any category, we **remove** it from the golden set and record why. The final set must still have at least 150 tickets.
6. If a disagreement shows that a rule was missing or unclear, we update this protocol, change the version number (v1 → v2) and record the change in Section 7.
7. We commit the final golden set and the final protocol **before any model is run**.

---

## 7. Revision log

| Version | Date | What changed | Why (ticket ID that caused it) |
|---|---|---|---|
| v1 | | First version | – |
| | | | |
