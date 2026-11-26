# Prediction Record – P2 Group 20 (Assignment 2)

**Brief, Step 3.** Committed **before any Assignment 2 test** (accuracy or speed). These predictions are not revised
afterwards; the comparison with the outcomes goes on slide 7. Commit hash: `4360c4a` · Date: 26 November 2026 (no A2 request appears in `logs/requests.jsonl` before this commit)

**What the predictions are based on (no A2 measurement):**

- the accuracy limits (`a2/limits.json`): top model `llama3.1:8b` 85/92 = 92.4% on the test set, so the overall
  limit is **82.4% (≥ 76/92)**, and each category needs: Bank account ≥ 13/15, Consumer loan ≥ 9/10,
  Credit card ≥ 11/13, Credit reporting ≥ 13/17, Debt collection ≥ 7/11, Money transfer ≥ 11/13, Mortgage ≥ 12/13;
- the tuning-set simulation (`python a2/tune_cascade.py`, 93 tuning tickets, A1 records);
- the A1 one-at-a-time timings of the tuning tickets: time grows almost linearly with length
  (`llama3.1:8b` ≈ 1.67 s + 2.59 s per 100 words, r = 0.97; `llama3.2:3b` ≈ 0.94 s + 1.18 s per 100 words, r = 0.98);
- the committed speed-test workload (`a2/workload_rows.csv`: median 174 words, 25% long tickets) and S rows.

A queueing simulation turned those timings into the p50/p95 predictions below: `python a2/predict_latency.py`
(seed 20, so the numbers can be reproduced; random arrivals at the planned rate, one server, the fixed workload order,
4,000 simulated runs per configuration). Response time = waiting time + service time. It ignores the CPU contention
when the small and large model run at the same time, so we expect it to **underestimate** the cascade's latency.

## 1. Already known, not predicted: single models

The single-model test-set accuracy was scored from the A1 prediction records when the limits were set (Step 1, same
environment), so it is a known result, not a prediction:

| Configuration | Test accuracy | Overall limit | Category limits | Speed test? |
|---|---|---|---|---|
| `llama3.1:8b` alone (top) | 85/92 = 92.4% | reference | reference | yes (reference) |
| `qwen2.5:7b` alone | 77/92 = 83.7% | pass | **fail**: Credit card 8/13, Money transfer 9/13 | no |
| `qwen2.5:3b` alone | 70/92 = 76.1% | **fail** | fail (Consumer loan 2/10, …) | no |
| `llama3.2:3b` alone | 68/92 = 73.9% | **fail** | fail (Consumer loan 5/10, …) | no |

So only the top model and the two cascade settings get speed tests.

## 2. Speed-test set-up predictions

| Quantity | Prediction |
|---|---|
| S (median of 3 median-length tickets, `llama3.1:8b`) | **5.4 s** (range 4.5–6.5 s), measured on rows 20481, 20142, 20163 (144, 143, 145 words; chosen by `a2/pick_s_rows.py` as the unused tickets closest to the pool median of 144 words) |
| Arrival rate | one ticket every ~10.8 s ≈ 5.56 per minute (≈ 333/hour, far above the 19/hour A1 client peak) |
| Run length / tickets per run | S minutes = **5.4 minutes (324 s)** / ~30 tickets |
| JMeter timeout / pause | 300 s (10 × S is below the 5-minute minimum) / at least 6 minutes |
| JMeter schedule | `rate(5.56/min) random_arrivals(324 s) pause(6 min)`, recomputed from the measured S |
| Top-model utilisation | ~62%: short queues will still form when tickets arrive close together, but should not keep growing through a run |
| Unfinished or errored requests | 0 in every run |

## 3. Fastest configuration that passes both limits

**Prediction: cascade Setting 1 (strict) is the fastest configuration that passes both limits, but only narrowly.**

- p50 (mean of 3 runs): **cascade-strict ≈ 9.2 s vs top model alone ≈ 10.5 s**, about **12% faster**.
- We expect this gain to be **smaller than the run-to-run spread** (simulated single-run p50 ≈ 7.9–13.9 s for the
  top model and 5.3–13.4 s for strict). The strict cascade does about 10% less CPU work per ticket than the 8B alone
  (≈ 3.3 s small model on every ticket + 42% × 6.8 s large model, vs 6.8 s), so the queues are similar.
- **Setting 2 (loose) will be the fastest overall** (p50 ≈ 5.9 s, ~44% faster than the top model) **but will fail
  the Money transfer per-category limit** (see section 5), so it will not qualify.
- Reasoning in one line: with A1 means of 2.67 s (small) and 5.47 s (large), a cascade only wins if it escalates
  fewer than 51% of tickets; strict (~42%) is just under that, loose (~25%) is well under it.

## 4. Cascade predictions, one row per setting

| Setting | Escalation, accuracy test (92 tickets) | Escalation under load (speed test) | Test accuracy | Passes overall? | Passes every category? | p50 (mean of 3 runs) | Pooled p95 |
|---|---|---|---|---|---|---|---|
| **1 – Strict** | **42%** (35–50%) | **35%** (25–45%) | **84/92 = 91.3%** (82–86) | yes | **yes** | **9.2 s** | **27 s** |
| **2 – Loose** | **25%** (18–32%) | **20%** (12–28%) | **81/92 = 88.0%** (78–83) | yes | **no** (Money transfer) | **5.9 s** | **19 s** |
| Top model alone | – | – | 85/92 (known) | reference | reference | **10.5 s** | **27 s** |

- **Accuracy** = the top model's 85/92 minus the net tickets lost on the tuning set (1 for strict, 4 for loose).
  Assumption: the cascade loses about the same number of tickets relative to the top model on the test set as it did
  on the tuning set (the two sets are the same size).
- **Escalated vs accepted accuracy (accuracy test):** accepted tickets 92–93% correct for strict and ~86% for loose;
  escalated tickets ~82% for both, because escalated tickets are the harder ones the small model doubts.
- **Escalation under load will be lower than in the accuracy test.** Only 3 of the first 30 workload tickets are
  Debt collection or Bank account complaints by their CFPB product (10%), against 21% of the tuning set, and those are
  the predictions that escalate.
- **Measured cascade p50 will be at or above these values**, not below, because overlapping small- and large-model
  calls compete for the same CPU, which the simulation ignores.
- **Memory:** `llama3.2:3b` + `llama3.1:8b` both stay resident (`ollama ps` lists both); the weights are ≈ 6.9 GB, and
  we expect ≈ 8 GB in use with the 4096-token context. `small_load_ms` and `large_load_ms` will be ≈ 0 after warm-up.

## 5. Categories expected to lose the most accuracy when the small model's answer is accepted

1. **Money transfer or service** – loose setting only. The small model calls some Money transfer complaints
   "Bank account or service" (4 of the 10 slipped answers on the tuning set), and the loose setting accepts that.
   Tuning: 13/15 → 11/15. **Prediction: 10/13 on the test set under loose, below the 11/13 limit → FAIL.**
   Under strict it stays at the top model's level (12/13).
2. **Credit reporting** – both settings. The small model calls some Credit reporting complaints "Mortgage" (3 on the
   tuning set), which both settings accept. Tuning: 24/26 → 22/26 (strict), 21/26 (loose).
   **Prediction: 14/17 (strict) and 13/17 (loose) on the test set; both pass, loose only just.**
3. **Credit card may gain** a ticket (7/8 → 8/8 on the tuning set): an example of the small model being right where the
   large one is wrong.

## 6. What would prove these predictions wrong (checked on slide 7)

- Strict p50 ≥ top-model p50 → the cascade did not help even at the strict setting.
- Loose passes Money transfer (≥ 11/13) → it becomes the recommended configuration.
- Any run with unfinished requests, or p50 rising steadily through a run → the rate was too high (a queue built).
- Escalation under load outside the predicted ranges → the workload's category mix behaves differently from tuning.
