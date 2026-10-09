# ICT3113-Assignment1-P2-Group20
ICT3113 Assignment 1 - Performance Requirements and Testing 

### Group
Lab P2 Group 20

### Team Members
- Chan Jean Wen Belle - 2402872
- Cheng Yi Zhen - 2402634
- Derick Lee Cheng Zhang - 2401154
- Tan Yu Xuan - 2402480


## Documentation

| Doc | What it covers |
|---|---|
| [`SERVICE_README.md`](SERVICE_README.md) | Baseline ticket-triage service (Flask + Ollama): endpoints, classification flow, prompt handling and strict parsing, how to run it |
| [`workload/workload_model.md`](workload/workload_model.md) | Step 3 workload model: ticket volume, peak/non-peak periods, agent search rate, ticket-length distribution |
| [`golden_set/labelling_protocol_v2.md`](golden_set/labelling_protocol_v2.md) | Final (frozen) labelling protocol used to build the 185-ticket golden set |
| [`golden_set/labelling_protocol_v1.md`](golden_set/labelling_protocol_v1.md) | Earlier labelling protocol, kept for history; superseded by v2 |
| [`model_selection_and_requirements.md`](model_selection_and_requirements.md) | Step 4 candidate models (2×2 size × family) and the R1–R5 performance requirements |
| [`predictions.md`](predictions.md) | Step 4 predictions recorded before any benchmark run (bottleneck, P1–P8, expected accuracy/latency) |
| [`results/summary/report.md`](results/summary/report.md) | Full analysis: R1–R5 results, prediction checks, clock skew and reconciliation |


## Results

| What | Where |
|---|---|
| Raw JMeter results (36 runs) | `results/jtl/<test>_<model>_run<k>.jtl` |
| Service request log | `logs/requests.jsonl` |
| Accuracy: raw predictions & summaries | `results/accuracy/<model>_raw.csv`, `<model>_summary.txt` |
| Full analysis report (all requirements, predictions, reconciliation) | `results/summary/report.md` |
| Per-run numbers | `results/summary/r1r2_perrun.csv`, `r3_perrun.csv`, `r4_perrun.csv` |
| JMeter ↔ service-log reconciliation | `results/summary/reconciliation.csv` |
| Slide figures | `results/figures/*.png` |

**Reproduce:** `bash loadtest/run_all.sh all` (tests), then
`python3 loadtest/analyse.py` and `python3 loadtest/make_figures.py` (analysis and figures).
