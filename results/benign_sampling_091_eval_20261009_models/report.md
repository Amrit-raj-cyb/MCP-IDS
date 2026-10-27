# External evaluation: data/benign_sampling_091_ml

* Sessions: 232 (232 benign, 0 attack); distinct feature vectors: 216
* Source dataset SHA-256: `06370ebfd8e8b433cb53ca2a8567f2b181dbb96adf471bd63ae43422a63c7367`

| Model | Sessions | FP | FPR | FPR 95% CI | Max benign score | Recall | Rows identical to training |
|---|---|---|---|---|---|---|---|
| expanded_20261009/random_forest (all) | 232 | 0 | 0.000 | 0.000–0.016 | 0.45 | – | 0 |
| expanded_20261009/random_forest (task not seen in training) | 232 | 0 | 0.000 | 0.000–0.016 | 0.45 | – |  |
| expanded_20261009/svm (all) | 232 | 103 | 0.444 | 0.382–0.508 | 0.7481 | – | 0 |
| expanded_20261009/svm (task not seen in training) | 232 | 103 | 0.444 | 0.382–0.508 | 0.7481 | – |  |
| expanded_20261009/xgboost (all) | 232 | 0 | 0.000 | 0.000–0.016 | 0.0896 | – | 0 |
| expanded_20261009/xgboost (task not seen in training) | 232 | 0 | 0.000 | 0.000–0.016 | 0.0896 | – |  |
| expanded_20261009/rf_xgb (all) | 232 | 0 | 0.000 | 0.000–0.016 | 0.2492 | – | 0 |
| expanded_20261009/rf_xgb (task not seen in training) | 232 | 0 | 0.000 | 0.000–0.016 | 0.2492 | – |  |
| expanded_20261009/decision_tree (all) | 232 | 0 | 0.000 | 0.000–0.016 | 0.0 | – | 0 |
| expanded_20261009/decision_tree (task not seen in training) | 232 | 0 | 0.000 | 0.000–0.016 | 0.0 | – |  |
| expanded_20261009/cnn (all) | 232 | 169 | 0.728 | 0.668–0.782 | 1.0 | – | 0 |
| expanded_20261009/cnn (task not seen in training) | 232 | 169 | 0.728 | 0.668–0.782 | 1.0 | – |  |

False positives by number of mounted servers:

| Model | 1 servers | 2 servers | 7 servers |
|---|---|---|---|
| expanded_20261009/random_forest | 0/60 (max 0.2333) | 0/56 (max 0.45) | 0/116 (max 0.4333) |
| expanded_20261009/svm | 5/60 (max 0.0211) | 36/56 (max 0.3904) | 62/116 (max 0.7481) |
| expanded_20261009/xgboost | 0/60 (max 0.0777) | 0/56 (max 0.0483) | 0/116 (max 0.0896) |
| expanded_20261009/rf_xgb | 0/60 (max 0.1364) | 0/56 (max 0.2492) | 0/116 (max 0.242) |
| expanded_20261009/decision_tree | 0/60 (max 0.0) | 0/56 (max 0.0) | 0/116 (max 0.0) |
| expanded_20261009/cnn | 37/60 (max 1.0) | 44/56 (max 1.0) | 88/116 (max 1.0) |

Flagged benign scenarios (false positives):

* expanded_20261009/random_forest: none
* expanded_20261009/svm: {'benign:helpdesk_triage_ticket:all_servers': 32, 'benign:helpdesk_order_reply': 24, 'benign:helpdesk_order_reply:all_servers': 18, 'benign:assist_translate_notes': 12, 'benign:assist_translate_notes:all_servers': 12, 'benign:helpdesk_triage_ticket': 5}
* expanded_20261009/xgboost: none
* expanded_20261009/rf_xgb: none
* expanded_20261009/decision_tree: none
* expanded_20261009/cnn: {'benign:helpdesk_triage_ticket:all_servers': 44, 'benign:helpdesk_triage_ticket': 37, 'benign:helpdesk_order_reply': 24, 'benign:helpdesk_order_reply:all_servers': 24, 'benign:assist_translate_notes': 20, 'benign:assist_translate_notes:all_servers': 20}
