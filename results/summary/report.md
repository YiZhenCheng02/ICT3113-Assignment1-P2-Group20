# Load test analysis

Percentiles: **nearest-rank** (value at position ceil(p*n) in the sorted list).
Times in seconds unless stated. R3/R4 runs are 360 s (6 min); 'unfinished' = non-HTTP/SocketException POSTs aborted at the run cut (their recorded end times all fall within ~0.2 s of T0+360000 ms).

## R1 - POST latency (targets: p50<=10, p95<=30, p99<=60 s)

Each run sent exactly 4 POST arrivals (rate 16/h; JMeter rounds rate x duration down), so the pooled sample is n=12 POST per model.

| model | pooled n | pooled p50 | pooled p95 | pooled p99 | per-run p50 | per-run p95 | per-run p99 | achieved/h | PASS/FAIL |
|---|---|---|---|---|---|---|---|---|---|
| qwen3b | 12 | 1.908 | 2.997 | 2.997 | 1.884 (1.858-1.908) | 2.936 (2.895-2.997) | 2.936 (2.895-2.997) | 16.0 (16.0-16.0) | PASS |
| llama3b | 12 | 1.910 | 3.224 | 3.224 | 1.846 (1.789-1.910) | 3.094 (2.997-3.224) | 3.094 (2.997-3.224) | 16.0 (16.0-16.0) | PASS |
| qwen7b | 12 | 3.672 | 6.114 | 6.114 | 3.458 (3.318-3.672) | 5.827 (5.644-6.114) | 5.827 (5.644-6.114) | 16.0 (16.0-16.0) | PASS |
| llama8b | 12 | 4.026 | 6.338 | 6.338 | 3.879 (3.726-4.026) | 6.150 (6.024-6.338) | 6.150 (6.024-6.338) | 16.0 (16.0-16.0) | PASS |

## R2 - GET latency (targets: p50<=1, p95<=5, p99<=10 s)

Each run sent exactly 7 GET arrivals (rate 28/h), so the pooled sample is n=21 GET per model.

| model | pooled n | pooled p50 | pooled p95 | pooled p99 | per-run p50 | per-run p95 | per-run p99 | achieved/h | PASS/FAIL |
|---|---|---|---|---|---|---|---|---|---|
| qwen3b | 21 | 0.051 | 0.070 | 0.123 | 0.046 (0.037-0.054) | 0.083 (0.059-0.123) | 0.083 (0.059-0.123) | 28.0 (28.0-28.0) | PASS |
| llama3b | 21 | 0.048 | 0.112 | 0.142 | 0.046 (0.039-0.050) | 0.105 (0.062-0.142) | 0.105 (0.062-0.142) | 28.0 (28.0-28.0) | PASS |
| qwen7b | 21 | 0.049 | 0.103 | 0.112 | 0.050 (0.047-0.055) | 0.091 (0.057-0.112) | 0.091 (0.057-0.112) | 28.0 (28.0-28.0) | PASS |
| llama8b | 21 | 0.055 | 0.110 | 0.306 | 0.055 (0.054-0.057) | 0.159 (0.061-0.306) | 0.159 (0.061-0.306) | 28.0 (28.0-28.0) | PASS |

## R3 - sustained POST (target: achieved >= 32/h)

| model | sent | success | invalid | infra | unfinished | achieved/h | p50 | p95 | p99 | error rate | PASS/FAIL |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3b | 229 (229-229) | 136 (135-137) | 0 (0-0) | 0 (0-0) | 93 (92-94) | 1446.7 (1440.0-1460.0) | 78.527 (66.164-91.654) | 127.813 (124.289-131.486) | 133.644 (128.448-136.785) | 0.0000 (0.0000-0.0000) | PASS |
| llama3b | 229 (229-229) | 134 (134-134) | 0 (0-0) | 0 (0-0) | 95 (95-95) | 1420.0 (1420.0-1420.0) | 84.661 (74.662-91.596) | 147.840 (137.720-153.436) | 152.764 (145.111-157.348) | 0.0000 (0.0000-0.0000) | PASS |
| qwen7b | 229 (229-229) | 64 (64-64) | 0 (0-0) | 0 (0-0) | 165 (165-165) | 660.0 (660.0-660.0) | 125.453 (121.962-130.833) | 241.691 (236.095-250.244) | 254.985 (250.544-262.232) | 0.0000 (0.0000-0.0000) | PASS |
| llama8b | 229 (229-229) | 59 (58-60) | 0 (0-0) | 0 (0-0) | 170 (169-171) | 606.7 (600.0-620.0) | 130.979 (119.484-138.479) | 248.486 (239.284-258.463) | 256.990 (248.800-271.518) | 0.0000 (0.0000-0.0000) | PASS |

R3 GET pooled p50 (all models): 60.800 s (n=10)

## R4 - sustained POST (target: achieved >= 19/h)

| model | sent | success | invalid | infra | unfinished | achieved/h | p50 | p95 | p99 | error rate | PASS/FAIL |
|---|---|---|---|---|---|---|---|---|---|---|---|
| qwen3b | 229 (229-229) | 90 (89-92) | 0 (0-0) | 0 (0-0) | 139 (137-140) | 913.3 (900.0-940.0) | 112.369 (101.843-117.662) | 207.823 (197.318-219.230) | 219.068 (207.284-230.717) | 0.0000 (0.0000-0.0000) | PASS |
| llama3b | 229 (229-229) | 87 (87-88) | 0 (0-0) | 0 (0-0) | 142 (141-142) | 880.0 (880.0-880.0) | 110.378 (109.011-112.560) | 210.687 (199.803-224.427) | 221.363 (210.945-234.600) | 0.0000 (0.0000-0.0000) | PASS |
| qwen7b | 229 (229-229) | 44 (43-44) | 0 (0-0) | 0 (0-0) | 185 (185-186) | 453.3 (440.0-460.0) | 147.045 (137.085-153.164) | 271.647 (269.305-274.950) | 285.107 (283.516-287.646) | 0.0000 (0.0000-0.0000) | PASS |
| llama8b | 229 (229-229) | 41 (41-41) | 0 (0-0) | 0 (0-0) | 188 (188-188) | 420.0 (420.0-420.0) | 149.933 (146.914-152.478) | 281.833 (276.824-287.537) | 298.989 (294.570-303.394) | 0.0000 (0.0000-0.0000) | PASS |

| model | R4/R3 ratio | headroom (R3 mean / 19) |
|---|---|---|
| qwen3b | 0.631 | 76.14 |
| llama3b | 0.620 | 74.74 |
| qwen7b | 0.687 | 34.74 |
| llama8b | 0.692 | 31.93 |

## R5 - accuracy (pass if overall>=75%, every category recall>=70% and precision>=70%, invalid<=1)

| model | accuracy | min recall | min precision | invalid | PASS/FAIL |
|---|---|---|---|---|---|
| qwen3b | 71.35% | 12.5% | 54.2% | 0 | FAIL |
| llama3b | 72.43% | 54.2% | 33.3% | 0 | FAIL |
| qwen7b | 85.41% | 66.7% | 69.2% | 0 | FAIL |
| llama8b | 90.81% | 66.7% | 85.7% | 0 | FAIL |

Per-category recall / precision (values below 70% marked with `*`):

**qwen3b** (accuracy 71.35%):

| category | recall | precision |
|---|---|---|
| Credit reporting | 90.7% | 79.6% |
| Debt collection | 55.6%* | 90.9% |
| Mortgage | 100.0% | 58.5%* |
| Credit card | 71.4% | 88.2% |
| Bank account or service | 96.3% | 54.2%* |
| Consumer loan | 12.5%* | 75.0% |
| Money transfer or service | 53.6%* | 100.0% |

**llama3b** (accuracy 72.43%):

| category | recall | precision |
|---|---|---|
| Credit reporting | 60.5%* | 96.3% |
| Debt collection | 88.9% | 33.3%* |
| Mortgage | 95.8% | 85.2% |
| Credit card | 76.2% | 94.1% |
| Bank account or service | 85.2% | 65.7%* |
| Consumer loan | 54.2%* | 92.9% |
| Money transfer or service | 60.7%* | 100.0% |

**qwen7b** (accuracy 85.41%):

| category | recall | precision |
|---|---|---|
| Credit reporting | 88.4% | 88.4% |
| Debt collection | 66.7%* | 75.0% |
| Mortgage | 100.0% | 92.3% |
| Credit card | 66.7%* | 93.3% |
| Bank account or service | 100.0% | 69.2%* |
| Consumer loan | 91.7% | 88.0% |
| Money transfer or service | 75.0% | 100.0% |

**llama8b** (accuracy 90.81%):

| category | recall | precision |
|---|---|---|
| Credit reporting | 90.7% | 86.7% |
| Debt collection | 66.7%* | 85.7% |
| Mortgage | 100.0% | 96.0% |
| Credit card | 90.5% | 90.5% |
| Bank account or service | 92.6% | 86.2% |
| Consumer loan | 100.0% | 92.3% |
| Money transfer or service | 89.3% | 100.0% |

Failed conditions per model:

- qwen3b: FAIL — overall accuracy 71.35% < 75%; recall<70%: Debt collection, Consumer loan, Money transfer or service; precision<70%: Mortgage, Bank account or service
- llama3b: FAIL — overall accuracy 72.43% < 75%; recall<70%: Credit reporting, Consumer loan, Money transfer or service; precision<70%: Debt collection, Bank account or service
- qwen7b: FAIL — recall<70%: Debt collection, Credit card; precision<70%: Bank account or service
- llama8b: FAIL — recall<70%: Debt collection

## Prediction checks

| prediction | measured | verdict |
|---|---|---|
| P1 qwen3b: median & min model_ms/latency >= 0.90 | median=0.996 min=0.989 | CORRECT |
| P1 llama3b: median & min model_ms/latency >= 0.90 | median=0.996 min=0.993 | CORRECT |
| P1 qwen7b: median & min model_ms/latency >= 0.90 | median=0.999 min=0.997 | CORRECT |
| P1 llama8b: median & min model_ms/latency >= 0.90 | median=0.999 min=0.997 | CORRECT |
| P2 qwen3b: pooled POST p95 <= 2 * pooled p50 | p95=2.997 2*p50=3.816 | CORRECT |
| P2 llama3b: pooled POST p95 <= 2 * pooled p50 | p95=3.224 2*p50=3.820 | CORRECT |
| P2 qwen7b: pooled POST p95 <= 2 * pooled p50 | p95=6.114 2*p50=7.344 | CORRECT |
| P2 llama8b: pooled POST p95 <= 2 * pooled p50 | p95=6.338 2*p50=8.052 | CORRECT |
| P3 qwen3b: pooled GET p95 < 0.5 s | p95=0.070 | CORRECT |
| P3 llama3b: pooled GET p95 < 0.5 s | p95=0.112 | CORRECT |
| P3 qwen7b: pooled GET p95 < 0.5 s | p95=0.103 | CORRECT |
| P3 llama8b: pooled GET p95 < 0.5 s | p95=0.110 | CORRECT |
| P4 qwen3b: R3 mean within +-20% of 1500 | measured=1447 | CORRECT |
| P4 llama3b: R3 mean within +-20% of 1440 | measured=1420 | CORRECT |
| P4 qwen7b: R3 mean within +-20% of 800 | measured=660 | CORRECT |
| P4 llama8b: R3 mean within +-20% of 750 | measured=607 | CORRECT |
| P4: both 3B >= 1.6x both 7-8B | see R3 achieved | CORRECT |
| P5 qwen3b: R4/R3 ratio in 0.60-0.85 | ratio=0.631 | CORRECT |
| P5 llama3b: R4/R3 ratio in 0.60-0.85 | ratio=0.620 | CORRECT |
| P5 qwen7b: R4/R3 ratio in 0.60-0.85 | ratio=0.687 | CORRECT |
| P5 llama8b: R4/R3 ratio in 0.60-0.85 | ratio=0.692 | CORRECT |
| P6: zero 504 & zero backend-unavailable 502 in R3/R4 | 504=0 backend502=0 | CORRECT |
| P7 qwen3b: sent~230 & unfinished~80 (+-20%) | sent=229 unfinished=93 | CORRECT |
| P7 llama3b: sent~230 & unfinished~80 (+-20%) | sent=229 unfinished=95 | CORRECT |
| P7 qwen7b: sent~230 & unfinished~150 (+-20%) | sent=229 unfinished=165 | CORRECT |
| P7 llama8b: sent~230 & unfinished~150 (+-20%) | sent=229 unfinished=170 | CORRECT |
| P8: R3 GET pooled p50 > 30 s | p50=60.800 s | CORRECT |
| Latency qwen3b: pooled R1 POST p50 in 1.9-3.1 s | p50=1.908 | CORRECT |
| Latency llama3b: pooled R1 POST p50 in 1.9-3.1 s | p50=1.910 | CORRECT |
| Latency qwen7b: pooled R1 POST p50 in 3.4-5.6 s | p50=3.672 | CORRECT |
| Latency llama8b: pooled R1 POST p50 in 3.8-6.3 s | p50=4.026 | CORRECT |
| Accuracy qwen3b: in 68-72% | 71.35% | CORRECT |
| Accuracy llama3b: in 63-67% | 72.43% | WRONG |
| Accuracy qwen7b: in 75-79% | 85.41% | WRONG |
| Accuracy llama8b: in 73-77% | 90.81% | WRONG |
| H1: Credit reporting lowest precision (>=3/4) and <70% all | lowest_in=0/4 all_lt70=False | WRONG |
| H2: Bank<->Money largest non-credit confusion (>=3/4); both 3B recall<70% in one | largest=2/4 recall_ok=2/2 | WRONG |
| H3: Mortgage highest recall (>=3/4) | mortgage_highest=4/4 | CORRECT |

## Clock skew (JMeter vs service log)

Matched the 4 POST 201 samples per R1/R2 run to the 4 service-log POST 201 lines, k-th to k-th in time order (48 pairs). skew = log epoch_ms - JMeter timeStamp (both are request-start times).

| metric | value |
|---|---|
| matched pairs | 48 |
| median skew (Computer 1 ahead of Computer 2) | +1.391 s |
| min / max skew | -0.028 / +1.586 s |
| JMeter elapsed - log latency_ms (median / max) | 0.114 / 0.325 s |

## Reconciliation (JMeter POST vs service-log POST per run)

R1/R2: JMeter and the service log both record exactly 4 POST 201 per run (12 runs), so they reconcile directly.

R3/R4: requests still being processed when JMeter ended its schedule at T0+360 s were aborted by the client (SocketException = unfinished). The service finished some of them after the cut, before the containers were stopped ~30 s later; these are the extra 201s in the service log. Server completion time = epoch_ms + latency_ms - skew. A run reconciles when the server-side 201s completed at or before the cut equal JMeter's 201 count (+-2 for network delay at the boundary).

| run | JMeter 201 | log 201 total | log 201 before cut | log 201 after cut | result |
|---|---|---|---|---|---|
| r3_qwen2-5-3b_run1 | 137 | 147 | 137 | 10 | RECONCILED |
| r3_qwen2-5-3b_run2 | 135 | 146 | 137 | 9 | RECONCILED |
| r3_qwen2-5-3b_run3 | 135 | 146 | 135 | 11 | RECONCILED |
| r4_qwen2-5-3b_run1 | 92 | 99 | 92 | 7 | RECONCILED |
| r4_qwen2-5-3b_run2 | 90 | 98 | 91 | 7 | RECONCILED |
| r4_qwen2-5-3b_run3 | 89 | 97 | 90 | 7 | RECONCILED |
| r3_llama3-2-3b_run1 | 134 | 144 | 134 | 10 | RECONCILED |
| r3_llama3-2-3b_run2 | 134 | 146 | 135 | 11 | RECONCILED |
| r3_llama3-2-3b_run3 | 134 | 144 | 134 | 10 | RECONCILED |
| r4_llama3-2-3b_run1 | 87 | 94 | 88 | 6 | RECONCILED |
| r4_llama3-2-3b_run2 | 87 | 94 | 88 | 6 | RECONCILED |
| r4_llama3-2-3b_run3 | 88 | 95 | 89 | 6 | RECONCILED |
| r3_qwen2-5-7b_run1 | 64 | 69 | 64 | 5 | RECONCILED |
| r3_qwen2-5-7b_run2 | 64 | 69 | 64 | 5 | RECONCILED |
| r3_qwen2-5-7b_run3 | 64 | 70 | 64 | 6 | RECONCILED |
| r4_qwen2-5-7b_run1 | 44 | 47 | 44 | 3 | RECONCILED |
| r4_qwen2-5-7b_run2 | 43 | 47 | 43 | 4 | RECONCILED |
| r4_qwen2-5-7b_run3 | 44 | 47 | 44 | 3 | RECONCILED |
| r3_llama3-1-8b_run1 | 60 | 65 | 60 | 5 | RECONCILED |
| r3_llama3-1-8b_run2 | 59 | 65 | 60 | 5 | RECONCILED |
| r3_llama3-1-8b_run3 | 58 | 64 | 59 | 5 | RECONCILED |
| r4_llama3-1-8b_run1 | 41 | 44 | 41 | 3 | RECONCILED |
| r4_llama3-1-8b_run2 | 41 | 44 | 41 | 3 | RECONCILED |
| r4_llama3-1-8b_run3 | 41 | 44 | 41 | 3 | RECONCILED |

