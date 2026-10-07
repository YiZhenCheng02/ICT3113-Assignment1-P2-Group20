# Ticket Triage Service – P2 Group 20 (Assignment 1 baseline)

```
 JMeter / curl  ──HTTP──▶  triage (Flask + gunicorn, port 8000)  ──HTTP──▶  ollama (CPU only, port 11434)
 (other machine)                 │                    │
                                 ▼                    ▼
                         data/tickets.db       logs/requests.jsonl
                           (SQLite)          (1 JSON line per request)
```

| Endpoint | What it does |
|---|---|
| `POST /tickets` | Body = one ticket narrative (plain text, or JSON `{"narrative": "...", "ref": "..."}`). Calls Ollama **synchronously**, stores the result, returns `{"id", "category", "model", "request_id"}` (HTTP 201). |
| `GET /search?q=<text>&limit=20` | Stored tickets whose narrative contains `q` (SQLite `LIKE`, newest first). |
| `GET /stats` | Number of stored tickets per category. |
| `GET /health` | Service is up and which model it uses. |

**Baseline:** synchronous, one Ollama call per ticket, no caching, no queue, no DB indexes. Ollama runs with `OLLAMA_NUM_PARALLEL=1` and no GPU. Classification does **not** use Ollama's structured output (`format` / JSON schema); the service calls `/api/generate` for free-text generation at `temperature 0` and then `parse_category()` strictly maps the reply to one of the 7 categories (an unparseable reply is rejected, not stored). The service starts empty on every container start.

## Classification

`POST /tickets` makes one synchronous call to Ollama's `/api/generate` with `stream: false`, `options.temperature = 0` and `options.num_ctx = NUM_CTX` (default `4096`). The model is used for **free-text generation**; no `format`/JSON-schema parameter is sent.

The prompt template is loaded once at startup from `prompts/classify_v1.txt` (`PROMPT_PATH`, default `/app/prompts/classify_v1.txt`; the file is mounted read-only into the container). The service fails fast at startup if the file is missing or does not contain exactly one `{narrative}` placeholder. The ticket text is inserted with a plain string replace of `{narrative}` (never `str.format`), so prompt text is never re-interpreted. The first 12 hex characters of the prompt file's SHA-256 are recorded on every `POST /tickets` log line as `prompt_sha256`, so results can be tied to the exact prompt wording that produced them.

The prompt is a condensed copy of the team's labelling protocol (V2): the human-only steps (who labels, computing agreement, the revision process) are removed, and the human instruction to *mark a ticket ambiguous for later discussion* is replaced with *choose the most likely category*, because the model must always answer with one of the 7 categories.

Parsing is strict (`parse_category()`): it takes the first non-empty line of the reply, strips surrounding quotes/asterisks/backticks and a trailing period, removes an optional leading `Category:`, then compares case-insensitively for **exact** equality with one of the 7 category names. If the reply does not exactly match a category, the service returns **HTTP 502** with `{"error": "model returned an invalid category"}`, does **not** store the ticket, and logs the failure (`error = "invalid model output"`, plus `raw_output`, `model_digest`, `model_ms` and the Ollama stats). Invalid outputs are counted as incorrect in accuracy and reported separately as an **invalid-output rate**; they never enter the stored per-category counts.

**Generation limits in the code:** only `temperature: 0` and `num_ctx` are set in `options`; there is **no `num_predict` output cap**, so output length is bounded only by Ollama's own defaults. The service waits for Ollama with a client timeout of `OLLAMA_TIMEOUT_S` (default `600` s); gunicorn's own timeout is `900` s.

**Pinned versions:** the Ollama image is pinned to `OLLAMA_VERSION` (`0.40.0`) in `.env`, and the context window is set explicitly via `NUM_CTX` (`4096`), both injected through `docker-compose.yml`.

## Run it

```bash
cp .env.example .env                 # then edit MODEL / RUN_ID if needed
docker compose up -d --build
docker compose exec ollama ollama pull qwen2.5:3b
python scripts/smoke_test.py golden_set/team20_rows_20000_20999.csv
```

## Switch candidate model

```bash
docker compose exec ollama ollama pull <tag>
# edit MODEL=<tag> and RUN_ID=<name> in .env, then:
docker compose up -d triage
```

## Start a test run from empty

The database is wiped every time the triage container starts, so a restart = a fresh, empty service:

```bash
# set RUN_ID=<name of this run> in .env, then:
docker compose up -d --force-recreate triage
```

## Logs

`logs/requests.jsonl` has one JSON line per request (including errors). Every line contains:

`ts` (ISO-8601 UTC arrival time), `epoch_ms` (the request **start** time as integer epoch milliseconds, so it matches JMeter's `timeStamp`), `run_id`, `request_id`, `method`, `path`, `status`, `latency_ms` (total time inside the service), `model`.

`POST /tickets` additionally logs `ref`, `narrative_chars`, `narrative_words`, `num_ctx`, `prompt_sha256`, and — on a successful classification — `ticket_id`, `category`, `raw_output`, `model_digest`, `model_ms`, and Ollama timings/token counts (`ollama_total_ms`, `ollama_load_ms`, `prompt_tokens`, `prompt_eval_ms`, `output_tokens`, `eval_ms`). A rejected POST logs `error` instead: `empty narrative` (HTTP 400) or `invalid model output` (HTTP 502, alongside `raw_output`, `model_digest`, `model_ms` and the Ollama stats).

`GET /search` additionally logs `query` and `results` (or `error` when `q` is missing). `GET /stats` and `GET /health` add no extra fields. **Commit these logs for every run you report.**

## Known baseline behaviours (intentional)

These are deliberate for the Assignment 1 baseline (optimising them is Assignment 2):

- SQLite is not tuned: no WAL, no indexes.
- Search is a `LIKE '%q%'` full table scan.
- 1 gunicorn worker with 8 threads.
- `OLLAMA_NUM_PARALLEL=1`.
- No input length limit.
- No retries.

## Assumptions

- The service assumes genuine complaint narratives of roughly 200 to 2,000 characters (the team dataset ranges from 200 to 1,989). It does not enforce this.
- Context overflow, prompt injection and gibberish input are out of scope.
- Timeouts and errors can still occur under overload; they are measured by the load and stress tests.

**Tip for JMeter (Step 5):** add an HTTP Header Manager with `X-Request-ID: ${__UUID()}`. The service logs that same ID, so every JMeter sample can be matched to exactly one log line.