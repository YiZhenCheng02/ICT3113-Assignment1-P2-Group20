# Assignment 2 escalation rule

> **STATUS (A2 outcome):** the brief's memory check is **marginal** for this pair — see
> `a2/memory_check.md`. On a long-lived WSL session every escalation is OOM-killed; after a full
> reboot, a 10-probe stability gate passed (0 kernel kills, 8/8 escalations served). Accuracy was
> measured on the held-out test set: **Setting 1 = 86.96% overall** (Credit card and Money
> transfer fail their per-category floors by one ticket each), **Setting 2 = 89.13% overall**
> (same two one-ticket misses). Both pass the overall limit (82.4%). Every measured run must start
> from a fresh stack (`docker compose down && up`), never a long-lived session.

## Method

Category-based escalation. The small model classifies every incoming ticket using the unchanged
Assignment 1 prompt. The service parses the first non-empty output line using the existing strict
seven-category parser.

If the small model's **predicted category** appears in the configured acceptance list for the
selected setting, its prediction is accepted. Otherwise, the ticket is escalated to the large
model, and the large model's prediction is final.

The routing decision never uses the true/golden label, which is unavailable at request time.

## Model pair

- Small model: `qwen2.5:3b` (Assignment 1 candidate)
- Large model: `qwen2.5:7b` (Assignment 1 candidate)

This is the only pair that satisfies the brief's memory check on the fixed 7.4 GB WSL2 limit:
`ollama ps` shows both resident together (2.2 GB + 5.1 GB = 7.3 GB, ~106 MB free). Every pair
containing an 8B model was OOM-killed (`llama-server process has terminated: signal: killed`) —
both `llama3.2:3b + llama3.1:8b` and `qwen2.5:3b + llama3.1:8b`. See the memory-check evidence in
`a2/memory_check.md`. The originally-predicted pair was `llama3.2:3b → llama3.1:8b`; the model
pair changed only because that pair does not fit, so the frozen prediction record
(`a2/predictions_A2.md`) describes a different pair and is flagged as such.

## Setting 1 (strict)

Accept when the small model's **predicted** category is one of:
**Money transfer or service, Consumer loan, Credit reporting, Credit card**

Everything else is escalated — in practice this escalates predictions of **Debt collection,
Mortgage** and **Bank account or service**. (`k = 4` in `a2/tune_cascade.py`.)

Chosen on the tuning set only (`a2/tuning_set.csv`, 93 tickets; never the test set):
escalated **46/93 = 49.5%**; cascade accuracy **79/93 = 84.9%**; simulated per-ticket mean **5.25 s**,
median **4.11 s**. All represented categories are within the 15 pp tuning tolerance.

Set `CASCADE_SETTING=1` and `CASCADE_ACCEPT_SETTING_1` in `.env`.

## Setting 2 (loose)

Accept when the predicted category is one of (Setting 1 **plus** Debt collection):
**Money transfer or service, Consumer loan, Credit reporting, Credit card, Debt collection**

Everything else is escalated — in practice this escalates predictions of **Mortgage** and
**Bank account or service**. (`k = 5` in `a2/tune_cascade.py`.)

Chosen on the tuning set only (`a2/tuning_set.csv`, 93 tickets):
escalated **43/93 = 46.2%**; cascade accuracy **78/93 = 83.9%**; simulated per-ticket mean **5.01 s**,
median **3.62 s** — below the 5.22 s large-only mean. All represented categories are within the
15 pp tuning tolerance.

Set `CASCADE_SETTING=2` and `CASCADE_ACCEPT_SETTING_2` in `.env`.

## Invalid outputs and backend errors

- If the small model returns text that does not parse to one of the seven categories, escalate
  with reason `invalid_small_model_output`.
- If the small model returns a valid category not in the acceptance list, escalate with reason
  `predicted_category_not_accepted`.
- If the large model returns an invalid category, return HTTP 502 and do not store the ticket.
- Ollama timeout returns HTTP 504; other Ollama request failures return HTTP 502.
- A successfully classified ticket is inserted into SQLite exactly once.

## Logging

Each cascade POST log line records the small model, small prediction, small inference time,
escalation decision/reason, large inference time, final model, final category and total request
latency. Use these service logs to calculate the measured escalation fraction.
