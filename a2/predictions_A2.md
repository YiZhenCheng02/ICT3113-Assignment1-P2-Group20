# Assignment 2 – Prediction Record (P2 Group 20)

**Brief, Step 3 — pre-test predictions**

This document records the predictions made before any Assignment 2 accuracy or speed tests. The predictions should not be changed after testing; actual outcomes should be compared against them on slide 7.

**Commit Hash:**

**Date:** 27 November 2026

## Selected models

- **Small model:** `qwen2.5:3b`
- **Large model:** `qwen2.5:7b`

## What the predictions are based on

The predictions are based on existing information only; no live Assignment 2 measurements are included.

- The accuracy limits in `a2/limits.json`: at least **76/92 (82.6%)** overall, with a minimum accuracy requirement for each category.
- The cascade tuning results from `python a2/tune_cascade.py`, using 93 tuning tickets and Assignment 1 records.
- Assignment 1 one-at-a-time response-time measurements for the tuning tickets.
- The committed speed-test workload in `a2/workload_rows.csv`, which has a median ticket length of 174 words and a mean of 197 words.
- Offline latency simulation using the fitted response-time estimates.

All performance figures below are predictions or simulation estimates, not live Assignment 2 service measurements or JMeter results.

---

## 1. Accuracy requirements and single-model baseline

The accuracy requirements are evaluated using the **92-ticket accuracy test set**.

| Category | Test tickets | Minimum correct | Minimum accuracy |
|---|---:|---:|---:|
| Bank account or service | 15 | 13/15 | 86.7% |
| Consumer loan | 10 | 9/10 | 90.0% |
| Credit card | 13 | 11/13 | 84.6% |
| Credit reporting | 17 | 13/17 | 76.5% |
| Debt collection | 11 | 7/11 | 63.6% |
| Money transfer or service | 13 | 11/13 | 84.6% |
| Mortgage | 13 | 12/13 | 92.3% |
| **Overall** | **92** | **76/92** | **82.6%** |

### Existing single-model results

The following results are based on the saved Qwen predictions for the 92-ticket accuracy test set.

| Model | Correct | Accuracy | Overall requirement |
|---|---:|---:|---|
| `qwen2.5:7b` | 77/92 | 83.7% | Pass |
| `qwen2.5:3b` | 70/92 | 76.1% | Fail |

### Per-category single-model results

| Category | Qwen 7B | Qwen 3B | Required |
|---|---:|---:|---:|
| Bank account or service | 15/15 (100.0%) | 15/15 (100.0%) | 13/15 |
| Consumer loan | 9/10 (90.0%) | 2/10 (20.0%) | 9/10 |
| Credit card | 8/13 (61.5%) | 9/13 (69.2%) | 11/13 |
| Credit reporting | 15/17 (88.2%) | 16/17 (94.1%) | 13/17 |
| Debt collection | 8/11 (72.7%) | 8/11 (72.7%) | 7/11 |
| Money transfer or service | 9/13 (69.2%) | 7/13 (53.8%) | 11/13 |
| Mortgage | 13/13 (100.0%) | 13/13 (100.0%) | 12/13 |

Qwen 7B meets the overall accuracy requirement but does not meet the category requirements for Credit card or Money transfer or service. Qwen 3B does not meet the overall requirement and performs particularly poorly for Consumer loan.

---

## 2. Tuning results

The tuning set contains 93 tickets. The two selected configurations produced the following results:

| Measure | Setting 1 – Strict | Setting 2 – Loose |
|---|---:|---:|
| Configuration | K=4 | K=5 |
| Tickets escalated | 46/93 | 43/93 |
| Escalation percentage | 49.5% | 46.2% |
| Correct predictions | 79/93 | 78/93 |
| Tuning accuracy | 84.9% | 83.9% |

Setting 1 has slightly higher tuning accuracy, while Setting 2 has a lower escalation percentage. The difference in tuning accuracy is small.

These are tuning-set results. They are not the predicted final accuracy results for the 92-ticket accuracy test set.

---

## 3. Latency prediction

The latency prediction uses the 93 tuning tickets and their recorded Assignment 1 response times.

### Timing estimates

| Model | Fitted elapsed time | Correlation | Tuning tickets |
|---|---|---:|---:|
| `qwen2.5:7b` | 1.75 s + 2.36 s per 100 words | 0.967 | 93 |
| `qwen2.5:3b` | 0.93 s + 1.09 s per 100 words | 0.955 | 93 |

Ticket length has a strong relationship with response time for both models.

### Workload prediction

The three S tickets are rows 20481, 20142 and 20163, containing 144, 143 and 145 words respectively.

| Quantity | Prediction |
|---|---:|
| Predicted S | 5.16 s |
| Mean arrival interval (2 × S) | 10.3 s |
| Arrival rate | 5.82 tickets/minute (349/hour) |
| Run duration | 309 s (5.2 minutes) |
| Approximate tickets per run | 30 |
| Workload median ticket length | 174 words |
| Workload mean ticket length | 197 words |

### Simulated latency results

The simulation uses 4,000 runs per configuration, random arrivals and a fixed random seed of 20.

| Configuration | Predicted p50 (mean across runs) | Single-run p50, 10th–90th percentile | Pooled p95 | Utilisation |
|---|---:|---:|---:|---:|
| Qwen 7B alone | 9.8 s | 7.5–12.9 s | 25.7 s | 61% |
| Setting 1 – Strict (K=4) | 10.2 s | 6.4–14.2 s | 29.1 s | 60% |
| Setting 2 – Loose (K=5) | 9.5 s | 5.8–13.6 s | 27.9 s | 58% |

Setting 2 is predicted to have the lowest p50 and pooled p95 among the two cascade configurations. However, both cascade configurations are predicted to have a higher pooled p95 than Qwen 7B alone.

These are simulation estimates. The simulation does not model CPU contention between overlapping model calls, so actual response times may be higher.

---

## 4. Fastest configuration predicted to meet both accuracy limits

**Prediction: Neither cascade setting is expected to meet both the overall and all per-category accuracy requirements.**

Setting 2 – Loose (K=5) is predicted to be the fastest configuration by p50:

- Setting 2: approximately **9.5 s**.
- Qwen 7B alone: approximately **9.8 s**.
- Setting 1 – Strict (K=4): approximately **10.2 s**.

Setting 2 is predicted to be about 3% faster than Qwen 7B alone by p50. However, it is still expected to fail the Credit card and Money transfer or service category requirements.

The offline accuracy predictions are:

- Setting 1: **80/92 (87.0%)**.
- Setting 2: **81/92 (88.0%)**.

Both settings are predicted to pass the overall requirement of 76/92, but neither is predicted to pass every category requirement.

The predicted p50 difference between the two cascade settings is small. Actual results may vary because the simulation does not model CPU contention between overlapping model calls.

---

## 5. Cascade predictions

The following accuracy results were calculated offline by applying the two selected configurations to the saved Qwen 3B and Qwen 7B predictions for the 92-ticket accuracy test set. They are not results from live Assignment 2 endpoint tests.

### Predicted accuracy by category

| Category | Required | Setting 1 – Strict (K=4) | Setting 2 – Loose (K=5) |
|---|---:|---:|---:|
| Bank account or service | 13/15 | 15/15 | 15/15 |
| Consumer loan | 9/10 | 9/10 | 9/10 |
| Credit card | 11/13 | 10/13 | 10/13 |
| Credit reporting | 13/17 | 17/17 | 17/17 |
| Debt collection | 7/11 | 7/11 | 8/11 |
| Money transfer or service | 11/13 | 9/13 | 9/13 |
| Mortgage | 12/13 | 13/13 | 13/13 |
| **Overall** | **76/92** | **80/92 (87.0%)** | **81/92 (88.0%)** |

Both configurations are predicted to exceed the overall accuracy requirement. However, both are predicted to fall short of the required accuracy for:

- **Credit card**
- **Money transfer or service**

Setting 2 is predicted to achieve one more correct classification overall than Setting 1, mainly due to its result for Debt collection. Neither configuration is predicted to meet every per-category accuracy requirement.

### Summary by configuration

| Configuration | Escalation in offline accuracy simulation | Predicted accuracy | Passes overall? | Passes every category? | Predicted p50 | Predicted pooled p95 |
|---|---:|---:|---|---|---:|---:|
| Setting 1 – Strict (K=4) | 54/92 (58.7%) | 80/92 (87.0%) | Yes | No — Credit card and Money transfer or service | 10.2 s | 29.1 s |
| Setting 2 – Loose (K=5) | 46/92 (50.0%) | 81/92 (88.0%) | Yes | No — Credit card and Money transfer or service | 9.5 s | 27.9 s |
| Qwen 7B alone | — | 77/92 (83.7%) | Yes | No — Credit card and Money transfer or service | 9.8 s | 25.7 s |

The escalation counts in this table refer only to the offline accuracy simulation. The escalation rate during the live speed test is not predicted here and should be measured during testing.

The simulation estimates utilisation of approximately 61% for Qwen 7B alone, 60% for Setting 1 and 58% for Setting 2. Actual cascade p50 may be higher than the estimates because overlapping small- and large-model calls compete for CPU resources, which the simulation does not model.

---

## 6. Categories expected to lose accuracy when the small model's answer is accepted

- **Money transfer or service:** This is expected to remain a weak category for both settings. Qwen 3B achieves 7/13, while Qwen 7B achieves 9/13. Both cascade settings are predicted to achieve 9/13, below the required 11/13.
- **Credit card:** Qwen 7B achieves 8/13, while Qwen 3B achieves 9/13. Both cascade settings are predicted to achieve 10/13, which is an improvement over Qwen 7B alone but still below the required 11/13.
- **Consumer loan:** Qwen 3B performs poorly, achieving 2/10 compared with Qwen 7B's 9/10. Both cascade settings are predicted to achieve 9/10, exactly meeting the minimum requirement.
- **Debt collection:** Both single models achieve 8/11. Setting 1 is predicted to achieve 7/11, exactly meeting the minimum, while Setting 2 is predicted to achieve 8/11.

---

## 7. What would prove these predictions wrong (checked on slide 7)

- **Setting 1 has a lower p50 than Qwen 7B alone:** The strict cascade is faster than predicted.
- **Setting 2 does not have a lower p50 than Setting 1:** The loose setting does not provide the expected speed improvement.
- **Either cascade setting meets the Credit card and Money transfer or service requirements (at least 11/13 in each category):** The category-level accuracy prediction was too pessimistic.
- **A cascade setting's overall accuracy is below 76/92:** The prediction that both settings would pass the overall accuracy requirement was incorrect.
- **Requests remain unfinished, or p50 rises steadily during a run:** The speed-test arrival rate may be too high for the service, causing a queue to build.
- **Actual response times are substantially higher than the simulated estimates:** Runtime overhead or CPU contention has a larger effect than the simulation accounts for.

The final comparison should use the actual Assignment 2 accuracy results and JMeter measurements. The simulation figures are estimates and should not be presented as measured performance.
