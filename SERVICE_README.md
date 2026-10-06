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

**Baseline:** synchronous, one Ollama call per ticket, no caching, no queue, no DB indexes. Ollama runs with `OLLAMA_NUM_PARALLEL=1` and no GPU. Ollama's structured output (`format` = JSON schema with the 7 category names) guarantees every ticket gets one of the 7 categories. The service starts empty on every container start.

## Run it

```bash
cp .env.example .env                 # then edit MODEL / RUN_ID if needed
docker compose up -d --build
docker compose exec ollama ollama pull qwen2.5:1.5b
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

`logs/requests.jsonl` has one line per request (including errors): `ts`, `epoch_ms` (matches JMeter's `timeStamp`), `run_id`, `request_id`, `method`, `path`, `status`, `latency_ms` (total time inside the service), `model`, `model_digest`, and for POST /tickets also `ref`, `category`, `raw_output`, `model_ms`, Ollama timings (`prompt_eval_ms`, `eval_ms`, token counts) and `narrative_words`. **Commit these logs for every run you report.**

**Tip for JMeter (Step 5):** add an HTTP Header Manager with `X-Request-ID: ${__UUID()}`. The service logs that same ID, so every JMeter sample can be matched to exactly one log line.