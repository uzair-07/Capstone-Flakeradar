# Evaluation

How well does the flakiness score find flaky tests? The demo suite (`demo/`) has 60 tests
with known behaviour: 40 never fail and 20 fail at random with a fixed probability
(2%, 5%, 10%, 20% or 40%, four tests each, see `demo/ground_truth.json`).

| Script | What it does |
| --- | --- |
| `simulate.py` | Generates realistic CI history for the demo suite (commits, failed runs re-run on the same commit) and writes JUnit reports or uploads them to a FlakeRadar server |
| `evaluate.py` | Scores the simulated history with the server's own parser and scoring code and prints precision and recall of "suggested for quarantine" |

```bash
python evaluation/evaluate.py --commits 60 --seeds 1 2 3 4 5 6 7 8 9 10
python evaluation/simulate.py --commits 60 --server http://localhost:8080 --project demo --token fr_...
```

## First result (24 Nov 2026, score v1, default thresholds)

10 simulated histories of 60 commits (96–105 runs each):

| Metric | Result | Target (proposal) |
| --- | --- | --- |
| Precision | 1.00 (no stable test flagged) | ≥ 0.80 |
| Recall | 0.49 | ≥ 0.70 |

Recall by true failure rate: 40% → 100%, 20% → 92%, 10% → 45%, 5% → 10%, 2% → 0%.

The score is cautious: it never raises a false alarm, but rarely flaky tests fail too seldom
within the 30-run window to cross the 0.15 threshold. Tuning the window, the threshold and the
weights against this benchmark is planned for Sprint 4.
