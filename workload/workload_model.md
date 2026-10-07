# Step 3 – Workload Model (P2 Group 20)

**Committed before the first benchmark run.** All numbers are reproduced by `python workload_model.py complaints-2026-10-07_13_39.csv`.
**Legend:** **[S#]** = from a cited source or our data export · **[E]** = our estimate (the method is given next to it)

The brief asks for four things: (1) the number of tickets in a relevant period, (2) peak and non-peak periods, (3) the rate of agent-side searches, and (4) the distribution of ticket lengths.

---

## 0. Who the client is (assumption)

The brief describes "a financial services company whose customer relations desk receives a steady stream of complaint tickets" but doesn't give its size. **We assume the client receives complaints at the same rate as Capital One**, a large US bank and credit card issuer.

- Its complaints are published in the **CFPB Consumer Complaint Database [S1]**, the same source as our course dataset.
- We exported every Capital One complaint received from **8 Oct 2025 to 4 Oct 2026** (`complaints-2026-10-07_13_39.csv`, 33,465 rows).
- The export includes the **exact time each complaint was received** (UTC timestamps), so we can measure hourly peaks from real data instead of guessing.
- Capital One's complaints cover the same products as our seven categories: credit card 39.2%, credit reporting 31.5%, checking/savings 12.2%, debt collection 11.6%, vehicle loan 3.7%, money transfer 1.1% **[S1]**.

## 1. Number of tickets the client receives

Our dataset covers the period from 8 October 2025 to 4 October 2026, giving us **362 days** of complaint data. During this period, we recorded **33,465 complaints** **[S1]**. Based on this data, the estimated annual complaint volume is approximately **33,700 complaints per year**, or about **93 complaints per day**.

| Quantity | Calculation | Value |
|---|---|---|
| Annual volume | 33,465 ÷ 362 × 365 | **≈ 33,739 complaints/year** |
| Average per day | 33,465 ÷ 362 | **≈ 93 complaints/day** |
| Busiest single day | measured | **148 complaints** (15 Jul 2026) |

**Monthly volume is fairly steady.** Full months range from 2,408 to 3,246 complaints, so there is no strong seasonal peak:

| Oct 25* | Nov | Dec | Jan 26 | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep* |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1,813 | 2,464 | 2,744 | 2,985 | 2,408 | 2,885 | 3,246 | 3,173 | 3,055 | 3,179 | 3,041 | 2,464 |

\*Partial or incomplete months: October 2025 starts on the 8th. Late September 2026 has unusually few complaints (as low as 7 a day), probably because the CFPB publishes complaints with a delay. Our annual figure may therefore be **slightly understated**.

**Cross-check:** TSB, a mid-sized UK bank, publishes the complaints it receives **directly**: 30,781 in H1 2026, about 61,600 a year **[S2]**. Our figure is the same order of magnitude, so it is plausible. It is probably a **lower bound**, because CFPB figures only include complaints customers escalate to the regulator. The surge level in Section 2 covers this risk.

## 2. Peak and non-peak periods

To understand how complaint traffic varies, we built a table with **one row for every hour** of the 362 days (362 × 24 = **8,688 rows**, including hours with zero complaints) and counted the complaints in each. The table is saved as `hourly_counts.csv` (columns: Date, Hour of the Day, Number of Complaints), so it can be checked in Excel.

| Hourly arrival rate (all 8,688 hours together) | Tickets/hour |
|---|---|
| Mean | 3.9 (≈ 4) |
| Median | 3 |
| 95th percentile | **10** |
| 99th percentile | 13 |
| Maximum observed | **19** (reached in 2 hours, e.g. 8 Jul 2026, 16:00–17:00 US Eastern) |

- **Typical hour:** about **4 tickets/hour** (mean 3.9; the median is 3).
- **Busy hours:** 95% of hours had **10 or fewer** tickets.
- **Peak:** the busiest hour had **19** tickets, so we use **19 tickets/hour as the observed peak workload**.

**When is the peak?** The timestamps in the export are in **UTC**. The busiest UTC hours are 16:00–21:00, which is **12:00–17:00 US Eastern time**: the customer's working day, not the evening.

**Per hour of the day:** for each of the 24 hours, we took its 362 values (one per day), sorted them and took the middle value. With 362 values, the median is the average of the 181st and 182nd values. US Eastern time:

| Hour (ET) | 00 | 01 | 02 | 03 | 04 | 05 | 06 | 07 | 08 | 09 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Median** | 2 | 2 | 1 | 1 | 1 | 2 | 1 | 1 | 2 | 4 | 5 | **6** | **6** | **6** | **6** | **6** | **6** | **6** | 5 | 4 | 4 | 4 | 3 | 3 |
| Mean | 2.2 | 1.7 | 1.7 | 1.1 | 1.0 | 2.3 | 1.2 | 1.5 | 2.3 | 3.9 | 5.2 | 6.0 | 6.2 | 6.3 | 6.4 | 6.4 | 6.4 | 6.0 | 5.3 | 4.4 | 4.4 | 4.1 | 3.4 | 2.9 |
| p95 | 5 | 4 | 4 | 3 | 3 | 6 | 3 | 4 | 6 | 8 | 11 | 12 | 12 | 12 | 12 | 12 | 13 | 11 | 11 | 8 | 9 | 9 | 7 | 6 |
| Max | 7 | 6 | 8 | 4 | 9 | 11 | 5 | 6 | 8 | 12 | 13 | 17 | **19** | 16 | 15 | 17 | **19** | 14 | 14 | 13 | 14 | 12 | 11 | 9 |

*In US Eastern time, hours 01 and 02 have 363 and 361 values instead of 362 because of the daylight-saving switches. The UTC version of this table is printed by the script.*

- **Quietest:** 02:00–08:00 ET, with a median of 1–2 tickets/hour.
- **Peak period:** **11:00–18:00 ET**, with a median of 6 tickets/hour and busy hours (p95) of 12–13.

| Day (US Eastern) | Mon | Tue | Wed | Thu | Fri | Sat | Sun |
|---|---|---|---|---|---|---|---|
| Average tickets/day | 107.7 | **113.4** | 112.1 | 104.8 | 99.7 | 58.3 | 52.5 |

- **Peak period:** **weekdays, 11:00–18:00 US Eastern**. Tuesday and Wednesday are the busiest days.
- **Non-peak period:** nights (18:00–09:00) and weekends. Weekends carry about half the weekday volume, and **82.9%** of complaints arrive Monday–Friday.
- **Measured split:** in weekday business hours (09:00–18:00 ET) the mean is **7.0 tickets/hour** (p95 12). In all other hours it is **2.7/hour**.

**Surge (an addition to the brief) [E]:** the data shows normal operation only. Incidents can be far bigger: after TSB's April 2018 IT failure, the bank received **114,399 complaints** about that one incident **[S3]**. We therefore also define a **surge level of 3 × the observed peak = 57 tickets/hour** for the stress test. This also covers the possibility that CFPB data understates the bank's direct complaints.

## 3. Rate of agent-side searches (`GET /search`)

No relevant data was found for this **[E]**.

- **Assumption:** each ticket requires one initial search, and 50% of tickets require an additional search to find relevant information or previous complaints.
- **Result:** an average of **1.5 searches per ticket**.

| Workload level | Ticket arrival rate | Estimated search rate |
|---|---|---|
| Non-peak (typical hour) | 4 tickets/hour | 6 searches/hour |
| High (95th-percentile hour) | 10 tickets/hour | 15 searches/hour |
| **Peak (max observed hour)** | **19 tickets/hour** | **29 searches/hour** (28.5) |
| Surge (3 × peak) [E] | 57 tickets/hour | 86 searches/hour (85.5) |

## 4. Expected distribution of ticket lengths

Measured on our team's **1,000 rows (20000–20999)** of the course dataset:

| Ticket length (word count) | Number of tickets |
|---|---|
| 0–100 words | 299 |
| 101–250 words | 549 |
| 251–500 words | 152 |
| 501–1,000 words | 0 |
| > 1,000 words | 0 |
| **Total** | **1,000** |

| Statistic | Mean | Min | **Median** | p90 | **p95** | p99 | Max |
|---|---|---|---|---|---|---|---|
| Words | 156.9 | 32 | **142** | 278 | **304** | 359 | 387 |
| Characters | 881 | 200 | **792** | 1,563 | **1,717** | 1,932 | 1,989 |

- **Right-skewed:** most tickets are 50–250 words, with a tail up to 387 words.
- **Why it matters:** on a CPU the model reads every word, so longer tickets should take longer. The service logs each ticket's length (`narrative_words`, `prompt_tokens`), so we can check this later.
- **Limitation:** the course extract only contains narratives of 200–2,000 characters, so real-world tickets could be longer.

## 5. Summary: load levels for Steps 4 and 5

JMeter needs rates per minute.

| Load level | Tickets/hour | Tickets/min | Searches/hour | Searches/min | Use |
|---|---|---|---|---|---|
| Non-peak | 4 | 0.07 | 6 | 0.10 | typical service |
| High | 10 | 0.17 | 15 | 0.25 | busy hour |
| **Peak** | **19** | **0.32** | **29** | **0.48** | **requirements must hold here** |
| Surge [E] | 57 | 0.95 | 86 | 1.43 | stress test: what happens on a bad day |

**Our position:** the requirements in Step 4 are set at the **observed peak of 19 tickets/hour together with 29 searches/hour**. The surge level is used to find out how much headroom the system has.

---

## Sources

- **[S1]** Consumer Financial Protection Bureau, *Consumer Complaint Database*, company = Capital One Financial Corporation, date received 8 Oct 2025 – 7 Oct 2026, exported 7 Oct 2026 (`complaints-2026-10-07_13_39.csv`). https://www.consumerfinance.gov/data-research/consumer-complaints/search/?company=CAPITAL%20ONE%20FINANCIAL%20CORPORATION&date_received_max=2026-10-07&date_received_min=2025-10-08
- **[S2]** TSB Bank plc, *Complaints data*, 1 Jan – 30 Jun 2026. https://www.tsb.co.uk/help-and-support/service-quality/complaints.html
- **[S3]** MoneyExpert, "TSB issues customers compensation after 2018 meltdown". https://www.moneyexpert.com/news/tsb-issues-customers-compensation-2018-meltdown/
- Course dataset: CFPB Consumer Complaint Database extract (ICT3113), rows 20000–20999.