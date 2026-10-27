# External evaluation: data/benign_unique_081_ml

* Sessions: 200 (200 benign, 0 attack); distinct feature vectors: 197
* Source dataset SHA-256: `b0118a9fe336525705ca7178616443e11f77611d9f078f29911d54104e0df8ba`

| Model | Sessions | FP | FPR | FPR 95% CI | Max benign score | Recall | Rows identical to training |
|---|---|---|---|---|---|---|---|
| expanded_20261008/random_forest (all) | 200 | 0 | 0.000 | 0.000–0.019 | 0.19 | – | 25 |
| expanded_20261008/random_forest (task seen in training) | 200 | 0 | 0.000 | 0.000–0.019 | 0.19 | – |  |
| expanded_20261008/svm (all) | 200 | 0 | 0.000 | 0.000–0.019 | -0.6994 | – | 25 |
| expanded_20261008/svm (task seen in training) | 200 | 0 | 0.000 | 0.000–0.019 | -0.6994 | – |  |
| expanded_20261008/xgboost (all) | 200 | 0 | 0.000 | 0.000–0.019 | 0.2505 | – | 25 |
| expanded_20261008/xgboost (task seen in training) | 200 | 0 | 0.000 | 0.000–0.019 | 0.2505 | – |  |
| expanded_20261008/rf_xgb (all) | 200 | 0 | 0.000 | 0.000–0.019 | 0.2202 | – | 25 |
| expanded_20261008/rf_xgb (task seen in training) | 200 | 0 | 0.000 | 0.000–0.019 | 0.2202 | – |  |

False positives by number of mounted servers:

| Model | 1 servers | 2 servers | 3 servers | 6 servers |
|---|---|---|---|---|
| expanded_20261008/random_forest | 0/89 (max 0.0067) | 0/10 (max 0.19) | 0/1 (max 0.19) | 0/100 (max 0.04) |
| expanded_20261008/svm | 0/89 (max -0.6994) | 0/10 (max -0.9828) | 0/1 (max -0.7888) | 0/100 (max -0.7376) |
| expanded_20261008/xgboost | 0/89 (max 0.0018) | 0/10 (max 0.1327) | 0/1 (max 0.2505) | 0/100 (max 0.0033) |
| expanded_20261008/rf_xgb | 0/89 (max 0.0042) | 0/10 (max 0.1613) | 0/1 (max 0.2202) | 0/100 (max 0.0204) |

Flagged benign scenarios (false positives):

* expanded_20261008/random_forest: none
* expanded_20261008/svm: none
* expanded_20261008/xgboost: none
* expanded_20261008/rf_xgb: none
