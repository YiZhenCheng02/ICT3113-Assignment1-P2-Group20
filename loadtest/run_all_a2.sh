#!/usr/bin/env bash
# loadtest/run_all_a2.sh — A2 overnight speed-test runner (Assignment 2).
# Run from the repo root on Computer 1 (WSL). JMeter runs on Computer 2 (the load generator
# must be a separate machine, brief Step 4). Modeled on the A1 loadtest/run_all.sh.
#
# Usage:
#   bash loadtest/run_all_a2.sh trial          # ~4 min: validate SSH, JMeter, plan, fetch
#   bash loadtest/run_all_a2.sh full           # 12 single-model runs (+ cascade runs if CASCADE=1)
#   CASCADE=1 bash loadtest/run_all_a2.sh full # 18 runs: 12 singles + 6 cascade (S1 x3, S2 x3)
#   bash loadtest/run_all_a2.sh preflight      # checks only: SSH, JMeter path, files on C2
#
# Schedule is FIXED from the measured S (results/S_measurement_summary.txt): S = 9.25 s ->
# rate 3.24/min (1 ticket per 2S), run 555 s (S minutes), timeout 300000 ms, pause 6 min.
# The same schedule is used for every configuration so runs are comparable.
set -u
cd "$(dirname "$0")/.."

C2=loadtest@192.168.1.44
SSHPASS_VAL=$(grep -oP "SSHPASS='\K[^']+" loadtest/run_all.sh)
export SSHPASS="$SSHPASS_VAL"
JMETER='D:\jmeter\apache-jmeter-5.6.3\bin\jmeter.bat'
REMOTE_DIR='C:\Users\loadtest\loadtest'
HOST=192.168.1.42
PORT=8000
RATE_PER_MIN=3.24
RUN_S=555
PAUSE_MIN=6
TIMEOUT_MS=300000
MODELS="qwen2.5:3b qwen2.5:7b llama3.2:3b llama3.1:8b"
CASCADE=${CASCADE:-0}
MODE="${1:-trial}"

mkdir -p results/a2/jtl
PROG=results/a2/progress.log
log(){ echo "$(date '+%F %T') $*" | tee -a "$PROG"; }
rssh(){ sshpass -e ssh -o StrictHostKeyChecking=no "$C2" "$@"; }
rget(){ sshpass -e scp -q -o StrictHostKeyChecking=no "$C2:$REMOTE_DIR\\a2\\results\\$1" results/a2/jtl/ 2>/dev/null \
        || sshpass -e scp -q -o StrictHostKeyChecking=no "$C2:loadtest/a2/results/$1" results/a2/jtl/; }

# Copy the A2 plan and workload to Computer 2 (idempotent).
push_files(){
  rssh "if not exist $REMOTE_DIR\\a2\\results mkdir $REMOTE_DIR\\a2\\results" >/dev/null 2>&1
  sshpass -e scp -q -o StrictHostKeyChecking=no a2/plan_a2.jmx "a2/workload_rows.csv" "$C2:$REMOTE_DIR/a2/" || return 1
}

start_service(){ # $1 tag; remaining env for compose are set by the caller
  docker compose down >/dev/null 2>&1
  docker compose up -d >/dev/null 2>&1
  for i in $(seq 1 90); do curl -sf http://localhost:8000/health >/dev/null 2>&1 && return 0; sleep 2; done
  log "ERROR service did not start for $1"; return 1
}

warmup(){ # $1 tag; echoes how many warmups were sent; verifies models resident via ollama ps
  python3 a2/send_tickets.py a2/warmup_rows.csv --out "results/a2/warmup_$1.csv" >/dev/null 2>&1
  docker compose exec -T ollama ollama ps
}

run_jmeter(){ # $1 tag
  rssh "if exist $REMOTE_DIR\\a2\\results\\$1.jtl del $REMOTE_DIR\\a2\\results\\$1.jtl" >/dev/null 2>&1
  rssh "$JMETER -n -t $REMOTE_DIR\\a2\\plan_a2.jmx -l $REMOTE_DIR\\a2\\results\\$1.jtl -Jhost=$HOST -Jport=$PORT -Jrate_per_min=$RATE_PER_MIN -Jrun_s=$RUN_S -Jpause_min=$PAUSE_MIN -Jtimeout_ms=$TIMEOUT_MS -Jworkload_file=$REMOTE_DIR\\a2\\workload_rows.csv -Jrun_tag=$1" \
    > "results/a2/jtl/$1.console.txt" 2>&1
  rget "$1.jtl"
}

run_single(){ # $1 model, $2 run number
  local m="$1" k="$2" safe=${1//[:.]/_} n_esc
  local tag="single_${safe}_run${k}"
  if ! CLASSIFICATION_MODE=single MODEL="$m" RUN_ID="$tag" start_service "$tag"; then return 1; fi
  warmup "$tag" | tee -a "$PROG"
  log "START $tag  ($m, single)"
  curl -s "http://localhost:$PORT/stats" >> "$PROG" 2>/dev/null; echo >> "$PROG"
  run_jmeter "$tag"
  log "DONE $tag"
}

run_cascade(){ # $1 setting (1|2), $2 run number
  local s="$1" k="$2"
  local tag="cascade_s${s}_run${k}"
  if ! CLASSIFICATION_MODE=cascade CASCADE_SETTING="$s" RUN_ID="$tag" start_service "$tag"; then return 1; fi
  warmup "$tag" | tee -a "$PROG"
  n_esc=$(python3 -c "
import json
lines=[json.loads(l) for l in open('logs/requests.jsonl')]
last=[e for e in lines if e.get('run_id')=='$tag' and e.get('path')=='/tickets']
print(sum(1 for e in last if e.get('escalated')))")
  if [ "${n_esc:-0}" -lt 1 ]; then log "WARN no escalation in warm-up for $tag (large model may be cold)"; fi
  log "START $tag  (cascade setting $s, warmup escalations=$n_esc)"
  curl -s "http://localhost:$PORT/stats" >> "$PROG" 2>/dev/null; echo >> "$PROG"
  run_jmeter "$tag"
  log "DONE $tag"
}

case "$MODE" in
  preflight)
    log "== preflight =="
    rssh "echo C2 reachable && if exist \"$JMETER\" (echo jmeter.bat FOUND) else (echo JMETER MISSING)" \
      || { log "FAIL: cannot reach $C2"; exit 1; }
    push_files && log "plan + workload copied to C2" || { log "FAIL: copy to C2"; exit 1; }
    start_service preflight && log "service starts OK" || exit 1
    log "PREFLIGHT OK"
    ;;
  trial)
    log "== trial =="
    push_files || { log "FAIL: copy to C2"; exit 1; }
    CLASSIFICATION_MODE=single MODEL=qwen2.5:3b RUN_ID=trial start_service trial || exit 1
    warmup trial >/dev/null
    log "START trial (single qwen2.5:3b, 1/min x 60 s)"
    rssh "if exist $REMOTE_DIR\\a2\\results\\trial.jtl del $REMOTE_DIR\\a2\\results\\trial.jtl" >/dev/null 2>&1
    rssh "$JMETER -n -t $REMOTE_DIR\\a2\\plan_a2.jmx -l $REMOTE_DIR\\a2\\results\\trial.jtl -Jhost=$HOST -Jport=$PORT -Jrate_per_min=1 -Jrun_s=60 -Jpause_min=1 -Jtimeout_ms=300000 -Jworkload_file=$REMOTE_DIR\\a2\\workload_rows.csv -Jrun_tag=trial" \
      > results/a2/jtl/trial.console.txt 2>&1
    rget trial.jtl
    if [ -f results/a2/jtl/trial.jtl ]; then
      log "TRIAL OK: $(( $(wc -l < results/a2/jtl/trial.jtl) - 1 )) samples in results/a2/jtl/trial.jtl"
    else
      log "TRIAL FAILED: no .jtl fetched; check results/a2/jtl/trial.console.txt"
    fi
    ;;
  full)
    log "===== A2 FULL RUN START (CASCADE=$CASCADE) ====="
    for m in $MODELS; do for k in 1 2 3; do run_single "$m" "$k"; done; done
    if [ "$CASCADE" = "1" ]; then
      for s in 1 2; do for k in 1 2 3; do run_cascade "$s" "$k"; done; done
    fi
    docker compose down >/dev/null 2>&1
    log "===== A2 FULL RUN DONE — summarize with: python3 a2/summarize_jtl.py ====="
    ;;
  *) echo "usage: bash loadtest/run_all_a2.sh {trial|full|preflight}  (CASCADE=1 adds cascade runs)"; exit 2;;
esac
