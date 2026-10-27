# External evaluation: data/benign_unique_081_ml

* Sessions: 200 (200 benign, 0 attack); distinct feature vectors: 197
* Source dataset SHA-256: `b0118a9fe336525705ca7178616443e11f77611d9f078f29911d54104e0df8ba`

| Model | Sessions | FP | FPR | FPR 95% CI | Max benign score | Recall | Rows identical to training |
|---|---|---|---|---|---|---|---|
| combined_sampling_20261010_v2/random_forest (all) | 200 | 0 | 0.000 | 0.000–0.019 | 0.4677 | – | 13 |
| combined_sampling_20261010_v2/random_forest (task seen in training) | 160 | 0 | 0.000 | 0.000–0.023 | 0.4677 | – |  |
| combined_sampling_20261010_v2/random_forest (task not seen in training) | 40 | 0 | 0.000 | 0.000–0.088 | 0.0019 | – |  |
| combined_sampling_20261010_v2/svm (all) | 200 | 0 | 0.000 | 0.000–0.019 | -0.7875 | – | 13 |
| combined_sampling_20261010_v2/svm (task seen in training) | 160 | 0 | 0.000 | 0.000–0.023 | -0.7875 | – |  |
| combined_sampling_20261010_v2/svm (task not seen in training) | 40 | 0 | 0.000 | 0.000–0.088 | -0.8731 | – |  |
| combined_sampling_20261010_v2/xgboost (all) | 200 | 0 | 0.000 | 0.000–0.019 | 0.1029 | – | 13 |
| combined_sampling_20261010_v2/xgboost (task seen in training) | 160 | 0 | 0.000 | 0.000–0.023 | 0.1029 | – |  |
| combined_sampling_20261010_v2/xgboost (task not seen in training) | 40 | 0 | 0.000 | 0.000–0.088 | 0.0043 | – |  |
| combined_sampling_20261010_v2/rf_xgb (all) | 200 | 0 | 0.000 | 0.000–0.019 | 0.2853 | – | 13 |
| combined_sampling_20261010_v2/rf_xgb (task seen in training) | 160 | 0 | 0.000 | 0.000–0.023 | 0.2853 | – |  |
| combined_sampling_20261010_v2/rf_xgb (task not seen in training) | 40 | 0 | 0.000 | 0.000–0.088 | 0.0021 | – |  |
| combined_sampling_20261010_v2/decision_tree (all) | 200 | 3 | 0.015 | 0.005–0.043 | 1.0 | – | 13 |
| combined_sampling_20261010_v2/decision_tree (task seen in training) | 160 | 3 | 0.019 | 0.006–0.054 | 1.0 | – |  |
| combined_sampling_20261010_v2/decision_tree (task not seen in training) | 40 | 0 | 0.000 | 0.000–0.088 | 0.0 | – |  |
| combined_sampling_20261010_v2/cnn (all) | 200 | 0 | 0.000 | 0.000–0.019 | 0.0023 | – | 13 |
| combined_sampling_20261010_v2/cnn (task seen in training) | 160 | 0 | 0.000 | 0.000–0.023 | 0.0023 | – |  |
| combined_sampling_20261010_v2/cnn (task not seen in training) | 40 | 0 | 0.000 | 0.000–0.088 | 0.0001 | – |  |
| combined_sampling_20261010_v2/cnn_raw (all) | 200 | 123 | 0.615 | 0.546–0.680 | 0.6121 | – | 12 |
| combined_sampling_20261010_v2/cnn_raw (task seen in training) | 160 | 94 | 0.588 | 0.510–0.661 | 0.6121 | – |  |
| combined_sampling_20261010_v2/cnn_raw (task not seen in training) | 40 | 29 | 0.725 | 0.572–0.839 | 0.597 | – |  |

False positives by number of mounted servers:

| Model | 1 servers | 2 servers | 3 servers | 6 servers |
|---|---|---|---|---|
| combined_sampling_20261010_v2/random_forest | 0/89 (max 0.0019) | 0/10 (max 0.4112) | 0/1 (max 0.4677) | 0/100 (max 0.0189) |
| combined_sampling_20261010_v2/svm | 0/89 (max -2.7202) | 0/10 (max -1.4122) | 0/1 (max -2.8279) | 0/100 (max -0.7875) |
| combined_sampling_20261010_v2/xgboost | 0/89 (max 0.0036) | 0/10 (max 0.0904) | 0/1 (max 0.1029) | 0/100 (max 0.0043) |
| combined_sampling_20261010_v2/rf_xgb | 0/89 (max 0.0018) | 0/10 (max 0.2508) | 0/1 (max 0.2853) | 0/100 (max 0.0096) |
| combined_sampling_20261010_v2/decision_tree | 0/89 (max 0.0) | 2/10 (max 1.0) | 1/1 (max 1.0) | 0/100 (max 0.0) |
| combined_sampling_20261010_v2/cnn | 0/89 (max 0.0) | 0/10 (max 0.0) | 0/1 (max 0.0005) | 0/100 (max 0.0023) |
| combined_sampling_20261010_v2/cnn_raw | 21/89 (max 0.597) | 4/10 (max 0.6121) | 0/1 (max 0.0088) | 98/100 (max 0.597) |

Flagged benign scenarios (false positives):

* combined_sampling_20261010_v2/random_forest: none
* combined_sampling_20261010_v2/svm: none
* combined_sampling_20261010_v2/xgboost: none
* combined_sampling_20261010_v2/rf_xgb: none
* combined_sampling_20261010_v2/decision_tree: {'benign:multi_news_to_file': 2, 'benign:multi_price_check': 1}
* combined_sampling_20261010_v2/cnn: none
* combined_sampling_20261010_v2/cnn_raw: {'benign:fs_report_digest:all_servers': 24, 'benign:fs_find_data_files:all_servers': 8, 'benign:db_top_products:all_servers': 8, 'benign:db_user_lookup:all_servers': 8, 'benign:web_faq_long:all_servers': 6, 'benign:fs_summarize_notes:all_servers': 4, 'benign:fs_explore_documents:all_servers': 4, 'benign:db_top_products': 4, 'benign:db_order_status': 4, 'benign:db_order_status:all_servers': 4, 'benign:db_user_lookup': 4, 'benign:db_add_log:all_servers': 4, 'benign:db_new_order:all_servers': 4, 'benign:web_api_docs:all_servers': 4, 'benign:calc_temperature:all_servers': 4, 'benign:db_new_order': 3, 'benign:web_getting_started:all_servers': 3, 'benign:fs_summarize_notes': 2, 'benign:web_news:all_servers': 2, 'benign:multi_news_to_file:all_servers': 2, 'benign:multi_db_report:all_servers': 2, 'benign:calc_add': 2, 'benign:calc_temperature': 2, 'benign:calc_add:all_servers': 2, 'benign:multi_order_share': 2, 'benign:multi_region_share': 2, 'benign:multi_order_share:all_servers': 2, 'benign:multi_region_share:all_servers': 2, 'benign:multi_price_check:all_servers': 1}
