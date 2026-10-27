# External evaluation: data/benign_unique_081_ml

* Sessions: 200 (200 benign, 0 attack); distinct feature vectors: 197
* Source dataset SHA-256: `b0118a9fe336525705ca7178616443e11f77611d9f078f29911d54104e0df8ba`

| Model | Sessions | FP | FPR | FPR 95% CI | Max benign score | Recall | Rows identical to training |
|---|---|---|---|---|---|---|---|
| combined_canonical_20261010/random_forest (all) | 200 | 0 | 0.000 | 0.000–0.019 | 0.08 | – | 102 |
| combined_canonical_20261010/random_forest (task seen in training) | 96 | 0 | 0.000 | 0.000–0.038 | 0.08 | – |  |
| combined_canonical_20261010/random_forest (task not seen in training) | 104 | 0 | 0.000 | 0.000–0.036 | 0.0633 | – |  |
| combined_canonical_20261010/svm (all) | 200 | 0 | 0.000 | 0.000–0.019 | -0.0133 | – | 102 |
| combined_canonical_20261010/svm (task seen in training) | 96 | 0 | 0.000 | 0.000–0.038 | -0.0133 | – |  |
| combined_canonical_20261010/svm (task not seen in training) | 104 | 0 | 0.000 | 0.000–0.036 | -0.1401 | – |  |
| combined_canonical_20261010/xgboost (all) | 200 | 0 | 0.000 | 0.000–0.019 | 0.0072 | – | 102 |
| combined_canonical_20261010/xgboost (task seen in training) | 96 | 0 | 0.000 | 0.000–0.038 | 0.0072 | – |  |
| combined_canonical_20261010/xgboost (task not seen in training) | 104 | 0 | 0.000 | 0.000–0.036 | 0.0067 | – |  |
| combined_canonical_20261010/rf_xgb (all) | 200 | 0 | 0.000 | 0.000–0.019 | 0.0427 | – | 102 |
| combined_canonical_20261010/rf_xgb (task seen in training) | 96 | 0 | 0.000 | 0.000–0.038 | 0.0427 | – |  |
| combined_canonical_20261010/rf_xgb (task not seen in training) | 104 | 0 | 0.000 | 0.000–0.036 | 0.035 | – |  |
| combined_canonical_20261010/decision_tree (all) | 200 | 0 | 0.000 | 0.000–0.019 | 0.0 | – | 102 |
| combined_canonical_20261010/decision_tree (task seen in training) | 96 | 0 | 0.000 | 0.000–0.038 | 0.0 | – |  |
| combined_canonical_20261010/decision_tree (task not seen in training) | 104 | 0 | 0.000 | 0.000–0.036 | 0.0 | – |  |
| combined_canonical_20261010/cnn (all) | 200 | 0 | 0.000 | 0.000–0.019 | 0.0006 | – | 102 |
| combined_canonical_20261010/cnn (task seen in training) | 96 | 0 | 0.000 | 0.000–0.038 | 0.0 | – |  |
| combined_canonical_20261010/cnn (task not seen in training) | 104 | 0 | 0.000 | 0.000–0.036 | 0.0006 | – |  |
| combined_canonical_20261010/cnn_raw (all) | 200 | 0 | 0.000 | 0.000–0.019 | 0.3819 | – | 100 |
| combined_canonical_20261010/cnn_raw (task seen in training) | 96 | 0 | 0.000 | 0.000–0.038 | 0.3819 | – |  |
| combined_canonical_20261010/cnn_raw (task not seen in training) | 104 | 0 | 0.000 | 0.000–0.036 | 0.3819 | – |  |

False positives by number of mounted servers:

| Model | 1 servers | 2 servers | 3 servers | 6 servers |
|---|---|---|---|---|
| combined_canonical_20261010/random_forest | 0/89 (max 0.0) | 0/10 (max 0.08) | 0/1 (max 0.0633) | 0/100 (max 0.0067) |
| combined_canonical_20261010/svm | 0/89 (max -0.8394) | 0/10 (max -0.611) | 0/1 (max -0.2368) | 0/100 (max -0.0133) |
| combined_canonical_20261010/xgboost | 0/89 (max 0.0005) | 0/10 (max 0.0072) | 0/1 (max 0.0067) | 0/100 (max 0.0034) |
| combined_canonical_20261010/rf_xgb | 0/89 (max 0.0003) | 0/10 (max 0.0427) | 0/1 (max 0.035) | 0/100 (max 0.0037) |
| combined_canonical_20261010/decision_tree | 0/89 (max 0.0) | 0/10 (max 0.0) | 0/1 (max 0.0) | 0/100 (max 0.0) |
| combined_canonical_20261010/cnn | 0/89 (max 0.0) | 0/10 (max 0.0) | 0/1 (max 0.0006) | 0/100 (max 0.0) |
| combined_canonical_20261010/cnn_raw | 0/89 (max 0.3819) | 0/10 (max 0.3819) | 0/1 (max 0.0) | 0/100 (max 0.3186) |

Flagged benign scenarios (false positives):

* combined_canonical_20261010/random_forest: none
* combined_canonical_20261010/svm: none
* combined_canonical_20261010/xgboost: none
* combined_canonical_20261010/rf_xgb: none
* combined_canonical_20261010/decision_tree: none
* combined_canonical_20261010/cnn: none
* combined_canonical_20261010/cnn_raw: none
