# Step 4: Prediction
All predictions below were written before any benchmark run. The latency figures come from a smoke test on 10 tickets that are not in the golden set, so no model had seen any golden-set ticket when this record was written.

## Bottleneck
Main prediction: Ollama inference will be the bottleneck. It will limit POST throughput before anything else does.

Why: each POST /tickets makes one synchronous call to Ollama, and OLLAMA_NUM_PARALLEL=1, so Ollama classifies one ticket at a time. The service runs one Gunicorn worker with 8 threads, so at most 8 POSTs can be waiting on Ollama at once. Any further requests wait in Gunicorn's queue. Our smoke-test medians were 2.4 s, 2.5 s, 4.5 s and 4.8 s for qwen2.5:3b, llama3.2:3b, qwen2.5:7b and llama3.1:8b. If one ticket takes that long and only one is processed at a time, the maximum throughput is 3,600 ÷ time.

## Specific Predictions

| ID | Prediction | How we will check it |
|---|---|---|
| P1 | At the R1 load, Ollama time (`model_ms`) will be at least 90% of total POST time (`latency_ms`) for every model. | Service log fields model_ms and latency_ms |
| P2 | At the R1 load (19 POST/hour), there will be no queue: the model is busy only 1–3% of the time. POST p95 will be no more than 2 × POST p50 for every model. | R1 per-run and pooled percentiles. |
| P3 | At the R1 load, GET /search p95 will be under 0.5 s for every model, because searching 100 stored tickets is fast and 8 threads are enough at this load. | R2 results. |
| P4 | In R3, achieved throughput will be within ±20% of 1,500 / 1,440 / 800 / 750 tickets/hour for `qwen2.5:3b` / `llama3.2:3b` / `qwen2.5:7b` / `llama3.1:8b`. Both 3B models will reach at least 1.6 × the throughput of both 7–8B models. | R3 results by model. |
| P5 | In R4 (long tickets), achieved throughput will be 0.60 to 0.85 × the same model's R3 result. Longer tickets mean more input text for the model to read, but the fixed instructions in the prompt make up part of every request, so throughput drops by less than ticket length grows. | R4 throughput ÷ R3 throughput. |
| P6 | In R3 and R4, there will be zero HTTP 504s and zero "model backend unavailable" 502s. The Ollama timeout is 600 s, and a request waiting at Ollama waits behind at most 7 others: about 8 × 4.8 s ≈ 38 s for the slowest model. Extra requests queue in Gunicorn instead, so they become "unfinished", not errors. | Infrastructure error count |
| P7 | In each R3 run, about 230 POSTs will be sent. About 80 will be unfinished for each 3B model and about 150 for each 7–8B model, within ±20%. | Unfinished count |
| P8 | In R3, GET /search p50 will be over 30 s for every model. Search itself is fast, but each search request waits in Gunicorn's queue behind POSTs that are waiting for Ollama. This shows the Ollama bottleneck spreading to the search endpoint. With about 3 searches per run, this is checked on the pooled results. | R3 GET latency |

## Expected accuracy and latency for each model
Single-request latency: the time from sending POST /tickets to receiving the full response, with the model already loaded, using a ticket from the pool, at the R1 load (so no request waits for another). This is predicted as the median over different tickets and checked against the pooled R1 p50.

| Model | Pinned digest | Single-request latency | Accuracy on golden set |
|---|---|---:|---:|
| `qwen2.5:3b` | `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b` | 2.5 s (1.9–3.1 s) | 70% (68–72%) |
| `llama3.2:3b` | `a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72` | 2.5 s (1.9–3.1 s) | 65% (63–67%) |
| `qwen2.5:7b` | `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` | 4.5 s (3.4–5.6 s) | 77% (75–79%) |
| `llama3.1:8b` | `46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e` | 5.0 s (3.8–6.3 s) | 75% (73–77%) |

A prediction counts as correct if the measured value falls inside the range in brackets. Latency ranges are ±25% and accuracy ranges are ±2percentage points.

Predicted accuracy ranking: qwen2.5:7b, then llama3.1:8b, then qwen2.5:3b, then llama3.2:3b.

Invalid outputs: llama3.2:3b will produce more than 1 invalid output out of 185 and so fail that part of R5. The two Qwen models will produce at most 1 each.

Basis for the latency predictions: we sent 10 different non-golden tickets to each model after a warm-up request, before any benchmark run, and took the median time per ticket. The medians were 2.4 s, 2.5 s, 4.5 s and 4.8 s. We rounded each to the nearest 0.5 s, because ten tickets is a small sample. The 7–8B models took about 1.9 times as long as the 3B models. Their parameter counts alone would suggest about 2.5 times, but we predict the measured ratio, since the smoke test already reflects our hardware.

Basis for the accuracy predictions: no model had been run on the golden set when this was written, so these predictions are based on judgement, for two reasons: 
- Larger models will be more accurate. Our prompt contains a long list of category definitions and edge-case rules taken from our labelling protocol. Applying it correctly means keeping several rules in mind at once, for example "assign to the original product if that problem is unresolved, even if the credit report is mentioned". Larger models generally handle long, multi-condition instructions better than smaller models from the same family. The 3B models are also more likely to grab a single keyword (such as "credit score") instead of applying the full rule.
- Qwen will be more accurate than Llama at the same size. The Qwen2.5 release specifically emphasised improved instruction following and structured output. Our task depends on exactly that: the model must reply with exactly one of seven category names. Llama 3.2 3B was made by shrinking and distilling larger Llama models, so we expect it to lose more of its instruction-following ability than Qwen2.5 3B, which was trained at that size. For this reason we place llama3.2:3b last.
- Ceiling: about 79%. Our two labellers agreed directly on 146 of the 185 golden-set tickets (78.9%) before resolving disagreements. The 39 tickets they disagreed on are the ambiguous ones that our edge-case rules cover, and a model is likely to struggle with the same tickets. We therefore expect even the best model to score at or slightly below the human agreement rate.
- qwen2.5:7b: 77%. This is our strongest candidate, predicted to land 2 points below the ceiling.
- llama3.1:8b: 75%. At this size, we expect a small gap between the two families, so 2 points below qwen2.5:7b.
- qwen2.5:3b: 70%. We expect a 3B model to score about 7 points below the larger model in the same family, because it is more likely to match keywords than apply the full rules.
- llama3.2:3b: 65%. We expect the family gap to be larger at small size, for the reason above, so 5 points below qwen2.5:3b.

## Hardest categories
H1: Credit reporting will be over-predicted. Complaints that also mention an unresolved card or loan problem will often be labelled Credit reporting, because the model sees phrases like "credit score". Our protocol assigns these tickets to the original product while that problem is still unresolved.
Measurable form: Credit reporting will have the lowest precision of the 7 categories for at least 3 of the 4 models, and its precision will be below 70% for all four models.

H2: Bank account or service and Money transfer or service will be confused with each other. This happens when an unauthorised transfer affects a bank account, and the model must decide whether the main complaint is about the transfer or the account.
 Measurable form: for at least 3 of the 4 models, this pair (both directions added together) will be the largest confusion that does not involve Credit reporting. Both 3B models will have recall below 70% in at least one of these two categories.

H3: Mortgage will be the easiest category. Mortgage complaints use distinctive vocabulary (escrow, loan servicer, foreclosure, refinance) that rarely appears in other categories.
 Measurable form: Mortgage will have the highest recall of the 7 categories for at least 3 of the 4 models.

## Predicted outcome against requirements

| Model | R1 | R2 | R3 | R4 | R5 overall accuracy (≥75%) | R5 per-category (≥70%) | R5 result |
|---|---|---|---|---|---|---|---|
| `qwen2.5:3b` | Pass | Pass | Pass | Pass | Fail (70%) | Fail | Fail |
| `llama3.2:3b` | Pass | Pass | Pass | Pass | Fail (65%) | Fail | Fail |
| `qwen2.5:7b` | Pass | Pass | Pass | Pass | Pass (77%) | Fail | Fail |
| `llama3.1:8b` | Pass | Pass | Pass | Pass | Borderline (75%) | Fail | Fail |

Why every model is predicted to pass R1 to R4:
- R1: predicted single-request latency is 2.5 to 5.0 s, well under the 10 s p50 target. At 19 POST/hour the model is busy only 1–3% of the time, so requests almost never wait for each other. By P2, p95 stays within 2 × p50, which is at most about 10 s, well under the 30 s target.
- R2: at this load, search requests do not wait behind POSTs, because 8 threads is more than enough (P3, under 0.5 s).
- R3 and R4: even the slowest predictions (450 to 640 tickets/hour for llama3.1:8b on long tickets) are more than 14 times the targets of 32 and 19 tickets/hour.

Why no model is predicted to pass R5:
- The 3B models fail the overall target. qwen2.5:3b (70%) and llama3.2:3b (65%) are both predicted below 75%. Both are also predicted to fall below 70% recall in Bank account or service or Money transfer or service (H2).
- The 7–8B models fail the per-category floor. qwen2.5:7b (77%) is predicted to pass the overall target, and llama3.1:8b (75%) sits exactly on it. But both are predicted to fail the per-category floor, because Credit reporting will be over-predicted and its precision will fall below 70% (H1).

What this means for our recommendation: if these predictions hold, no candidate meets every requirement. All four pass on speed, so speed cannot separate them. Following our position in Section 2 (a misrouted ticket costs more than a slow one), we would recommend the model closest to meeting R5. We predict this to be qwen2.5:7b, which passes the overall target and fails only on Credit reporting precision.
