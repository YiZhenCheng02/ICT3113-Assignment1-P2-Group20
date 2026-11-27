# Assignment 2 memory check (brief Step 2)

Fixed limit: the WSL2 VM the Docker/Ollama stack runs in is capped at **7.4 GB** (as documented
in Assignment 1). `OLLAMA_MAX_LOADED_MODELS=2`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_KEEP_ALIVE=-1`,
`num_ctx=4096`. RAM was **not** raised and `.wslconfig` was **not** changed.

Test method (two levels, per the brief):

1. **Residency check**: load the small model, then the large model (`num_ctx=4096`), and run
   `docker compose exec ollama ollama ps` to see whether both stay loaded.
2. **Real-workload check**: with both models resident, send real tickets (the full Assignment 1
   prompt, ~2,269 tokens) through `POST /tickets` — the brief requires that a few tickets run
   through **each** model successfully, not just that both models are listed.

## Results — all four possible pairs

| Pair (small → large) | Weights | Residency check | Real-workload check | Verdict |
|---|---|---|---|---|
| `llama3.2:3b` → `llama3.1:8b` | 2.6 + ~4.9 GB | **FAIL** — 8B OOM-killed at load | not reachable | infeasible |
| `qwen2.5:3b` → `llama3.1:8b` | 2.2 + ~4.9 GB | **FAIL** — 8B OOM-killed at load | not reachable | infeasible |
| `llama3.2:3b` → `qwen2.5:7b` | 2.6 + 5.1 GB | **FAIL** — 7B OOM-killed at load (7.7 GB) | not reachable | infeasible |
| `qwen2.5:3b` → `qwen2.5:7b` | 2.2 + 5.1 GB | **PASS** — both listed, ~106 MB free | **FAIL** — every full-prompt escalation to the 7B is OOM-killed | **infeasible** |

## Conclusion: cascade feasible ONLY on a fresh-boot stack — marginal, benchmark with care

All three other pairs are hard-infeasible (OOM at load). The `qwen2.5:3b + qwen2.5:7b` pair is
**marginal**: earlier in the session (WSL up all day, page cache + fragmentation accumulated),
every real-prompt escalation was OOM-killed (0/5). After a **full laptop reboot**, a 10-probe
stability gate (`a2/probe_cascade.py`) passed with **0 kernel OOM kills** and 8/8 genuine
escalations served 201 (2/10 tickets were answered by the small model due to sampling variance in
its live predictions — benign). The memory check therefore passes on a fresh-boot stack, and every
measured run below uses a fresh stack (`docker compose down && up`) before warm-up, matching the
validated state. Runbook rule: **reboot Computer 1 (or at minimum restart the WSL/docker stack)
before benchmark sessions; never benchmark the cascade on a long-lived session.**

The recommended production configuration remains the single top model `llama3.1:8b` (92.4% test
accuracy, passes the overall and all per-category limits) unless the cascade measurements show a
speed win inside the accuracy limits. The cascade design and the tuning-set-only selection of two
settings are preserved in `a2/escalation_rule.md` and `results/tuning_*.csv`.

## Raw evidence

All OOM kills are kernel-confirmed (`dmesg`), e.g.:

```
[ 8546.694485] Out of memory: Killed process 62617 (llama-server) total-vm:6076244kB,
    anon-rss:4818492kB, ... oom_score_adj:0
[ 8726.609740] Out of memory: Killed process 64285 (llama-server) total-vm:6422236kB,
    anon-rss:4875952kB, ...
[ 8746.364997] Out of memory: Killed process 64646 (llama-server) total-vm:6076244kB,
    anon-rss:4765380kB, ...
```

Saved in `results/oom_dmesg_evidence.txt`; service-side 502 responses in `logs/requests.jsonl`
(`run_id=acc-cascade-s1`).

8B pairs (OOM at load):

```
$ curl -s localhost:11434/api/generate -d '{"model":"llama3.1:8b",...,"options":{"num_ctx":4096}}'
{"error":"llama-server process has terminated: signal: killed"}
$ docker compose exec -T ollama ollama ps
NAME          ID              SIZE      PROCESSOR    CONTEXT    RUNNER      UNTIL
qwen2.5:3b    357c53fb659c    2.2 GB    100% CPU     4096       llamacpp    Forever
```

`qwen2.5:3b + qwen2.5:7b` residency (passes) and the WSL2 total visible to the container:

```
$ docker compose exec -T ollama ollama ps
NAME          ID              SIZE      PROCESSOR    CONTEXT    RUNNER      UNTIL
qwen2.5:7b    845dbda0ea48    5.1 GB    100% CPU     4096       llamacpp    Forever
qwen2.5:3b    357c53fb659c    2.2 GB    100% CPU     4096       llamacpp    Forever
$ free -m
               total        used        free      shared  buff/cache   available
Mem:            7590        7515          76          5         163          74
Swap:           2048        2048           0
```

Real-workload failure (`qwen2.5:3b` + `qwen2.5:7b`, fresh stack): the small-model ticket returns
201, every escalated ticket returns HTTP 502 while `ollama ps` continues to list both models —
the large model's runner is killed and re-registered on each attempt.
