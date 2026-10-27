# External evaluation: /lab/data/benign_varied_090_ml

* Sessions: 317 (317 benign, 0 attack); distinct feature vectors: 309
* Source dataset SHA-256: `7d7169a8e9a3dfb12cc925610d642a458d7f91192876e86e46d83ba2a5377783`

| Model | Sessions | FP | FPR | FPR 95% CI | Max benign score | Recall | Rows identical to training |
|---|---|---|---|---|---|---|---|
| expanded_20261006/random_forest (all) | 317 | 0 | 0.000 | 0.000–0.012 | 0.0533 | – | 70 |
| expanded_20261006/random_forest (task seen in training) | 317 | 0 | 0.000 | 0.000–0.012 | 0.0533 | – |  |
| expanded_20261006/svm (all) | 317 | 0 | 0.000 | 0.000–0.012 | -0.8344 | – | 70 |
| expanded_20261006/svm (task seen in training) | 317 | 0 | 0.000 | 0.000–0.012 | -0.8344 | – |  |
| expanded_20261006/xgboost (all) | 317 | 0 | 0.000 | 0.000–0.012 | 0.0046 | – | 70 |
| expanded_20261006/xgboost (task seen in training) | 317 | 0 | 0.000 | 0.000–0.012 | 0.0046 | – |  |
| expanded_20261006/rf_xgb (all) | 317 | 0 | 0.000 | 0.000–0.012 | 0.0274 | – | 70 |
| expanded_20261006/rf_xgb (task seen in training) | 317 | 0 | 0.000 | 0.000–0.012 | 0.0274 | – |  |

False positives by number of mounted servers:

| Model | 6 servers |
|---|---|
| expanded_20261006/random_forest | 0/317 (max 0.0533) |
| expanded_20261006/svm | 0/317 (max -0.8344) |
| expanded_20261006/xgboost | 0/317 (max 0.0046) |
| expanded_20261006/rf_xgb | 0/317 (max 0.0274) |

Flagged benign scenarios (false positives):

* expanded_20261006/random_forest: none
* expanded_20261006/svm: none
* expanded_20261006/xgboost: none
* expanded_20261006/rf_xgb: none
