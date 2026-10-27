# External evaluation: data/benign_unique_081_ml

* Sessions: 200 (200 benign, 0 attack); distinct feature vectors: 197
* Source dataset SHA-256: `b0118a9fe336525705ca7178616443e11f77611d9f078f29911d54104e0df8ba`

| Model | Sessions | FP | FPR | FPR 95% CI | Max benign score | Recall | Rows identical to training |
|---|---|---|---|---|---|---|---|
| phase9_081_20261009/random_forest (all) | 200 | 1 | 0.005 | 0.001–0.028 | 0.53 | – | 19 |
| phase9_081_20261009/random_forest (task seen in training) | 24 | 0 | 0.000 | 0.000–0.138 | 0.0867 | – |  |
| phase9_081_20261009/random_forest (task not seen in training) | 176 | 1 | 0.006 | 0.001–0.032 | 0.53 | – |  |
| phase9_081_20261009/svm (all) | 200 | 93 | 0.465 | 0.397–0.534 | 0.7539 | – | 19 |
| phase9_081_20261009/svm (task seen in training) | 24 | 0 | 0.000 | 0.000–0.138 | -0.301 | – |  |
| phase9_081_20261009/svm (task not seen in training) | 176 | 93 | 0.528 | 0.455–0.601 | 0.7539 | – |  |
| phase9_081_20261009/xgboost (all) | 200 | 3 | 0.015 | 0.005–0.043 | 0.99 | – | 19 |
| phase9_081_20261009/xgboost (task seen in training) | 24 | 0 | 0.000 | 0.000–0.138 | 0.1303 | – |  |
| phase9_081_20261009/xgboost (task not seen in training) | 176 | 3 | 0.017 | 0.006–0.049 | 0.99 | – |  |
| phase9_081_20261009/rf_xgb (all) | 200 | 3 | 0.015 | 0.005–0.043 | 0.76 | – | 19 |
| phase9_081_20261009/rf_xgb (task seen in training) | 24 | 0 | 0.000 | 0.000–0.138 | 0.1085 | – |  |
| phase9_081_20261009/rf_xgb (task not seen in training) | 176 | 3 | 0.017 | 0.006–0.049 | 0.76 | – |  |
| phase9_081_20261009/decision_tree (all) | 200 | 3 | 0.015 | 0.005–0.043 | 1.0 | – | 19 |
| phase9_081_20261009/decision_tree (task seen in training) | 24 | 0 | 0.000 | 0.000–0.138 | 0.0 | – |  |
| phase9_081_20261009/decision_tree (task not seen in training) | 176 | 3 | 0.017 | 0.006–0.049 | 1.0 | – |  |
| phase9_081_20261009/cnn (all) | 200 | 7 | 0.035 | 0.017–0.070 | 0.9894 | – | 19 |
| phase9_081_20261009/cnn (task seen in training) | 24 | 0 | 0.000 | 0.000–0.138 | 0.0046 | – |  |
| phase9_081_20261009/cnn (task not seen in training) | 176 | 7 | 0.040 | 0.019–0.080 | 0.9894 | – |  |

False positives by number of mounted servers:

| Model | 1 servers | 2 servers | 3 servers | 6 servers |
|---|---|---|---|---|
| phase9_081_20261009/random_forest | 0/89 (max 0.39) | 1/10 (max 0.53) | 0/1 (max 0.3933) | 0/100 (max 0.1567) |
| phase9_081_20261009/svm | 61/89 (max 0.7539) | 0/10 (max -0.1957) | 1/1 (max 0.3636) | 31/100 (max 0.7539) |
| phase9_081_20261009/xgboost | 0/89 (max 0.3711) | 2/10 (max 0.99) | 1/1 (max 0.986) | 0/100 (max 0.0447) |
| phase9_081_20261009/rf_xgb | 0/89 (max 0.2322) | 2/10 (max 0.76) | 1/1 (max 0.6896) | 0/100 (max 0.0851) |
| phase9_081_20261009/decision_tree | 0/89 (max 0.0) | 2/10 (max 1.0) | 1/1 (max 1.0) | 0/100 (max 0.0) |
| phase9_081_20261009/cnn | 7/89 (max 0.9894) | 0/10 (max 0.0023) | 0/1 (max 0.0) | 0/100 (max 0.0333) |

Flagged benign scenarios (false positives):

* phase9_081_20261009/random_forest: {'benign:multi_news_to_file': 1}
* phase9_081_20261009/svm: {'benign:fs_report_digest': 21, 'benign:fs_report_digest:all_servers': 14, 'benign:fs_find_data_files': 6, 'benign:web_faq_long': 6, 'benign:web_faq_long:all_servers': 6, 'benign:db_user_lookup': 5, 'benign:db_top_products': 4, 'benign:web_api_docs': 4, 'benign:fs_explore_documents': 3, 'benign:web_getting_started': 3, 'benign:fs_find_data_files:all_servers': 2, 'benign:db_order_status': 2, 'benign:db_order_status:all_servers': 2, 'benign:db_user_lookup:all_servers': 2, 'benign:db_add_log': 2, 'benign:db_new_order': 2, 'benign:web_news': 2, 'benign:fs_summarize_notes': 1, 'benign:fs_explore_documents:all_servers': 1, 'benign:db_top_products:all_servers': 1, 'benign:db_add_log:all_servers': 1, 'benign:db_new_order:all_servers': 1, 'benign:multi_price_check': 1, 'benign:multi_price_check:all_servers': 1}
* phase9_081_20261009/xgboost: {'benign:multi_news_to_file': 2, 'benign:multi_price_check': 1}
* phase9_081_20261009/rf_xgb: {'benign:multi_news_to_file': 2, 'benign:multi_price_check': 1}
* phase9_081_20261009/decision_tree: {'benign:multi_news_to_file': 2, 'benign:multi_price_check': 1}
* phase9_081_20261009/cnn: {'benign:fs_report_digest': 4, 'benign:fs_find_data_files': 2, 'benign:fs_explore_documents': 1}
