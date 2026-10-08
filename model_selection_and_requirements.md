# Step 4: Candidate Models and Requirements

## Candidate Models Selection

| Model | Size class | Family | Parameters | Quantisation | Pinned digest | License |
|---|---|---|---|---|---|---|
| `qwen2.5:3b` | Small | Qwen (Alibaba) | ~3B | Q4_K_M | `357c53fb659c5076de1d65ccb0b397446227b71a42be9d1603d46168015c9e4b` | Qwen Research License |
| `llama3.2:3b` | Small | Llama (Meta) | ~3B | Q4_K_M | `a80c4f17acd55265feec403c7aef86be0c25983ab279d83f3bcd3abbcb5b8b72` | Llama 3.2 Community License |
| `qwen2.5:7b` | Large | Qwen (Alibaba) | ~7B | Q4_K_M | `845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e` | Apache 2.0 |
| `llama3.1:8b` | Large | Llama (Meta) | ~8B | Q4_K_M | `46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e` | Llama 3.1 Community License |

The four models form a 2 × 2 design: two size classes (3B and 7–8B) crossed with two model families (Qwen and Llama). Each size class has one model from each family. This lets us separate the effect of model size from the effect of model family. For example, comparing qwen2.5:3b with qwen2.5:7b isolates size, and comparing qwen2.5:7b with llama3.1:8b isolates family at a similar size. 

All four models use the same Q4_K_M quantisation, so differences in speed or accuracy cannot be explained by quantisation.

The size range is chosen to make the client's trade-off visible on CPU-only hardware. The 3B models are expected to be faster and sustain more throughput, but to misclassify more often. The 7–8B models are expected to be more accurate but slower.

## Requirements
Positioning for Step 6:

A misrouted ticket costs the client more than a slow one. A misroute needs a staff member to notice it and re-route it, and it delays the customer's resolution by hours. A classification delay of up to 30 seconds is invisible next to today's process, where every ticket waits for a human to read it. We therefore set loose latency targets (R1, R2) and strict accuracy targets (R5). Our recommendation will weigh R5 above R1 to R4.

### R1: POST /tickets latency
Target: p50 ≤ 10 s, p95 ≤ 30 s, p99 ≤ 60 s, computed on all successful POSTs from the three runs pooled together. 

Load condition: 19 POST/hour and 29 GET /search per hour, arriving open-loop at the same time. 

How measured:
- JMeter records the elapsed time of each HTTP 201 response.
- Ticket narratives are drawn from a shuffled pool of our 1,000 rows.
- OLLAMA_KEEP_ALIVE=-1, so the model stays loaded for the whole run.
- Each run lasts 30 minutes after a warm-up. These are the same runs as R2, set up as described in R2.
- For each run we report p50, p95, p99, achieved POST/hour, error rate and sample count, then the mean and the min-to-max spread across the three runs.
- The target is checked on the pooled samples, about 28 POSTs.
With about 28 samples, p99 equals the slowest observed request. We report it, but treat it as indicative rather than precise.

Justification: 19/hour is the busiest hour in the Capital One CFPB complaint data from October 2025 to October 2026. 29/hour is 19 × 1.5 searches per ticket, which is an assumption explained in our workload model.

POST /tickets is called by the client's intake system, not by an agent. Common reverse proxies such as nginx cut off requests after 60 seconds by default. p99 ≤ 60 s therefore means almost no classification would be cut off by a standard gateway, and p95 ≤ 30 s keeps a safety margin below that. p50 ≤ 10 s means a typical ticket is routed long before any human would have read it.

### R2: GET /search latency
Target: p50 ≤ 1 s, p95 ≤ 5 s, p99 ≤ 10 s, computed on all successful searches from the three runs pooled together.

Load condition: the same runs as R1: 29 GET/hour and 19 POST/hour open-loop, with 100 tickets already stored at the start of each run.

How measured: before each of the three runs:
- Restart the service with docker compose down, then docker compose up -d. The service deletes its ticket database on every start (service/Dockerfile:13), so each run begins with an empty store. 
- Post 100 tickets through POST /tickets using the model under test. These seeding requests appear in the service log but are excluded from results.
- Warm up the model.
- Start the 30-minute run.

JMeter records the elapsed time of each HTTP 200 response. Search terms are words drawn from the ticket narratives and kept in a CSV file. For each run we report p50, p95, p99, achieved GET/hour, error rate and sample count, separately from POST results, then the mean and spread. The target is checked on the pooled samples, about 44 searches. 

Justification: 29/hour is the search rate from our workload model. 100 stored tickets is about one day of client volume (about 92 per day).

The targets follow Nielsen's response-time limits. Within 1 second, a user's flow of thought is not interrupted, which sets p50 ≤ 1 s. Within 10 seconds, a user stays focused on the task, which sets p99 ≤ 10 s.

Limitation: a real ticket store would hold thousands of tickets. Search performance on a larger store is not tested in this assignment.

### R3: Maximum throughput
Target: ≥ 32 tickets/hour, averaged over three runs.

Load condition: POSTs from the whole pool arrive open-loop at N = 2,300 POST/hour, which is more than any candidate can process, with 29 GET/hour alongside.

How measured:
- Before each run, restart the containers and warm up the model.
- Each run lasts exactly 6 minutes.
- Achieved throughput = HTTP 201 completions in the final 3 minutes × 20.
- At the 6-minute mark, the containers are stopped with docker compose down to clear the queue. Any request still waiting for a response is counted as "unfinished". Unfinished requests are not errors and are excluded from latency.
- A run is valid only if achieved throughput is below 2,070 tickets/hour (90% of N). This proves the model was overloaded. If not, raise N and rerun.
- Three runs. For each, report achieved tickets/hour, p50, p95, p99, error rate and unfinished count, then the mean and spread, and headroom = achieved ÷ 19.

Justification: N = 2,300 is 1.5 × the fastest model's estimated throughput (about 1,500 tickets/hour from our smoke tests). This ensures every model is overloaded, so the measured number is its true maximum.

The target allows for growth. In the CFPB database, Capital One received 20,493 complaints in 2024 and 34,102 in 2025, a growth factor of 34,102 ÷ 20,493 = 1.66. If the busiest hour grows at the same rate for one more year, it becomes 19 × 1.66 = 31.6, rounded up to 32 tickets/hour. The headroom figure shows how far each model is above today's observed peak.

### R4: Worst-case throughput (long tickets)
Target: ≥ 19 tickets/hour, averaged over three runs.

Load condition: the same as R3 (N = 2,300 POST/hour, with 29 GET/hour), but narratives are drawn only from pool tickets longer than 1,227 characters, about 250 tickets.

How measured: the same procedure as R3, including the 6-minute run, the container stop, the unfinished rule and the validity rule. Narratives come from a separate shuffled file, jmeter_long.csv, and each narrative is sent at most once per run. Three runs. For each, report achieved tickets/hour, p50, p95, p99, error rate and unfinished count, then the mean and spread, and the ratio to R3's result.

Justification: 1,227 characters is the 75th percentile of ticket length in our workload model, and the longest ticket is 1,989 characters. Longer tickets take longer to process, so throughput is lowest here. 19/hour is the observed peak, so a model must keep up with the busiest hour even if every ticket were long.

### R5: Classification quality
Target:
- Overall accuracy ≥ 75%.
- In each of the 7 categories, recall ≥ 70% and precision ≥ 70%.
- Invalid outputs ≤ 1% of the 185 tickets, which means at most 1 ticket.

Load condition: all 185 frozen golden-set tickets, each sent once through POST /tickets.

How measured: failed requests and invalid outputs count as incorrect, and the denominator stays 185. A category that is never predicted has precision 0. We report overall accuracy, per-category recall and precision, a confusion matrix, and the invalid-output count.

Justification: the target is set from how well trained humans perform the same task. Our two labellers, following the same written protocol, agreed directly on 146 of the 185 tickets kept in the golden set (78.9%) before resolving disagreements. Across all 200 tickets labelled, raw agreement was 75.5% and Cohen's kappa was 0.716.

A model cannot reasonably be expected to agree with our final labels more often than our own labellers agreed with each other. We therefore set the overall target at 75%, close to human agreement but leaving a small margin. At about 92 tickets per day, 75% accuracy means roughly 23 misrouted tickets per day that need manual re-routing.

The 70% per-category floor stops any single category from being routinely wrong while the overall figure looks fine. Following our position above, this is the requirement our recommendation weighs most heavily.
The golden set has 185 tickets, but categories are not equal in size, so one wrong ticket matters more in small categories:

#### Golden-Set Thresholds

| Category | Golden tickets | One ticket moves recall by | Correct needed for ≥70% recall | Most wrong allowed |
|---|---:|---:|---:|---:|
| Credit reporting | 43 | 2.3 percentage points | 31 | 12 |
| Debt collection | 18 | 5.6 percentage points | 13 | 5 |
| Mortgage | 24 | 4.2 percentage points | 17 | 7 |
| Credit card | 21 | 4.8 percentage points | 15 | 6 |
| Bank account or service | 27 | 3.7 percentage points | 19 | 8 |
| Consumer loan | 24 | 4.2 percentage points | 17 | 7 |
| Money transfer or service | 28 | 3.6 percentage points | 20 | 8 |
| **Overall accuracy** | **185** | **0.5 percentage points** | **139 for ≥75% accuracy** | **46** |

Debt collection is the smallest category, so its recall is the least precise: one ticket moves it by 5.6 points. We will note this when interpreting its result.

### Definitions
Latency
- Latency: the JMeter elapsed time of a request, from sending it to receiving the full response.
- p50 / p95 / p99: the response time that 50% / 95% / 99% of requests finish within.
- Per-run percentiles: p50, p95 and p99 computed on one run's samples. These are reported for every run, along with the mean and - min-to-max spread across the three runs.
- Pooled percentiles: p50, p95 and p99 computed on all samples from the three runs combined. These are used to check the R1 and R2 targets.

What happens to each request
- Every request JMeter sends falls into exactly one of these four groups. For every run, the four counts must add up to the total number of requests sent.

#### Request Outcome Definitions

| Group | What counts | Used in |
|---|---|---|
| **Success** | HTTP 201 for `POST /tickets`; HTTP 200 for `GET /search`. | Latency percentiles and throughput. |
| **Invalid output** | HTTP 502 with the message `"model returned an invalid category"`: the model answered, but not with one of the 7 categories. The ticket is not stored. | Counted against R5 only. Reported as a count in R1 to R4, but not counted as an error. |
| **Infrastructure error** | HTTP 504 (`"model backend timed out"`), HTTP 502 (`"model backend unavailable"`), HTTP 400, HTTP 500, a connection failure, or a JMeter timeout | Error rate in R1 to R4 |
| **Unfinished at cutoff** | A request sent during an R3 or R4 run that had no response when the containers were stopped at the 6-minute mark. JMeter records these as connection errors ending at or after the stop time. | Reported as a count. Not an error, and excluded from latency. |

#### Rates and throughput
- Error rate: infrastructure errors ÷ (all requests sent − unfinished requests).
- Achieved throughput (R1, R2): successful requests ÷ run length, in requests per hour.
- Achieved throughput (R3, R4): HTTP 201 completions in the final 3 minutes of the run × 20, in tickets per hour.
- Headroom: achieved throughput ÷ 19, the observed peak. A headroom of 10 means the model can handle 10 times the busiest observed hour.

#### Test setup
- Open-loop: JMeter sends requests at a fixed arrival rate, no matter how slowly the service responds. This shows queue build-up, because a slow server does not reduce the number of incoming requests.
- Tested arrival rates: R1 and R2 at 19 POST/hour + 29 GET/hour. R3 and R4 at N = 2,300 POST/hour (the same for every model) + 29 GET/hour.
- Warm-up: one POST /tickets request sent after the model is loaded and before the timed run starts, so the first measured request does not include model loading time. Warm-up requests are excluded from results.
- Run: one timed test of one model at one arrival rate. 30 minutes for R1 and R2, 6 minutes for R3 and R4. Each configuration is run three times.
- Pool: our team's 1,000 dataset rows, used as ticket narratives in load tests.
- Golden set: the 185 frozen tickets with agreed labels, used only for the R5 accuracy test.

#### Accuracy (R5)
- Overall accuracy: tickets classified correctly ÷ 185.
- Recall (per category): of the golden tickets whose correct label is a given category, the share the model classified correctly. This is called per-category accuracy in the brief.
- Precision (per category): of the tickets the model assigned to a given category, the share that truly belong there. A category the model never predicts has precision 0.
- Confusion matrix: a 7 × 7 table of correct label against predicted label. Diagonal cells are correct, and off-diagonal cells show which categories get confused with each other.
