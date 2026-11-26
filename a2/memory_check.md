# Assignment 2 memory check (brief Step 2)

Fixed limit: the WSL2 VM the Docker/Ollama stack runs in is capped at **7.4 GB** (as documented
in Assignment 1). `OLLAMA_MAX_LOADED_MODELS=2`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_KEEP_ALIVE=-1`,
`num_ctx=4096`. RAM was **not** raised and `.wslconfig` was **not** changed.

Test method: send one `POST /api/generate` to the small model, then one to the large model
(`num_ctx=4096`), and run `docker compose exec ollama ollama ps` to confirm both are resident.
`free -m` shows the WSL2 total (~7.59 GB visible to the container).

## Results

| Pair (small + large) | Weights | Both in `ollama ps`? | Outcome |
|---|---|---|---|
| `llama3.2:3b` + `llama3.1:8b` | 2.6 + ~4.9 GB | **No** | 8B load `HTTP 500`, `llama-server process has terminated: signal: killed` |
| `qwen2.5:3b` + `llama3.1:8b` | 2.2 + ~4.9 GB | **No** | 8B load `HTTP 500`, `signal: killed`; swap 2041/2048 MB full |
| `qwen2.5:3b` + `qwen2.5:7b` | 2.2 + 5.1 GB | **Yes** | both resident, ~106 MB free, swap full (very tight) |

## Conclusion

Every pair containing an 8B model is OOM-killed, including the originally-planned
`llama3.2:3b → llama3.1:8b`. The only pair that keeps both models loaded simultaneously is
`qwen2.5:3b → qwen2.5:7b` (7.3 GB), so that is the measured cascade pair. Because a pair does
fit, a cascade is reported as feasible (not infeasible); the accuracy result is reported
separately.

## Raw evidence

```
# qwen2.5:3b loaded, then llama3.1:8b attempted:
$ curl -s localhost:11434/api/generate -d '{"model":"llama3.1:8b","prompt":"hi","stream":false,"options":{"num_ctx":4096}}'
{"error":"llama-server process has terminated: signal: killed"}
$ docker compose exec -T ollama ollama ps
NAME          ID              SIZE      PROCESSOR    CONTEXT    RUNNER      UNTIL
qwen2.5:3b    357c53fb659c    2.2 GB    100% CPU     4096       llamacpp    Forever
$ free -m
               total        used        free      shared  buff/cache   available
Mem:            7590        2446        4849          48         505        5143
Swap:           2048        2041           6

# qwen2.5:7b loaded while qwen2.5:3b resident:
$ docker compose exec -T ollama ollama ps
NAME          ID              SIZE      PROCESSOR    CONTEXT    RUNNER      UNTIL
qwen2.5:7b    845dbda0ea48    5.1 GB    100% CPU     4096       llamacpp    Forever
qwen2.5:3b    357c53fb659c    2.2 GB    100% CPU     4096       llamacpp    Forever
$ free -m
               total        used        free      shared  buff/cache   available
Mem:            7590        7215         106          45         480         374
Swap:           2048        2047           0
```
