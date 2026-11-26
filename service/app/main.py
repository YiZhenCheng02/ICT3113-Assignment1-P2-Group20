"""
Ticket Triage Service - ICT3113 P2 Group 20 (A1 baseline + A2 cascade option)

Endpoints:
    POST /tickets   classify one ticket narrative with the LLM (Ollama), store it, return the category
    GET  /search    return stored tickets whose narrative contains the query text
    GET  /stats     return how many stored tickets there are per category
    GET  /health    quick check that the service is up (not part of the spec, just handy)

This is the BASELINE on purpose (Assignment 1 says "do not pre-optimise"):
    - synchronous: POST /tickets only returns AFTER the model has classified the ticket
    - one Ollama call per ticket, made one after another (no batching)
    - no caching, no queue, no async workers
    - plain SQLite, no indexes, search is a simple LIKE '%q%'
Assignment 2 is where we optimise, so we want this version to be simple and measurable.

ASSIGNMENT 2 CHANGES (brief, Step 2 "Design the Cascade"; search this file for "A2")
    A2 adds ONE thing: an optional two-model CASCADE inside POST /tickets ("The cascade is
    implemented within POST /tickets"). Everything the brief fixes from A1 is untouched: the prompt
    file and its hash, the 7 categories, the strict parser, temperature 0 and num_ctx (NUM_CTX), the
    endpoints and their responses, and there is still no caching of classification results.

    CLASSIFICATION_MODE=single   A1 behaviour: MODEL answers every ticket. Used for the
                                 "top model alone" and "other models alone" configurations.
    CLASSIFICATION_MODE=cascade  SMALL_MODEL answers first. If its PREDICTED category is in the
                                 accept list of CASCADE_SETTING (1 = strict, 2 = loose), that answer
                                 is returned; otherwise the ticket is escalated to LARGE_MODEL, whose
                                 answer is final. The rule and both settings are in
                                 a2/escalation_rule.md (chosen on a2/tuning_set.csv only).

    What changed for A2:
      1. Config block "classification mode": reads the cascade settings and refuses to start on a
         misconfiguration (empty or misspelt accept list), so a run can never be mislabelled.
      2. classify(narrative, model=None): the same A1 call, but it can target either model.
      3. create_ticket(): the routing (small model -> accept, or escalate -> large model).
      4. Logging: every POST line records final_model, escalated and escalation_reason. The brief
         requires the log to show "which model produced the final classification and whether
         escalation occurred", so the escalation fraction can be counted from the logs (slides 4-5).
      5. The response's "model" field is only the configuration label in cascade mode ("the caller
         should not be able to tell which model produced the answer").
    Both cascade models must stay loaded together: docker-compose.yml fixes OLLAMA_MAX_LOADED_MODELS=2.

Every request is logged as one JSON line in logs/requests.jsonl so that every number
in our report can be traced back to a log entry (and matched with the JMeter .jtl files).
"""
import hashlib
import json
import logging
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone

import requests
from flask import Flask, g, jsonify, request

# ---------------------------------------------------------------------------
# Config (all from environment variables, set in docker-compose.yml / .env)
# ---------------------------------------------------------------------------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
MODEL = os.getenv("MODEL", "qwen2.5:3b")                 # the candidate model being tested
DB_PATH = os.getenv("DB_PATH", "/data/tickets.db")
LOG_PATH = os.getenv("LOG_PATH", "/logs/requests.jsonl")
OLLAMA_TIMEOUT_S = float(os.getenv("OLLAMA_TIMEOUT_S", "600"))  # CPU inference can be slow
RUN_ID = os.getenv("RUN_ID", "manual")                    # tag each test run so logs are easy to filter
NUM_CTX = int(os.getenv("NUM_CTX", "4096"))               # Ollama context window (tokens), explicit for reproducibility
PROMPT_PATH = os.getenv("PROMPT_PATH", "/app/prompts/classify_v1.txt")  # classification prompt, read once at startup

CATEGORIES = [
    "Credit reporting",
    "Debt collection",
    "Mortgage",
    "Credit card",
    "Bank account or service",
    "Consumer loan",
    "Money transfer or service",
]

# ---- Assignment 2: classification mode ---------------------------------------------------------
# CLASSIFICATION_MODE=single  -> exactly the A1 behaviour: MODEL answers every ticket.
# CLASSIFICATION_MODE=cascade -> SMALL_MODEL classifies every ticket first (same prompt, same options).
#   If its PARSED category is in the acceptance list of the selected CASCADE_SETTING (1 or 2), that answer
#   is accepted. Otherwise (a category not in the list, or an unparseable reply) the ticket is ESCALATED
#   to LARGE_MODEL, whose answer is final. The decision uses only the small model's predicted category.
CLASSIFICATION_MODE = os.getenv("CLASSIFICATION_MODE", "single").strip().lower()
if CLASSIFICATION_MODE not in ("single", "cascade"):
    raise RuntimeError(f"CLASSIFICATION_MODE must be 'single' or 'cascade', got {CLASSIFICATION_MODE!r}")
CASCADE = CLASSIFICATION_MODE == "cascade"
SMALL_MODEL = os.getenv("SMALL_MODEL", "").strip()
LARGE_MODEL = os.getenv("LARGE_MODEL", "").strip()
CASCADE_SETTING = os.getenv("CASCADE_SETTING", "1").strip()
ACCEPT_CATEGORIES = []
if CASCADE:
    # Fail fast on any misconfiguration: a silent fallback would produce a mislabelled result.
    if not SMALL_MODEL or not LARGE_MODEL:
        raise RuntimeError("cascade mode needs both SMALL_MODEL and LARGE_MODEL")
    if CASCADE_SETTING not in ("1", "2"):
        raise RuntimeError(f"CASCADE_SETTING must be 1 or 2, got {CASCADE_SETTING!r}")
    ACCEPT_CATEGORIES = [c.strip() for c in os.getenv(f"CASCADE_ACCEPT_SETTING_{CASCADE_SETTING}", "").split(",")
                         if c.strip()]
    if not ACCEPT_CATEGORIES:
        raise RuntimeError(f"CASCADE_ACCEPT_SETTING_{CASCADE_SETTING} is empty")
    _unknown = [c for c in ACCEPT_CATEGORIES if c not in CATEGORIES]
    if _unknown:   # a typo would silently escalate every ticket
        raise RuntimeError(f"CASCADE_ACCEPT_SETTING_{CASCADE_SETTING} has unknown categories: {_unknown}")
# What the caller (and the log's "model" field) sees: the model name in single mode, only the configuration
# label in cascade mode, so the caller cannot tell which model produced the answer (brief, Step 2).
SERVICE_MODEL = f"cascade-setting{CASCADE_SETTING}" if CASCADE else MODEL

# The classification prompt is loaded from a file (mounted read-only into the container) so the
# exact wording is versioned and hashed. It is a condensed copy of the team's labelling protocol:
# the human-only steps are removed and "choose the most likely category" replaces the human
# "mark ambiguous" step. Read once at startup; fail fast if it is missing or malformed.
try:
    with open(PROMPT_PATH, "rb") as _prompt_file:
        _PROMPT_BYTES = _prompt_file.read()
except OSError as e:
    raise RuntimeError(f"Could not read classification prompt file {PROMPT_PATH!r}: {e}") from e
PROMPT_TEMPLATE = _PROMPT_BYTES.decode("utf-8")
_prompt_placeholders = PROMPT_TEMPLATE.count("{narrative}")
if _prompt_placeholders != 1:
    raise RuntimeError(
        "Prompt file %r must contain exactly one '{narrative}' placeholder, found %d."
        % (PROMPT_PATH, _prompt_placeholders)
    )
PROMPT_SHA256 = hashlib.sha256(_PROMPT_BYTES).hexdigest()[:12]

# ---------------------------------------------------------------------------
# Logging: one JSON object per line (JSONL). Python's logging module is thread-safe,
# which matters because the web server handles requests on several threads.
# ---------------------------------------------------------------------------
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
req_logger = logging.getLogger("requests_log")
req_logger.setLevel(logging.INFO)
_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(message)s"))
req_logger.addHandler(_handler)
req_logger.propagate = False

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Database helpers (SQLite). A new connection per request keeps it simple and thread-safe.
# ---------------------------------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_db() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS tickets (
                   id            INTEGER PRIMARY KEY AUTOINCREMENT,
                   created_at    TEXT NOT NULL,
                   request_id    TEXT NOT NULL,
                   ref           TEXT,              -- optional caller reference, e.g. dataset row or golden_id
                   narrative     TEXT NOT NULL,
                   category      TEXT NOT NULL,
                   raw_output    TEXT,              -- exactly what the model replied, for debugging
                   model         TEXT NOT NULL,
                   model_digest  TEXT,
                   model_ms      REAL               -- time spent waiting for Ollama
               )"""
        )


# ---------------------------------------------------------------------------
# Model helpers
# ---------------------------------------------------------------------------
_digest_cache = {}


def get_model_digest(model):
    """Look up the exact digest of the model in Ollama, so every log line records
    precisely which model build produced the answer (the brief asks us to pin by digest)."""
    if model in _digest_cache:
        return _digest_cache[model]
    try:
        tags = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10).json().get("models", [])
        for m in tags:
            if m.get("name") == model or m.get("model") == model:
                _digest_cache[model] = m.get("digest")
                return _digest_cache[model]
    except requests.RequestException:
        pass
    return None


# Characters the model may wrap its answer in, e.g. "**Debt collection**" or "`Mortgage`".
_REPLY_TRIM_CHARS = "\"'\u0060*"   # double quote, single quote, backtick, asterisk


def parse_category(text):
    """Strict parser: the model must answer with exactly one of the 7 categories.
    Take the first non-empty line, strip surrounding quotes/asterisks/backticks and a trailing
    period, drop an optional leading "Category:", then compare case-insensitively for EXACT
    equality with a category name. Returns the canonical name on a match, otherwise None.
    There is deliberately no alias or substring matching."""
    if not isinstance(text, str):
        return None
    first = ""
    for line in text.strip().splitlines():
        if line.strip():
            first = line.strip()
            break
    if not first:
        return None
    first = first.strip(_REPLY_TRIM_CHARS).strip()
    if first.endswith("."):
        first = first[:-1].strip()
    if first.lower().startswith("category:"):
        first = first[len("category:"):].strip()
        if first.endswith("."):
            first = first[:-1].strip()
    for category in CATEGORIES:
        if first.lower() == category.lower():
            return category
    return None


def classify(narrative, model=None):
    """ONE synchronous call to Ollama. No retries, no cache, no batching (baseline).
    Returns the raw reply, the wall-clock time and Ollama's own timing stats. Parsing is left
    to the caller so that an unparseable reply can still be logged in full."""
    payload = {
        "model": model or MODEL,
        "prompt": PROMPT_TEMPLATE.replace("{narrative}", narrative),
        "stream": False,
        "options": {"temperature": 0, "num_ctx": NUM_CTX},   # deterministic + explicit context window
    }
    t0 = time.perf_counter()
    resp = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=OLLAMA_TIMEOUT_S)
    model_ms = (time.perf_counter() - t0) * 1000
    resp.raise_for_status()
    body = resp.json()
    raw = body.get("response", "").strip()
    # Ollama reports its own timings in nanoseconds. We log them because they help us
    # find the bottleneck later (e.g. time waiting in Ollama vs time actually generating).
    ollama_stats = {
        "ollama_total_ms": body.get("total_duration", 0) / 1e6,
        "ollama_load_ms": body.get("load_duration", 0) / 1e6,
        "prompt_tokens": body.get("prompt_eval_count"),
        "prompt_eval_ms": body.get("prompt_eval_duration", 0) / 1e6,
        "output_tokens": body.get("eval_count"),
        "eval_ms": body.get("eval_duration", 0) / 1e6,
    }
    return raw, model_ms, ollama_stats


# ---------------------------------------------------------------------------
# Request logging: runs around EVERY request (including errors)
# ---------------------------------------------------------------------------
@app.before_request
def start_timer():
    g.t0 = time.perf_counter()
    g.start_epoch_ms = int(time.time() * 1000)   # request START in epoch ms (matches JMeter's timeStamp)
    g.received_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    # Reuse the caller's request id if it sent one (JMeter can), otherwise make one.
    g.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    g.extra = {}


@app.after_request
def log_request(response):
    entry = {
        "ts": g.received_at,                       # when the request arrived (UTC)
        "epoch_ms": g.start_epoch_ms,              # request START in epoch ms (matches JMeter's timeStamp)
        "run_id": RUN_ID,
        "request_id": g.request_id,
        "method": request.method,
        "path": request.path,
        "status": response.status_code,
        "latency_ms": round((time.perf_counter() - g.t0) * 1000, 2),  # total time inside our service
        "model": SERVICE_MODEL,                    # A2: MODEL in single mode; "cascade-settingN" in cascade mode
        "mode": CLASSIFICATION_MODE,               # A2: single or cascade (the answering model is in final_model)
    }
    entry.update(g.extra)                          # endpoint-specific fields (category, model timings, ...)
    req_logger.info(json.dumps(entry))
    response.headers["X-Request-ID"] = g.request_id
    return response


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.post("/tickets")
def create_ticket():
    # Accept either JSON {"narrative": "...", "ref": "..."} or the raw narrative as plain text.
    # Plain text is easier to send from JMeter because we don't have to JSON-escape quotes/newlines.
    if request.is_json:
        data = request.get_json(silent=True) or {}
        narrative = (data.get("narrative") or "").strip()
        ref = data.get("ref")
    else:
        narrative = request.get_data(as_text=True).strip()
        ref = None
    ref = ref or request.headers.get("X-Ticket-Ref")   # optional, e.g. "20517" or "G042"

    g.extra.update({"ref": ref, "narrative_chars": len(narrative), "narrative_words": len(narrative.split()),
                    "num_ctx": NUM_CTX, "prompt_sha256": PROMPT_SHA256})
    if not narrative:
        g.extra["error"] = "empty narrative"
        return jsonify(error="request body must contain a ticket narrative"), 400

    try:
        if not CASCADE:
            # ---- Single-model mode: unchanged from A1 ----
            raw, model_ms, ollama_stats = classify(narrative)
            category, final_model = parse_category(raw), MODEL
            g.extra.update({"escalated": False})
        else:
            # ---- A2 cascade (brief, Step 2; rule in a2/escalation_rule.md) ----
            # Step 1 of the rule: the small model classifies EVERY ticket with the unchanged A1 prompt.
            s_raw, s_ms, s_stats = classify(narrative, SMALL_MODEL)
            s_cat = parse_category(s_raw)
            if s_cat is None:
                reason = "invalid_small_model_output"
            elif s_cat not in ACCEPT_CATEGORIES:
                reason = "predicted_category_not_accepted"
            else:
                reason = None
            # Step 2 of the rule: accept only if the small model's PREDICTED category is in the accept
            # list. The true label is never available here, so it is never used.
            escalated = reason is not None
            # Logged for every ticket -> escalation fraction per run, and accuracy of escalated vs
            # accepted tickets (brief, Step 4; slides 4 and 5). small_load_ms ~ 0 shows the small
            # model was already resident (no reload), which supports the memory check (Step 2).
            g.extra.update({"cascade_setting": int(CASCADE_SETTING), "small_model": SMALL_MODEL,
                            "large_model": LARGE_MODEL, "small_prediction": s_cat,
                            "small_raw_output": s_raw[:200], "small_model_ms": round(s_ms, 2),
                            "small_load_ms": round(s_stats["ollama_load_ms"], 2),
                            "escalated": escalated, "escalation_reason": reason})
            if not escalated:
                raw, model_ms, ollama_stats, category, final_model = s_raw, s_ms, s_stats, s_cat, SMALL_MODEL
            else:
                # ---- Step 3 of the rule: escalate; the large model's answer is final ----
                # large_load_ms ~ 0 means the large model was still loaded (no swap between models).
                raw, l_ms, ollama_stats = classify(narrative, LARGE_MODEL)
                category, final_model, model_ms = parse_category(raw), LARGE_MODEL, s_ms + l_ms
                g.extra.update({"large_prediction": category, "large_model_ms": round(l_ms, 2),
                                "large_load_ms": round(ollama_stats["ollama_load_ms"], 2)})
    except requests.Timeout:
        g.extra["error"] = "ollama timeout"
        return jsonify(error="model backend timed out"), 504
    except requests.RequestException as e:
        g.extra["error"] = f"ollama error: {e}"
        return jsonify(error="model backend unavailable"), 502

    digest = get_model_digest(final_model)
    if category is None:
        # Invalid model output: do NOT store it. Log everything needed to analyse the failure.
        g.extra["error"] = "invalid model output"
        g.extra.update({"final_model": final_model, "raw_output": raw[:200], "model_digest": digest,
                        "model_ms": round(model_ms, 2), **ollama_stats})
        return jsonify(error="model returned an invalid category"), 502

    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO tickets (created_at, request_id, ref, narrative, category, raw_output, model, model_digest, model_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (g.received_at, g.request_id, ref, narrative, category, raw, final_model, digest, model_ms),
        )
        ticket_id = cur.lastrowid

    # final_model = which model produced the answer (the brief requires this in the log).
    # model_ms = total model time for this ticket (small + large when escalated).
    g.extra.update({"ticket_id": ticket_id, "category": category, "final_model": final_model, "raw_output": raw[:200],
                    "model_digest": digest, "model_ms": round(model_ms, 2), **ollama_stats})
    return jsonify(id=ticket_id, category=category, model=SERVICE_MODEL, request_id=g.request_id), 201


@app.get("/search")
def search():
    q = request.args.get("q", "").strip()
    limit = min(int(request.args.get("limit", 20)), 100)
    if not q:
        g.extra["error"] = "missing q"
        return jsonify(error="query parameter 'q' is required"), 400
    with get_db() as conn:
        # Baseline: full table scan with LIKE, newest first. No full-text index on purpose.
        rows = conn.execute(
            "SELECT id, created_at, category, substr(narrative, 1, 200) AS snippet "
            "FROM tickets WHERE narrative LIKE ? ORDER BY id DESC LIMIT ?",
            (f"%{q}%", limit),
        ).fetchall()
    g.extra.update({"query": q, "results": len(rows)})
    return jsonify(query=q, count=len(rows), results=[dict(r) for r in rows])


@app.get("/stats")
def stats():
    with get_db() as conn:
        rows = conn.execute("SELECT category, COUNT(*) AS n FROM tickets GROUP BY category").fetchall()
    counts = {c: 0 for c in CATEGORIES}
    for r in rows:
        if r["category"] in counts:   # only ever the 7 known categories; /stats returns exactly these keys
            counts[r["category"]] = r["n"]
    return jsonify(total=sum(counts.values()), by_category=counts)


@app.get("/health")
def health():
    return jsonify(status="ok", mode=CLASSIFICATION_MODE, model=SERVICE_MODEL, run_id=RUN_ID,
                   small_model=SMALL_MODEL if CASCADE else None, large_model=LARGE_MODEL if CASCADE else None,
                   cascade_setting=int(CASCADE_SETTING) if CASCADE else None, accept_categories=ACCEPT_CATEGORIES)


init_db()