# ICT3113-Assignment1-P2-Group20
ICT3113 Assignment 1 - Performance Requirements and Testing 

### Group
Lab P2 Group 20

### Team Members
- Chan Jean Wen Belle - 2402872
- Cheng Yi Zhen - 2402634
- Derick Lee Cheng Zhang - 2401154
- Tan Yu Xuan - 2402480


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
