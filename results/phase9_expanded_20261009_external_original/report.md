# External evaluation: data/expanded_20261006_holdout_original_ml

* Sessions: 634 (634 benign, 0 attack); distinct feature vectors: 601
* Source dataset SHA-256: `12a010f1cdfbe55bae4ebd94dc425ad0f9543759ed7cd59ab432950d0d4dcf6a`

| Model | Sessions | FP | FPR | FPR 95% CI | Max benign score | Recall | Rows identical to training |
|---|---|---|---|---|---|---|---|
| phase9_expanded_20261009/random_forest (all) | 634 | 3 | 0.005 | 0.002–0.014 | 0.5667 | – | 29 |
| phase9_expanded_20261009/random_forest (task seen in training) | 24 | 0 | 0.000 | 0.000–0.138 | 0.0167 | – |  |
| phase9_expanded_20261009/random_forest (task not seen in training) | 610 | 3 | 0.005 | 0.002–0.014 | 0.5667 | – |  |
| phase9_expanded_20261009/svm (all) | 634 | 255 | 0.402 | 0.365–0.441 | 0.7812 | – | 29 |
| phase9_expanded_20261009/svm (task seen in training) | 24 | 0 | 0.000 | 0.000–0.138 | -0.4788 | – |  |
| phase9_expanded_20261009/svm (task not seen in training) | 610 | 255 | 0.418 | 0.380–0.458 | 0.7812 | – |  |
| phase9_expanded_20261009/xgboost (all) | 634 | 44 | 0.069 | 0.052–0.092 | 0.9985 | – | 29 |
| phase9_expanded_20261009/xgboost (task seen in training) | 24 | 0 | 0.000 | 0.000–0.138 | 0.0109 | – |  |
| phase9_expanded_20261009/xgboost (task not seen in training) | 610 | 44 | 0.072 | 0.054–0.095 | 0.9985 | – |  |
| phase9_expanded_20261009/rf_xgb (all) | 634 | 27 | 0.043 | 0.029–0.061 | 0.7823 | – | 29 |
| phase9_expanded_20261009/rf_xgb (task seen in training) | 24 | 0 | 0.000 | 0.000–0.138 | 0.0123 | – |  |
| phase9_expanded_20261009/rf_xgb (task not seen in training) | 610 | 27 | 0.044 | 0.031–0.064 | 0.7823 | – |  |
| phase9_expanded_20261009/decision_tree (all) | 634 | 10 | 0.016 | 0.009–0.029 | 1.0 | – | 29 |
| phase9_expanded_20261009/decision_tree (task seen in training) | 24 | 0 | 0.000 | 0.000–0.138 | 0.0 | – |  |
| phase9_expanded_20261009/decision_tree (task not seen in training) | 610 | 10 | 0.016 | 0.009–0.030 | 1.0 | – |  |
| phase9_expanded_20261009/cnn (all) | 634 | 42 | 0.066 | 0.049–0.088 | 0.9993 | – | 29 |
| phase9_expanded_20261009/cnn (task seen in training) | 24 | 0 | 0.000 | 0.000–0.138 | 0.0004 | – |  |
| phase9_expanded_20261009/cnn (task not seen in training) | 610 | 42 | 0.069 | 0.051–0.092 | 0.9993 | – |  |

False positives by number of mounted servers:

| Model | 1 servers | 2 servers | 3 servers | 6 servers |
|---|---|---|---|---|
| phase9_expanded_20261009/random_forest | 0/287 (max 0.4133) | 3/29 (max 0.5667) | 0/1 (max 0.4133) | 0/317 (max 0.17) |
| phase9_expanded_20261009/svm | 150/287 (max 0.7812) | 9/29 (max 0.7648) | 1/1 (max 0.3969) | 95/317 (max 0.7812) |
| phase9_expanded_20261009/xgboost | 13/287 (max 0.9326) | 13/29 (max 0.9985) | 1/1 (max 0.9972) | 17/317 (max 0.7335) |
| phase9_expanded_20261009/rf_xgb | 13/287 (max 0.596) | 13/29 (max 0.7823) | 1/1 (max 0.7053) | 0/317 (max 0.4368) |
| phase9_expanded_20261009/decision_tree | 0/287 (max 0.0) | 9/29 (max 1.0) | 1/1 (max 1.0) | 0/317 (max 0.0) |
| phase9_expanded_20261009/cnn | 42/287 (max 0.9993) | 0/29 (max 0.0009) | 0/1 (max 0.0) | 0/317 (max 0.0151) |

Flagged benign scenarios (false positives):

* phase9_expanded_20261009/random_forest: {'benign:multi_news_to_file': 2, 'benign:multi_web_db_prices': 1}
* phase9_expanded_20261009/svm: {'benign:fs_report_digest': 20, 'benign:web_docs_tour': 16, 'benign:fs_report_digest:all_servers': 14, 'benign:fs_json_summary': 12, 'benign:db_recent_orders': 11, 'benign:db_recent_orders:all_servers': 10, 'benign:web_docs_tour:all_servers': 10, 'benign:db_low_stock': 9, 'benign:fs_write_todo': 8, 'benign:fs_search_reports': 8, 'benign:fs_search_reports:all_servers': 8, 'benign:fs_copy_notes': 8, 'benign:fs_json_summary:all_servers': 8, 'benign:web_products_list': 8, 'benign:multi_db_to_csv': 8, 'benign:db_error_logs': 7, 'benign:web_faq_long': 6, 'benign:web_faq_long:all_servers': 6, 'benign:db_error_logs:all_servers': 6, 'benign:web_about_team': 6, 'benign:multi_db_to_csv:all_servers': 6, 'benign:db_user_lookup': 5, 'benign:db_low_stock:all_servers': 5, 'benign:db_top_products': 4, 'benign:web_api_docs': 4, 'benign:web_products_list:all_servers': 4, 'benign:fs_find_data_files': 3, 'benign:db_user_lookup:all_servers': 3, 'benign:db_add_log': 3, 'benign:web_getting_started': 3, 'benign:fs_find_data_files:all_servers': 2, 'benign:db_top_products:all_servers': 2, 'benign:db_order_status': 2, 'benign:db_order_status:all_servers': 2, 'benign:db_new_order': 2, 'benign:web_news': 2, 'benign:calc_unit_report': 2, 'benign:calc_unit_report:all_servers': 2, 'benign:fs_explore_documents': 1, 'benign:fs_explore_documents:all_servers': 1, 'benign:db_add_log:all_servers': 1, 'benign:db_new_order:all_servers': 1, 'benign:web_api_docs:all_servers': 1, 'benign:multi_price_check': 1, 'benign:multi_price_check:all_servers': 1, 'benign:web_about_team:all_servers': 1, 'benign:multi_web_db_prices': 1, 'benign:multi_web_db_prices:all_servers': 1}
* phase9_expanded_20261009/xgboost: {'benign:web_faq_long': 6, 'benign:web_faq_long:all_servers': 6, 'benign:web_products_list': 4, 'benign:web_products_list:all_servers': 4, 'benign:multi_db_to_csv': 4, 'benign:multi_db_to_csv:all_servers': 4, 'benign:multi_news_growth': 4, 'benign:db_error_logs': 3, 'benign:db_error_logs:all_servers': 3, 'benign:multi_web_db_prices': 3, 'benign:multi_news_to_file': 2, 'benign:multi_price_check': 1}
* phase9_expanded_20261009/rf_xgb: {'benign:web_faq_long': 6, 'benign:web_products_list': 4, 'benign:multi_db_to_csv': 4, 'benign:multi_news_growth': 4, 'benign:db_error_logs': 3, 'benign:multi_web_db_prices': 3, 'benign:multi_news_to_file': 2, 'benign:multi_price_check': 1}
* phase9_expanded_20261009/decision_tree: {'benign:multi_news_growth': 4, 'benign:multi_web_db_prices': 3, 'benign:multi_news_to_file': 2, 'benign:multi_price_check': 1}
* phase9_expanded_20261009/cnn: {'benign:fs_search_reports': 27, 'benign:calc_unit_report': 6, 'benign:fs_find_data_files': 4, 'benign:fs_explore_documents': 3, 'benign:web_docs_tour': 2}
