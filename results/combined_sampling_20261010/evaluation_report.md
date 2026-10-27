# Evaluation report: exp_015_combined_sampling_20261010

> **This experiment demonstrates the functionality of the ML pipeline, but the dataset is too small to establish strong real-world generalization.**

## Setup
* Dataset: `/lab/data/combined_sampling_20261010` (read-only), SHA-256 `74a73e6f87f1ceae...`
* Sessions: 1586 (1226 benign, 360 attack across poisoned_tool, sampling_injection, shadowing); protocol/mock success count (not real LLM influence): 213
* Features: 65 ({'structural': 26, 'behavioral': 19, 'content': 20}); lab marker/canary removed with `neutralize()`
* Split: task-grouped (whole tasks held out: 28 training / 14 test tasks), seed 42, test size 0.3 → train 1116 (816 benign / 300 attack), test 470 (410 benign / 60 attack)
* Positive class: `attack` = attack **attempted** (not success)

## Headline: task-grouped cross-validation with 95 % confidence intervals (hyperparameters tuned, nested)
Protocol: nested task-grouped cross-validation (GroupKFold(n_splits=5) on task_id, 42 tasks; hyperparameters tuned inside each outer training fold); no task is in both train and test, so seed-level near-duplicates cannot be memorised; the held-out tasks never influence the chosen settings. **Quote these numbers**, not the single split in section 2.

| Model | F1 [95 % CI] | Precision [95 % CI] | Recall [95 % CI] | FPR [95 % CI] | Recall poisoned_tool | Recall sampling_injection | Recall shadowing | Baseline-split F1 | Untuned F1 |
|---|---|---|---|---|---|---|---|---|---|
| Random Forest | 0.800 [0.33, 1.00] | 1.000 [1.00, 1.00] | 0.667 [0.20, 1.00] | 0.000 [0.00, 0.00] | 1.00 | 0.00 | 1.00 | 1.000 | 0.800 |
| SVM (RBF) | 0.643 [0.18, 0.94] | 0.705 [0.21, 0.99] | 0.592 [0.14, 0.98] | 0.073 [0.00, 0.18] | 0.78 | 0.00 | 1.00 | 0.857 | 0.782 |
| XGBoost | 0.797 [0.33, 1.00] | 0.992 [0.94, 1.00] | 0.667 [0.20, 1.00] | 0.002 [0.00, 0.01] | 1.00 | 0.00 | 1.00 | 1.000 | 0.797 |
| RF + XGBoost (soft vote) | 0.797 [0.33, 1.00] | 0.992 [0.94, 1.00] | 0.667 [0.20, 1.00] | 0.002 [0.00, 0.01] | 1.00 | 0.00 | 1.00 | 1.000 | 0.797 |
| Decision Tree | 0.795 [0.33, 1.00] | 0.984 [0.93, 1.00] | 0.667 [0.20, 1.00] | 0.003 [0.00, 0.01] | 1.00 | 0.00 | 1.00 | 0.889 | 0.746 |
| 1-D CNN | 0.744 [0.28, 0.99] | 0.876 [0.45, 1.00] | 0.647 [0.20, 1.00] | 0.027 [0.00, 0.08] | 0.94 | 0.00 | 1.00 | 0.846 | 0.728 |
| Raw-traffic CNN | 0.438 [0.16, 0.81] | 0.473 [0.31, 0.89] | 0.408 [0.10, 0.97] | 0.134 [0.01, 0.32] | 0.72 | 0.50 | 0.00 | 0.462 | 0.474 |

Intervals: task-cluster bootstrap, 2000 resamples of 42 groups (valid resamples: 1995). Sessions of one task are not independent, so whole tasks are resampled; with few tasks the intervals are wide. Per-session Wilson intervals, which ignore that dependence, are narrower (Random Forest recall [0.62, 0.71], FPR [0.00, 0.00]) and are stored in `metrics.json` for every model.

## 1. Baseline split: TRAINING metrics (not evidence of generalization)
| Model | Accuracy | Precision | Recall | F1 | FPR | Latency |
|---|---|---|---|---|---|---|
| Random Forest | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| SVM (RBF) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| XGBoost | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| RF + XGBoost (soft vote) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| Decision Tree | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| 1-D CNN | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| Raw-traffic CNN | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |

## 2. Baseline split: TEST metrics (task-grouped split; one split only, see the headline above)
| Model | Accuracy | Precision | Recall | F1 | FPR | Latency (model only, median) |
|---|---|---|---|---|---|---|
| Random Forest | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 26.20 ms |
| SVM (RBF) | 0.962 | 0.818 | 0.900 | 0.857 | 0.029 | 3.70 ms |
| XGBoost | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 3.70 ms |
| RF + XGBoost (soft vote) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 26.28 ms |
| Decision Tree | 0.975 | 1.000 | 0.800 | 0.889 | 0.000 | 2.81 ms |
| 1-D CNN | 0.966 | 1.000 | 0.733 | 0.846 | 0.000 | 4.48 ms |
| Raw-traffic CNN | 0.911 | 1.000 | 0.300 | 0.462 | 0.000 | 5.55 ms |

Confusion matrices (test): `confusion_matrix_rf.png`, `confusion_matrix_svm.png`, `confusion_matrix_xgb.png`, `confusion_matrix_rf_xgb.png`, `confusion_matrix_dt.png`, `confusion_matrix_cnn.png`, `confusion_matrix_cnn_raw.png`

* Random Forest: TN=410 FP=0 FN=0 TP=60; end-to-end latency (read logs + features + model) median 68.3 ms; recall on attacks that succeeded 1.0 (n=26), that did not succeed 1.0 (n=34)
* SVM (RBF): TN=398 FP=12 FN=6 TP=54; end-to-end latency (read logs + features + model) median 12.9 ms; recall on attacks that succeeded 0.9615 (n=26), that did not succeed 0.8529 (n=34)
* XGBoost: TN=410 FP=0 FN=0 TP=60; end-to-end latency (read logs + features + model) median 13.5 ms; recall on attacks that succeeded 1.0 (n=26), that did not succeed 1.0 (n=34)
* RF + XGBoost (soft vote): TN=410 FP=0 FN=0 TP=60; end-to-end latency (read logs + features + model) median 57.9 ms; recall on attacks that succeeded 1.0 (n=26), that did not succeed 1.0 (n=34)
* Decision Tree: TN=410 FP=0 FN=12 TP=48; end-to-end latency (read logs + features + model) median 9.4 ms; recall on attacks that succeeded 0.8077 (n=26), that did not succeed 0.7941 (n=34)
* 1-D CNN: TN=410 FP=0 FN=16 TP=44; end-to-end latency (read logs + features + model) median 13.5 ms; recall on attacks that succeeded 0.8462 (n=26), that did not succeed 0.6471 (n=34)
* Raw-traffic CNN: TN=410 FP=0 FN=42 TP=18; end-to-end latency (read logs + features + model) median 15.7 ms; recall on attacks that succeeded 0.2692 (n=26), that did not succeed 0.3235 (n=34)

Per payload style in the test set (n is tiny):

| Style | n | RF recall | SVM recall | XGB recall | RF+XGB recall | DT recall | CNN recall | Raw CNN recall |
|---|---|---|---|---|---|---|---|---|
| overt | 12 | 1.00 | 0.92 | 1.00 | 1.00 | 1.00 | 0.42 | 0.50 |
| padded | 12 | 1.00 | 1.00 | 1.00 | 1.00 | 0.50 | 1.00 | 0.50 |
| param | 12 | 1.00 | 0.92 | 1.00 | 1.00 | 1.00 | 0.92 | 0.00 |
| polite | 12 | 1.00 | 0.75 | 1.00 | 1.00 | 0.50 | 0.33 | 0.00 |
| tagged | 12 | 1.00 | 0.92 | 1.00 | 1.00 | 1.00 | 1.00 | 0.50 |

## 3. Hold-one-payload-style-out (generalization to an unseen style)
Train: benign-train + attacks of the other 4 styles. Test: benign-test + all attacks of the held-out style. Payload-style holdout, NOT a family holdout. Benign train/test: 816/410.

**This is a payload-style holdout within `poisoned_tool`, not the family holdout.** The three-family experiment follows below.

| Held-out poisoned-tool style | test attacks | Model | Recall | FPR | F1 |
|---|---:|---|---:|---:|---:|
| overt | 24 | Random Forest | 1.00 | 0.00 | 1.00 |
| overt | 24 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| overt | 24 | XGBoost | 1.00 | 0.00 | 1.00 |
| overt | 24 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| overt | 24 | Decision Tree | 1.00 | 0.00 | 1.00 |
| overt | 24 | 1-D CNN | 1.00 | 0.00 | 1.00 |
| overt | 24 | Raw-traffic CNN | 0.75 | 0.20 | 0.29 |
| padded | 24 | Random Forest | 0.00 | 0.00 | 0.00 |
| padded | 24 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| padded | 24 | XGBoost | 0.50 | 0.00 | 0.67 |
| padded | 24 | RF + XGBoost (soft vote) | 0.50 | 0.00 | 0.67 |
| padded | 24 | Decision Tree | 0.50 | 0.00 | 0.67 |
| padded | 24 | 1-D CNN | 1.00 | 0.00 | 1.00 |
| padded | 24 | Raw-traffic CNN | 0.79 | 0.20 | 0.30 |
| param | 24 | Random Forest | 0.00 | 0.00 | 0.00 |
| param | 24 | SVM (RBF) | 0.12 | 0.00 | 0.22 |
| param | 24 | XGBoost | 0.00 | 0.00 | 0.00 |
| param | 24 | RF + XGBoost (soft vote) | 0.00 | 0.00 | 0.00 |
| param | 24 | Decision Tree | 0.00 | 0.00 | 0.00 |
| param | 24 | 1-D CNN | 0.42 | 0.00 | 0.59 |
| param | 24 | Raw-traffic CNN | 0.79 | 0.20 | 0.30 |
| polite | 24 | Random Forest | 0.00 | 0.00 | 0.00 |
| polite | 24 | SVM (RBF) | 0.12 | 0.00 | 0.22 |
| polite | 24 | XGBoost | 0.00 | 0.00 | 0.00 |
| polite | 24 | RF + XGBoost (soft vote) | 0.00 | 0.00 | 0.00 |
| polite | 24 | Decision Tree | 0.00 | 0.00 | 0.00 |
| polite | 24 | 1-D CNN | 0.79 | 0.00 | 0.88 |
| polite | 24 | Raw-traffic CNN | 0.04 | 0.13 | 0.03 |
| tagged | 24 | Random Forest | 1.00 | 0.00 | 1.00 |
| tagged | 24 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| tagged | 24 | XGBoost | 1.00 | 0.00 | 1.00 |
| tagged | 24 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| tagged | 24 | Decision Tree | 1.00 | 0.00 | 1.00 |
| tagged | 24 | 1-D CNN | 1.00 | 0.00 | 1.00 |
| tagged | 24 | Raw-traffic CNN | 0.50 | 0.20 | 0.20 |

## 3a. Hold-one-attack-family-out
For each fold, train on benign training sessions and all other attack families; test on benign test sessions plus the held-out attack family. This is a family holdout.

| Held-out family | test attacks | Model | Recall | FPR | F1 |
|---|---:|---|---:|---:|---:|
| poisoned_tool | 120 | Random Forest | 0.00 | 0.00 | 0.00 |
| poisoned_tool | 120 | SVM (RBF) | 0.12 | 0.11 | 0.17 |
| poisoned_tool | 120 | XGBoost | 0.00 | 0.00 | 0.00 |
| poisoned_tool | 120 | RF + XGBoost (soft vote) | 0.00 | 0.00 | 0.00 |
| poisoned_tool | 120 | Decision Tree | 0.10 | 0.00 | 0.18 |
| poisoned_tool | 120 | 1-D CNN | 0.14 | 0.00 | 0.25 |
| poisoned_tool | 120 | Raw-traffic CNN | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | Random Forest | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | SVM (RBF) | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | XGBoost | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | RF + XGBoost (soft vote) | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | Decision Tree | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | 1-D CNN | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | Raw-traffic CNN | 0.00 | 0.22 | 0.00 |
| shadowing | 120 | Random Forest | 1.00 | 0.00 | 1.00 |
| shadowing | 120 | SVM (RBF) | 1.00 | 0.06 | 0.91 |
| shadowing | 120 | XGBoost | 1.00 | 0.00 | 1.00 |
| shadowing | 120 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| shadowing | 120 | Decision Tree | 1.00 | 0.00 | 1.00 |
| shadowing | 120 | 1-D CNN | 1.00 | 0.03 | 0.95 |
| shadowing | 120 | Raw-traffic CNN | 0.00 | 0.20 | 0.00 |

## 4. Feature-group ablation (same split, test set)
| Features | # | Model | Recall | FPR | F1 |
|---|---:|---|---:|---:|---:|
| all | 65 | Random Forest | 1.00 | 0.00 | 1.00 |
| all | 65 | SVM (RBF) | 0.90 | 0.03 | 0.86 |
| all | 65 | XGBoost | 1.00 | 0.00 | 1.00 |
| all | 65 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| all | 65 | Decision Tree | 0.80 | 0.00 | 0.89 |
| all | 65 | 1-D CNN | 0.73 | 0.00 | 0.85 |
| structural | 26 | Random Forest | 0.50 | 0.00 | 0.67 |
| structural | 26 | SVM (RBF) | 0.55 | 0.26 | 0.33 |
| structural | 26 | XGBoost | 0.82 | 0.00 | 0.90 |
| structural | 26 | RF + XGBoost (soft vote) | 0.72 | 0.00 | 0.83 |
| structural | 26 | Decision Tree | 0.72 | 0.02 | 0.77 |
| structural | 26 | 1-D CNN | 0.42 | 0.06 | 0.46 |
| behavioral | 19 | Random Forest | 0.18 | 0.13 | 0.18 |
| behavioral | 19 | SVM (RBF) | 0.00 | 0.09 | 0.00 |
| behavioral | 19 | XGBoost | 0.18 | 0.12 | 0.18 |
| behavioral | 19 | RF + XGBoost (soft vote) | 0.18 | 0.13 | 0.18 |
| behavioral | 19 | Decision Tree | 0.18 | 0.12 | 0.18 |
| behavioral | 19 | 1-D CNN | 0.18 | 0.13 | 0.18 |
| content | 20 | Random Forest | 1.00 | 0.00 | 1.00 |
| content | 20 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| content | 20 | XGBoost | 1.00 | 0.00 | 1.00 |
| content | 20 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| content | 20 | Decision Tree | 0.80 | 0.00 | 0.89 |
| content | 20 | 1-D CNN | 0.90 | 0.00 | 0.95 |
| structural+behavioral | 45 | Random Forest | 0.12 | 0.00 | 0.21 |
| structural+behavioral | 45 | SVM (RBF) | 0.33 | 0.14 | 0.29 |
| structural+behavioral | 45 | XGBoost | 0.82 | 0.00 | 0.90 |
| structural+behavioral | 45 | RF + XGBoost (soft vote) | 0.80 | 0.00 | 0.89 |
| structural+behavioral | 45 | Decision Tree | 0.67 | 0.02 | 0.73 |
| structural+behavioral | 45 | 1-D CNN | 0.27 | 0.00 | 0.42 |

**Confound check:** a Random Forest that sees only `n_servers_mounted` reaches accuracy 0.58, recall 0.50, FPR 0.41 on the test set (majority-class accuracy would be 0.87). Server-count distributions are matched by construction in this Phase 9 dataset.

## 5. Supplementary: RepeatedStratifiedKFold(n_splits=5, n_repeats=5) on all 1586 sessions
| Model | Accuracy | Precision | Recall | F1 | FPR |
|---|---|---|---|---|---|
| Random Forest | 0.998 ± 0.002 | 0.990 ± 0.009 | 1.000 ± 0.000 | 0.995 ± 0.004 | 0.003 ± 0.003 |
| SVM (RBF) | 0.999 ± 0.001 | 0.997 ± 0.005 | 1.000 ± 0.000 | 0.999 ± 0.003 | 0.001 ± 0.002 |
| XGBoost | 1.000 ± 0.001 | 1.000 ± 0.003 | 1.000 ± 0.000 | 1.000 ± 0.001 | 0.000 ± 0.001 |
| RF + XGBoost (soft vote) | 0.999 ± 0.002 | 0.996 ± 0.007 | 1.000 ± 0.000 | 0.998 ± 0.004 | 0.001 ± 0.002 |
| Decision Tree | 0.998 ± 0.002 | 0.992 ± 0.008 | 1.000 ± 0.000 | 0.996 ± 0.004 | 0.002 ± 0.002 |
| 1-D CNN | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.000 ± 0.000 |

## 5a. Baseline duplicate check
0 of 470 baseline test sessions have an **exact feature-vector copy** in the training set (by group: none). The dataset has 941 distinct feature vectors among 1586 sessions. Few or no exact copies: the baseline split is not dominated by memorised sessions (near-duplicates can still exist; compare with the task-grouped results below).

## 5b. Task-grouped CV (more honest generalization estimate)
GroupKFold(n_splits=5) on task_id over 42 tasks: no task is in both train and test; every session is predicted out-of-fold and metrics are pooled.

| Model | Accuracy | Precision | Recall | F1 | FPR | Recall poisoned_tool | Recall sampling_injection | Recall shadowing |
|---|---|---|---|---|---|---|---|---|
| Random Forest | 0.924 | 1.000 | 0.667 | 0.800 | 0.000 | 1.00 | 0.00 | 1.00 |
| SVM (RBF) | 0.918 | 0.987 | 0.647 | 0.782 | 0.002 | 0.94 | 0.00 | 1.00 |
| XGBoost | 0.923 | 0.992 | 0.667 | 0.797 | 0.002 | 1.00 | 0.00 | 1.00 |
| RF + XGBoost (soft vote) | 0.923 | 0.992 | 0.667 | 0.797 | 0.002 | 1.00 | 0.00 | 1.00 |
| Decision Tree | 0.907 | 0.986 | 0.600 | 0.746 | 0.002 | 0.80 | 0.00 | 1.00 |
| 1-D CNN | 0.891 | 0.838 | 0.644 | 0.728 | 0.037 | 0.93 | 0.00 | 1.00 |
| Raw-traffic CNN | 0.803 | 0.600 | 0.392 | 0.474 | 0.077 | 0.68 | 0.50 | 0.00 |

Folds (held-out tasks): 1: calc_unit_report, fs_find_data_files, fs_shadowing_probe, fs_summarize_notes, multi_price_check, web_about_team, web_getting_started (318 sessions); 2: assist_summarize_text, db_new_order, fs_copy_notes, fs_sampling_probe, multi_news_to_file, multi_notes_to_log, web_api_docs (318 sessions); 3: db_country_counts, db_user_lookup, fs_explore_documents, fs_json_summary, fs_write_todo, helpdesk_triage_ticket, multi_order_share, multi_web_db_prices, web_products_list (316 sessions); 4: calc_add, db_add_log, db_low_stock, fs_search_reports, helpdesk_order_reply, multi_db_to_csv, multi_news_growth, web_docs_tour, web_faq_long (316 sessions); 5: assist_translate_notes, calc_temperature, db_error_logs, db_order_status, db_recent_orders, db_top_products, fs_report_digest, multi_db_report, multi_region_share, web_news (318 sessions)

## 5b-tuned. Nested task-grouped CV (hyperparameters tuned inside each outer fold)
Nested CV: for each outer fold, hyperparameters are searched on the outer training tasks only (inner GroupKFold(3) on task_id, pooled out-of-fold F1; ml/tuning.py), then the model is refitted with the winner and predicts the held-out tasks.

| Model | Precision | Recall | F1 | FPR | Recall poisoned_tool | Recall sampling_injection | Recall shadowing | Untuned F1 (5b) |
|---|---|---|---|---|---|---|---|---|
| Random Forest | 1.000 | 0.667 | 0.800 | 0.000 | 1.00 | 0.00 | 1.00 | 0.800 |
| SVM (RBF) | 0.705 | 0.592 | 0.643 | 0.073 | 0.78 | 0.00 | 1.00 | 0.782 |
| XGBoost | 0.992 | 0.667 | 0.797 | 0.002 | 1.00 | 0.00 | 1.00 | 0.797 |
| RF + XGBoost (soft vote) | 0.992 | 0.667 | 0.797 | 0.002 | 1.00 | 0.00 | 1.00 | 0.797 |
| Decision Tree | 0.984 | 0.667 | 0.795 | 0.003 | 1.00 | 0.00 | 1.00 | 0.746 |
| 1-D CNN | 0.876 | 0.647 | 0.744 | 0.027 | 0.94 | 0.00 | 1.00 | 0.728 |
| Raw-traffic CNN | 0.473 | 0.408 | 0.438 | 0.134 | 0.72 | 0.50 | 0.00 | 0.474 |

Settings chosen in each outer fold (fold 1 ... 5):

* Random Forest: {"max_depth": null, "max_features": 0.5, "min_samples_leaf": 1, "n_estimators": 600}; {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 300}; {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 300}; {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 300}; {"max_depth": null, "max_features": 0.5, "min_samples_leaf": 1, "n_estimators": 300}
* SVM (RBF): {"C": 100.0, "gamma": 0.001}; {"C": 100.0, "gamma": 0.001}; {"C": 10.0, "gamma": 0.001}; {"C": 0.1, "gamma": 0.001}; {"C": 100.0, "gamma": 0.001}
* XGBoost: {"learning_rate": 0.03, "max_depth": 6, "n_estimators": 100, "subsample": 1.0}; {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 300, "subsample": 1.0}; {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 300, "subsample": 1.0}; {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 300, "subsample": 1.0}; {"learning_rate": 0.3, "max_depth": 3, "n_estimators": 300, "subsample": 1.0}
* RF + XGBoost (soft vote): {"random_forest": {"max_depth": null, "max_features": 0.5, "min_samples_leaf": 1, "n_estimators": 600}, "xgboost": {"learning_rate": 0.03, "max_depth": 6, "n_estimators": 100, "subsample": 1.0}}; {"random_forest": {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 300}, "xgboost": {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 300, "subsample": 1.0}}; {"random_forest": {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 300}, "xgboost": {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 300, "subsample": 1.0}}; {"random_forest": {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 300}, "xgboost": {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 300, "subsample": 1.0}}; {"random_forest": {"max_depth": null, "max_features": 0.5, "min_samples_leaf": 1, "n_estimators": 300}, "xgboost": {"learning_rate": 0.3, "max_depth": 3, "n_estimators": 300, "subsample": 1.0}}
* Decision Tree: {"criterion": "gini", "max_depth": null, "min_samples_leaf": 10}; {"criterion": "gini", "max_depth": null, "min_samples_leaf": 1}; {"criterion": "gini", "max_depth": null, "min_samples_leaf": 1}; {"criterion": "gini", "max_depth": null, "min_samples_leaf": 1}; {"criterion": "gini", "max_depth": null, "min_samples_leaf": 10}
* 1-D CNN: {"channels": [16, 32], "dropout": 0.5, "epochs": 100, "learning_rate": 0.003}; {"channels": [32, 64], "dropout": 0.2, "epochs": 100, "learning_rate": 0.003}; {"channels": [32, 64], "dropout": 0.5, "epochs": 50, "learning_rate": 0.001}; {"channels": [32, 64], "dropout": 0.5, "epochs": 50, "learning_rate": 0.001}; {"channels": [32, 64], "dropout": 0.5, "epochs": 100, "learning_rate": 0.003}
* Raw-traffic CNN: {"dropout": 0.5, "learning_rate": 0.003, "max_len": 32768}; {"dropout": 0.5, "learning_rate": 0.003, "max_len": 32768}; {"dropout": 0.2, "learning_rate": 0.003, "max_len": 8192}; {"dropout": 0.5, "learning_rate": 0.003, "max_len": 8192}; {"dropout": 0.5, "learning_rate": 0.003, "max_len": 8192}

## 5c. Benign-only anomaly detection (task-grouped, no attack data used)
Fitted on benign sessions of the training tasks only; threshold = 0.95 quantile of their anomaly scores (target FPR about 5%). No attack data used for fitting or thresholds.

| Detector | Precision | Recall [95 % CI] | F1 [95 % CI] | FPR [95 % CI] | Recall poisoned_tool | Recall sampling_injection | Recall shadowing |
|---|---|---|---|---|---|---|---|
| Isolation Forest | 0.364 | 0.119 [0.02, 0.42] | 0.180 [0.03, 0.42] | 0.061 [0.03, 0.10] | 0.36 | 0.00 | 0.00 |
| One-Class SVM | 0.537 | 0.953 [0.84, 0.99] | 0.687 [0.32, 0.83] | 0.241 [0.13, 0.36] | 0.86 | 1.00 | 1.00 |

Intervals: task-cluster bootstrap (see the headline). A benign-only detector flags what is *unusual*, not what is malicious: on a closed-world lab dataset, unfamiliar benign tasks can look as unusual as attacks.

## 6. Most important Random Forest features (impurity-based)

| Feature | Category | Importance |
|---|---|---|
| `desc_len_std` | content | 0.337 |
| `max_desc_param_ratio` | content | 0.149 |
| `tool_name_mentions` | content | 0.090 |
| `desc_words_total` | content | 0.080 |
| `desc_len_mean` | content | 0.059 |
| `tools_call_req_size_mean` | structural | 0.034 |
| `n_distinct_method_bigrams` | behavioral | 0.029 |
| `tools_call_req_size_max` | structural | 0.025 |
| `model_address_count` | content | 0.024 |
| `second_person_count` | content | 0.023 |

Plot: `feature_importance_rf.png`

## 6a. Most important XGBoost features (share of total gain)

| Feature | Category | Importance |
|---|---|---|
| `desc_len_std` | content | 0.584 |
| `desc_words_total` | content | 0.201 |
| `param_desc_len_mean` | content | 0.122 |
| `tool_name_mentions` | content | 0.026 |
| `n_distinct_method_bigrams` | behavioral | 0.023 |
| `size_max` | structural | 0.014 |
| `model_address_count` | content | 0.005 |
| `tools_call_resp_size_mean` | structural | 0.004 |
| `desc_len_max` | content | 0.004 |
| `max_desc_param_ratio` | content | 0.003 |

Plot: `feature_importance_xgb.png`

## 7. Interpretation and limitations
* **Closed-world benign metadata.** Benign servers advertise fixed tool descriptions in this lab, so *any* change to `tools/list` (size, wording) can separate the classes. Several single features do so perfectly on this data (see docs/ml.md). High scores here mostly reflect this; they do not show that the detector would work on real, varied MCP servers.
* **Small, controlled sample.** Repeated scenario seeds do not create independent server implementations or attack designs. Results are proof of concept, not real-world validation.
* **Template and author bias.** Benign descriptions are fixed and payload templates were written by the same project team; richer benign variation is needed.
* **Mock-agent limitation.** Obedience is simulated. Sampling success means the protocol exchange completed, not that an LLM was influenced.
* **Lexicon bias.** Content lexicons were written by people who knew the payloads.
* **No model ranking.** Differences between the models (Random Forest, SVM (RBF), XGBoost, RF + XGBoost (soft vote), Decision Tree, 1-D CNN, Raw-traffic CNN) are within what a different split could change and inside each other's task-bootstrap intervals; no statistical test supports calling one of them better. The ensemble cannot recover information that neither member has: an attack family missing from training stays missed.
