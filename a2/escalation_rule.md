# Assignment 2 escalation rule

## Method

Category-based escalation. The small model classifies every incoming ticket using the unchanged
Assignment 1 prompt. The service parses the first non-empty output line using the existing strict
seven-category parser.

If the small model's **predicted category** appears in the configured acceptance list for the
selected setting, its prediction is accepted. Otherwise, the ticket is escalated to the large
model, and the large model's prediction is final.

The routing decision never uses the true/golden label, which is unavailable at request time.

## Model pair

- Small model: `llama3.2:3b` (change if the group selects a different pair)
- Large model: `llama3.1:8b` (change if the group selects a different pair)

## Setting 1

Acceptance categories: **TO BE FILLED FROM THE GROUP'S SELECTED TUNING RESULT**

Set `CASCADE_SETTING=1` and `CASCADE_ACCEPT_SETTING_1` in `.env`.

## Setting 2

Acceptance categories: **TO BE FILLED FROM THE GROUP'S SELECTED TUNING RESULT**

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
