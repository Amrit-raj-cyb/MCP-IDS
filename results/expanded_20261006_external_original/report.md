# External evaluation: /lab/data/expanded_20261006_holdout_original_ml

* Sessions: 634 (634 benign, 0 attack); distinct feature vectors: 601
* Source dataset SHA-256: `12a010f1cdfbe55bae4ebd94dc425ad0f9543759ed7cd59ab432950d0d4dcf6a`

| Model | Sessions | FP | FPR | FPR 95% CI | Max benign score | Recall | Rows identical to training |
|---|---|---|---|---|---|---|---|
| expanded_20261006/random_forest (all) | 634 | 0 | 0.000 | 0.000–0.006 | 0.19 | – | 43 |
| expanded_20261006/random_forest (task seen in training) | 634 | 0 | 0.000 | 0.000–0.006 | 0.19 | – |  |
| expanded_20261006/svm (all) | 634 | 0 | 0.000 | 0.000–0.006 | -0.6795 | – | 43 |
| expanded_20261006/svm (task seen in training) | 634 | 0 | 0.000 | 0.000–0.006 | -0.6795 | – |  |
| expanded_20261006/xgboost (all) | 634 | 0 | 0.000 | 0.000–0.006 | 0.2505 | – | 43 |
| expanded_20261006/xgboost (task seen in training) | 634 | 0 | 0.000 | 0.000–0.006 | 0.2505 | – |  |
| expanded_20261006/rf_xgb (all) | 634 | 0 | 0.000 | 0.000–0.006 | 0.2202 | – | 43 |
| expanded_20261006/rf_xgb (task seen in training) | 634 | 0 | 0.000 | 0.000–0.006 | 0.2202 | – |  |

False positives by number of mounted servers:

| Model | 1 servers | 2 servers | 3 servers | 6 servers |
|---|---|---|---|---|
| expanded_20261006/random_forest | 0/287 (max 0.01) | 0/29 (max 0.19) | 0/1 (max 0.19) | 0/317 (max 0.04) |
| expanded_20261006/svm | 0/287 (max -0.6994) | 0/29 (max -0.6795) | 0/1 (max -0.7888) | 0/317 (max -0.7376) |
| expanded_20261006/xgboost | 0/287 (max 0.0018) | 0/29 (max 0.1369) | 0/1 (max 0.2505) | 0/317 (max 0.0033) |
| expanded_20261006/rf_xgb | 0/287 (max 0.0056) | 0/29 (max 0.1613) | 0/1 (max 0.2202) | 0/317 (max 0.0204) |

Flagged benign scenarios (false positives):

* expanded_20261006/random_forest: none
* expanded_20261006/svm: none
* expanded_20261006/xgboost: none
* expanded_20261006/rf_xgb: none
