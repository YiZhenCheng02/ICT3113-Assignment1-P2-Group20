#!/usr/bin/env bash
# loadtest/run_all.sh: overnight test runner. Run from the repo root on Computer 1 (WSL).
# Usage: bash loadtest/run_all.sh trial   (2-minute check)
#        bash loadtest/run_all.sh all     (full overnight run)
set -u
cd "$(dirname "$0")/.."

C2=loadtest@192.168.1.11
export SSHPASS='Triage2026!'
JMETER='D:\jmeter\apache-jmeter-5.6.3\bin\jmeter.bat'   # <-- EDIT to match your folder
REMOTE_DIR='C:\Users\loadtest\loadtest'
HOST=192.168.1.14
MODELS="qwen2.5:3b llama3.2:3b qwen2.5:7b llama3.1:8b"
MODE="${1:-trial}"

mkdir -p results/jtl results/accuracy
PROG=results/progress.log
log(){ echo "$(date '+%F %T') $*" | tee -a "$PROG"; }
rssh(){ sshpass -e ssh -o StrictHostKeyChecking=no "$C2" "$@"; }
rget(){ sshpass -e scp -o StrictHostKeyChecking=no "$C2:loadtest/results/$1" results/jtl/; }

start_service(){ # $1 model, $2 run_id. Restart wipes the ticket DB (Dockerfile:13).
  docker compose down >/dev/null 2>&1
  MODEL="$1" RUN_ID="$2" docker compose up -d >/dev/null 2>&1
  for i in $(seq 1 90); do curl -sf http://localhost:8000/stats >/dev/null && return 0; sleep 2; done
  log "ERROR service did not start: $1 $2"; return 1
}

seed(){ # $1 count, $2 ref prefix. Sends the LAST N pool rows one at a time from Computer 1.
  python3 - "$1" "$2" <<'EOF'
import sys, json, urllib.request
n, prefix = int(sys.argv[1]), sys.argv[2]
lines = open("loadtest/data/pool.tsv", encoding="utf-8").read().splitlines()
ok = 0
for line in lines[-n:]:
    row, nj = line.split("\t", 1)
    body = json.dumps({"narrative": json.loads('"' + nj + '"'), "ref": f"{prefix}-{row}"}).encode()
    req = urllib.request.Request("http://localhost:8000/tickets", data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=900) as r: ok += (r.status == 201)
    except Exception: pass
print(f"{prefix}: {ok}/{n} stored")
EOF
}

run_jmeter(){ # $1 tag, $2 post/hour, $3 get/hour, $4 minutes, $5 pool file
  rssh "if not exist loadtest\\results mkdir loadtest\\results" >/dev/null 2>&1
  rssh "$JMETER -n -t $REMOTE_DIR\\plan.jmx -l $REMOTE_DIR\\results\\$1.jtl -Jhost=$HOST -Jport=8000 -Jpost_rate=$2 -Jget_rate=$3 -Jduration_min=$4 -Jpool_file=$REMOTE_DIR\\data\\$5 -Jterms_file=$REMOTE_DIR\\data\\search_terms.txt -Jrun_tag=$1" \
    > "results/jtl/$1.console.txt" 2>&1
}

run_acc(){ # accuracy test for one model
  local m="$1" safe=${1//[:.]/-}
  start_service "$m" "acc_$safe" || return
  seed 1 "warmup-acc_$safe" >/dev/null
  log "START acc $m"; python3 loadtest/run_accuracy.py "$m" >> "$PROG" 2>&1; log "DONE acc $m"
}

run_sat(){ # R3 or R4: $1 model, $2 r3|r4, $3 run number
  local m="$1" t="$2" k="$3" safe=${1//[:.]/-}
  local tag="${t}_${safe}_run${k}" pool=pool.tsv; [ "$t" = r4 ] && pool=long.tsv
  start_service "$m" "$tag" || return
  seed 1 "warmup-$tag" >/dev/null
  log "START $tag"
  run_jmeter "$tag" 2300 29 6 "$pool" &
  local jp=$!
  sleep 390                              # 6-min schedule + 30 s JMeter start-up slack
  docker compose down >/dev/null 2>&1    # hard stop: clears queue; in-flight = unfinished
  wait $jp; rget "$tag.jtl"; log "DONE $tag"
}

run_r1r2(){ # R1/R2: seed once, then three 15-min runs back-to-back
  local m="$1" safe=${1//[:.]/-}
  start_service "$m" "r1r2_$safe" || return
  log "SEED r1r2_$safe"; seed 100 "seed-r1r2_$safe" | tee -a "$PROG"
  for k in 1 2 3; do
    local tag="r1r2_${safe}_run$k"; log "START $tag"
    run_jmeter "$tag" 19 29 15 pool.tsv; rget "$tag.jtl"; log "DONE $tag"
  done
}

# Copy plan and data to Computer 2
rssh "if not exist loadtest mkdir loadtest" >/dev/null 2>&1
sshpass -e scp -o StrictHostKeyChecking=no -r loadtest/plan.jmx loadtest/data "$C2:loadtest/"

if [ "$MODE" = trial ]; then
  start_service qwen2.5:3b trial && seed 1 warmup-trial
  log "START trial"; run_jmeter trial 120 120 2 pool.tsv; rget trial.jtl
  log "TRIAL done: $(( $(wc -l < results/jtl/trial.jtl) - 1 )) samples"
  exit
fi

log "===== FULL RUN START ====="
for m in $MODELS; do run_acc "$m"; done
for m in $MODELS; do for k in 1 2 3; do run_sat "$m" r3 "$k"; done; done
for m in $MODELS; do run_r1r2 "$m"; done
for m in $MODELS; do for k in 1 2 3; do run_sat "$m" r4 "$k"; done; done
docker compose down >/dev/null 2>&1
log "===== ALL DONE ====="