# External evaluation: data/phase9_081_ml

* Sessions: 180 (90 benign, 90 attack); distinct feature vectors: 53
* Source dataset SHA-256: `f0fd05d28c873b61e59507dbb94cde3309bdd49007806c7cdfe46bfb4415728e`

| Model | Sessions | FP | FPR | FPR 95% CI | Max benign score | Recall | Rows identical to training |
|---|---|---|---|---|---|---|---|
| try6/random_forest (all) | 180 | 0 | 0.000 | 0.000–0.041 | 0.1233 | 0.500 | 0 |
| try6/random_forest (task seen in training) | 60 | 0 | 0.000 | 0.000–0.114 | 0.1233 | 1.000 |  |
| try6/random_forest (task not seen in training) | 120 | 0 | 0.000 | 0.000–0.060 | 0.12 | 0.250 |  |
| phase9_081/random_forest (all) | 180 | 0 | 0.000 | 0.000–0.041 | 0.0433 | 1.000 | 170 |
| phase9_081/random_forest (task seen in training) | 180 | 0 | 0.000 | 0.000–0.041 | 0.0433 | 1.000 |  |
| phase9_081/svm (all) | 180 | 0 | 0.000 | 0.000–0.041 | -0.5232 | 1.000 | 170 |
| phase9_081/svm (task seen in training) | 180 | 0 | 0.000 | 0.000–0.041 | -0.5232 | 1.000 |  |

False positives by number of mounted servers:

| Model | 1 servers | 2 servers | 6 servers |
|---|---|---|---|
| try6/random_forest | 0/16 (max 0.03) | 0/74 (max 0.08) | 0/90 (max 0.1233) |
| phase9_081/random_forest | 0/16 (max 0.0) | 0/74 (max 0.02) | 0/90 (max 0.0433) |
| phase9_081/svm | 0/16 (max -0.9998) | 0/74 (max -0.9997) | 0/90 (max -0.5232) |

Recall by attack family:

| Model | poisoned_tool | sampling_injection | shadowing |
|---|---|---|---|
| try6/random_forest | 30/30 (1.00) | 0/30 (0.00) | 15/30 (0.50) |
| phase9_081/random_forest | 30/30 (1.00) | 30/30 (1.00) | 30/30 (1.00) |
| phase9_081/svm | 30/30 (1.00) | 30/30 (1.00) | 30/30 (1.00) |

Flagged benign scenarios (false positives):

* try6/random_forest: none
* phase9_081/random_forest: none
* phase9_081/svm: none
