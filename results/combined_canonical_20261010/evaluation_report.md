# Evaluation report: exp_017_combined_canonical_20261010

> **This experiment demonstrates the functionality of the ML pipeline, but the dataset is too small to establish strong real-world generalization.**

## Setup
* Dataset: `/lab/data/combined_canonical_20261010` (read-only), SHA-256 `011239eb29cfd235...`
* Sessions: 2220 (1860 benign, 360 attack across poisoned_tool, sampling_injection, shadowing); protocol/mock success count (not real LLM influence): 213
* Features: 65 ({'structural': 26, 'behavioral': 19, 'content': 20}); lab marker/canary removed with `neutralize()`
* Split: task-grouped (whole tasks held out: 28 training / 14 test tasks), seed 42, test size 0.3 → train 1540 (1240 benign / 300 attack), test 680 (620 benign / 60 attack)
* Positive class: `attack` = attack **attempted** (not success)

## Headline: task-grouped cross-validation with 95 % confidence intervals (hyperparameters tuned, nested)
Protocol: nested task-grouped cross-validation (GroupKFold(n_splits=5) on task_id, 42 tasks; hyperparameters tuned inside each outer training fold); no task is in both train and test, so seed-level near-duplicates cannot be memorised; the held-out tasks never influence the chosen settings. **Quote these numbers**, not the single split in section 2.

| Model | F1 [95 % CI] | Precision [95 % CI] | Recall [95 % CI] | FPR [95 % CI] | Recall poisoned_tool | Recall sampling_injection | Recall shadowing | Baseline-split F1 | Untuned F1 |
|---|---|---|---|---|---|---|---|---|---|
| Random Forest | 0.710 [0.33, 1.00] | 1.000 [1.00, 1.00] | 0.550 [0.20, 1.00] | 0.000 [0.00, 0.00] | 1.00 | 0.00 | 0.65 | 1.000 | 0.710 |
| SVM (RBF) | 0.730 [0.26, 0.99] | 0.805 [0.34, 1.00] | 0.667 [0.20, 1.00] | 0.031 [0.00, 0.10] | 1.00 | 0.00 | 1.00 | 0.394 | 0.789 |
| XGBoost | 0.791 [0.33, 1.00] | 0.972 [0.82, 1.00] | 0.667 [0.20, 1.00] | 0.004 [0.00, 0.01] | 1.00 | 0.00 | 1.00 | 1.000 | 0.795 |
| RF + XGBoost (soft vote) | 0.796 [0.33, 1.00] | 0.988 [0.91, 1.00] | 0.667 [0.20, 1.00] | 0.002 [0.00, 0.01] | 1.00 | 0.00 | 1.00 | 1.000 | 0.795 |
| Decision Tree | 0.789 [0.33, 1.00] | 0.968 [0.81, 1.00] | 0.667 [0.20, 1.00] | 0.004 [0.00, 0.01] | 1.00 | 0.00 | 1.00 | 0.889 | 0.797 |
| 1-D CNN | 0.704 [0.24, 0.98] | 0.763 [0.28, 0.99] | 0.653 [0.20, 1.00] | 0.039 [0.00, 0.11] | 0.96 | 0.00 | 1.00 | 0.593 | 0.725 |
| Raw-traffic CNN | 0.377 [0.00, 0.88] | 0.763 [0.00, 1.00] | 0.250 [0.00, 1.00] | 0.015 [0.00, 0.05] | 0.75 | 0.00 | 0.00 | 0.870 | 0.500 |

Intervals: task-cluster bootstrap, 2000 resamples of 42 groups (valid resamples: 1995). Sessions of one task are not independent, so whole tasks are resampled; with few tasks the intervals are wide. Per-session Wilson intervals, which ignore that dependence, are narrower (Random Forest recall [0.50, 0.60], FPR [0.00, 0.00]) and are stored in `metrics.json` for every model.

## 1. Baseline split: TRAINING metrics (not evidence of generalization)
| Model | Accuracy | Precision | Recall | F1 | FPR | Latency |
|---|---|---|---|---|---|---|
| Random Forest | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| SVM (RBF) | 0.997 | 0.984 | 1.000 | 0.992 | 0.004 | - |
| XGBoost | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| RF + XGBoost (soft vote) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| Decision Tree | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| 1-D CNN | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| Raw-traffic CNN | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |

## 2. Baseline split: TEST metrics (task-grouped split; one split only, see the headline above)
| Model | Accuracy | Precision | Recall | F1 | FPR | Latency (model only, median) |
|---|---|---|---|---|---|---|
| Random Forest | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 16.13 ms |
| SVM (RBF) | 0.887 | 0.373 | 0.417 | 0.394 | 0.068 | 1.62 ms |
| XGBoost | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 2.08 ms |
| RF + XGBoost (soft vote) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 20.11 ms |
| Decision Tree | 0.982 | 1.000 | 0.800 | 0.889 | 0.000 | 1.43 ms |
| 1-D CNN | 0.929 | 0.603 | 0.583 | 0.593 | 0.037 | 1.90 ms |
| Raw-traffic CNN | 0.974 | 0.769 | 1.000 | 0.870 | 0.029 | 5.11 ms |

Confusion matrices (test): `confusion_matrix_rf.png`, `confusion_matrix_svm.png`, `confusion_matrix_xgb.png`, `confusion_matrix_rf_xgb.png`, `confusion_matrix_dt.png`, `confusion_matrix_cnn.png`, `confusion_matrix_cnn_raw.png`

* Random Forest: TN=620 FP=0 FN=0 TP=60; end-to-end latency (read logs + features + model) median 37.0 ms; recall on attacks that succeeded 1.0 (n=26), that did not succeed 1.0 (n=34)
* SVM (RBF): TN=578 FP=42 FN=35 TP=25; end-to-end latency (read logs + features + model) median 7.0 ms; recall on attacks that succeeded 0.5 (n=26), that did not succeed 0.3529 (n=34)
* XGBoost: TN=620 FP=0 FN=0 TP=60; end-to-end latency (read logs + features + model) median 8.8 ms; recall on attacks that succeeded 1.0 (n=26), that did not succeed 1.0 (n=34)
* RF + XGBoost (soft vote): TN=620 FP=0 FN=0 TP=60; end-to-end latency (read logs + features + model) median 44.1 ms; recall on attacks that succeeded 1.0 (n=26), that did not succeed 1.0 (n=34)
* Decision Tree: TN=620 FP=0 FN=12 TP=48; end-to-end latency (read logs + features + model) median 6.1 ms; recall on attacks that succeeded 0.8077 (n=26), that did not succeed 0.7941 (n=34)
* 1-D CNN: TN=597 FP=23 FN=25 TP=35; end-to-end latency (read logs + features + model) median 7.4 ms; recall on attacks that succeeded 0.6154 (n=26), that did not succeed 0.5588 (n=34)
* Raw-traffic CNN: TN=602 FP=18 FN=0 TP=60; end-to-end latency (read logs + features + model) median 12.9 ms; recall on attacks that succeeded 1.0 (n=26), that did not succeed 1.0 (n=34)

Per payload style in the test set (n is tiny):

| Style | n | RF recall | SVM recall | XGB recall | RF+XGB recall | DT recall | CNN recall | Raw CNN recall |
|---|---|---|---|---|---|---|---|---|
| overt | 12 | 1.00 | 0.00 | 1.00 | 1.00 | 1.00 | 0.00 | 1.00 |
| padded | 12 | 1.00 | 1.00 | 1.00 | 1.00 | 0.50 | 1.00 | 1.00 |
| param | 12 | 1.00 | 0.08 | 1.00 | 1.00 | 1.00 | 0.92 | 1.00 |
| polite | 12 | 1.00 | 0.00 | 1.00 | 1.00 | 0.50 | 0.00 | 1.00 |
| tagged | 12 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

## 3. Hold-one-payload-style-out (generalization to an unseen style)
Train: benign-train + attacks of the other 4 styles. Test: benign-test + all attacks of the held-out style. Payload-style holdout, NOT a family holdout. Benign train/test: 1240/620.

**This is a payload-style holdout within `poisoned_tool`, not the family holdout.** The three-family experiment follows below.

| Held-out poisoned-tool style | test attacks | Model | Recall | FPR | F1 |
|---|---:|---|---:|---:|---:|
| overt | 24 | Random Forest | 1.00 | 0.00 | 0.98 |
| overt | 24 | SVM (RBF) | 1.00 | 0.01 | 0.91 |
| overt | 24 | XGBoost | 1.00 | 0.01 | 0.89 |
| overt | 24 | RF + XGBoost (soft vote) | 1.00 | 0.01 | 0.89 |
| overt | 24 | Decision Tree | 1.00 | 0.01 | 0.89 |
| overt | 24 | 1-D CNN | 1.00 | 0.00 | 1.00 |
| overt | 24 | Raw-traffic CNN | 1.00 | 0.16 | 0.33 |
| padded | 24 | Random Forest | 0.00 | 0.00 | 0.00 |
| padded | 24 | SVM (RBF) | 0.50 | 0.02 | 0.50 |
| padded | 24 | XGBoost | 0.00 | 0.00 | 0.00 |
| padded | 24 | RF + XGBoost (soft vote) | 0.00 | 0.00 | 0.00 |
| padded | 24 | Decision Tree | 0.00 | 0.01 | 0.00 |
| padded | 24 | 1-D CNN | 1.00 | 0.00 | 1.00 |
| padded | 24 | Raw-traffic CNN | 0.00 | 0.16 | 0.00 |
| param | 24 | Random Forest | 0.00 | 0.00 | 0.00 |
| param | 24 | SVM (RBF) | 0.46 | 0.03 | 0.39 |
| param | 24 | XGBoost | 0.00 | 0.00 | 0.00 |
| param | 24 | RF + XGBoost (soft vote) | 0.00 | 0.00 | 0.00 |
| param | 24 | Decision Tree | 0.00 | 0.00 | 0.00 |
| param | 24 | 1-D CNN | 0.12 | 0.00 | 0.22 |
| param | 24 | Raw-traffic CNN | 1.00 | 0.13 | 0.38 |
| polite | 24 | Random Forest | 0.00 | 0.00 | 0.00 |
| polite | 24 | SVM (RBF) | 0.96 | 0.00 | 0.96 |
| polite | 24 | XGBoost | 0.00 | 0.00 | 0.00 |
| polite | 24 | RF + XGBoost (soft vote) | 0.00 | 0.00 | 0.00 |
| polite | 24 | Decision Tree | 0.00 | 0.00 | 0.00 |
| polite | 24 | 1-D CNN | 0.58 | 0.00 | 0.74 |
| polite | 24 | Raw-traffic CNN | 1.00 | 0.00 | 1.00 |
| tagged | 24 | Random Forest | 1.00 | 0.00 | 0.98 |
| tagged | 24 | SVM (RBF) | 1.00 | 0.04 | 0.67 |
| tagged | 24 | XGBoost | 1.00 | 0.01 | 0.89 |
| tagged | 24 | RF + XGBoost (soft vote) | 1.00 | 0.01 | 0.89 |
| tagged | 24 | Decision Tree | 1.00 | 0.01 | 0.89 |
| tagged | 24 | 1-D CNN | 1.00 | 0.00 | 1.00 |
| tagged | 24 | Raw-traffic CNN | 0.00 | 0.31 | 0.00 |

## 3a. Hold-one-attack-family-out
For each fold, train on benign training sessions and all other attack families; test on benign test sessions plus the held-out attack family. This is a family holdout.

| Held-out family | test attacks | Model | Recall | FPR | F1 |
|---|---:|---|---:|---:|---:|
| poisoned_tool | 120 | Random Forest | 0.00 | 0.00 | 0.00 |
| poisoned_tool | 120 | SVM (RBF) | 0.00 | 0.03 | 0.00 |
| poisoned_tool | 120 | XGBoost | 0.00 | 0.00 | 0.00 |
| poisoned_tool | 120 | RF + XGBoost (soft vote) | 0.00 | 0.00 | 0.00 |
| poisoned_tool | 120 | Decision Tree | 0.00 | 0.00 | 0.00 |
| poisoned_tool | 120 | 1-D CNN | 0.10 | 0.01 | 0.18 |
| poisoned_tool | 120 | Raw-traffic CNN | 0.20 | 0.14 | 0.21 |
| sampling_injection | 120 | Random Forest | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | SVM (RBF) | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | XGBoost | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | RF + XGBoost (soft vote) | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | Decision Tree | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | 1-D CNN | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | Raw-traffic CNN | 0.00 | 0.01 | 0.00 |
| shadowing | 120 | Random Forest | 1.00 | 0.00 | 1.00 |
| shadowing | 120 | SVM (RBF) | 1.00 | 0.08 | 0.83 |
| shadowing | 120 | XGBoost | 1.00 | 0.00 | 1.00 |
| shadowing | 120 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| shadowing | 120 | Decision Tree | 1.00 | 0.00 | 1.00 |
| shadowing | 120 | 1-D CNN | 1.00 | 0.01 | 0.97 |
| shadowing | 120 | Raw-traffic CNN | 0.00 | 0.15 | 0.00 |

## 4. Feature-group ablation (same split, test set)
| Features | # | Model | Recall | FPR | F1 |
|---|---:|---|---:|---:|---:|
| all | 65 | Random Forest | 1.00 | 0.00 | 1.00 |
| all | 65 | SVM (RBF) | 0.42 | 0.07 | 0.39 |
| all | 65 | XGBoost | 1.00 | 0.00 | 1.00 |
| all | 65 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| all | 65 | Decision Tree | 0.80 | 0.00 | 0.89 |
| all | 65 | 1-D CNN | 0.58 | 0.04 | 0.59 |
| structural | 26 | Random Forest | 0.33 | 0.00 | 0.50 |
| structural | 26 | SVM (RBF) | 0.55 | 0.29 | 0.24 |
| structural | 26 | XGBoost | 0.50 | 0.00 | 0.67 |
| structural | 26 | RF + XGBoost (soft vote) | 0.50 | 0.00 | 0.67 |
| structural | 26 | Decision Tree | 0.37 | 0.00 | 0.54 |
| structural | 26 | 1-D CNN | 0.02 | 0.02 | 0.03 |
| behavioral | 19 | Random Forest | 0.18 | 0.20 | 0.11 |
| behavioral | 19 | SVM (RBF) | 0.00 | 0.15 | 0.00 |
| behavioral | 19 | XGBoost | 0.18 | 0.20 | 0.11 |
| behavioral | 19 | RF + XGBoost (soft vote) | 0.18 | 0.20 | 0.11 |
| behavioral | 19 | Decision Tree | 0.18 | 0.23 | 0.10 |
| behavioral | 19 | 1-D CNN | 0.18 | 0.21 | 0.11 |
| content | 20 | Random Forest | 1.00 | 0.00 | 1.00 |
| content | 20 | SVM (RBF) | 0.80 | 0.00 | 0.89 |
| content | 20 | XGBoost | 1.00 | 0.00 | 1.00 |
| content | 20 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| content | 20 | Decision Tree | 0.80 | 0.00 | 0.89 |
| content | 20 | 1-D CNN | 1.00 | 0.00 | 1.00 |
| structural+behavioral | 45 | Random Forest | 0.12 | 0.00 | 0.21 |
| structural+behavioral | 45 | SVM (RBF) | 0.25 | 0.13 | 0.19 |
| structural+behavioral | 45 | XGBoost | 0.60 | 0.00 | 0.75 |
| structural+behavioral | 45 | RF + XGBoost (soft vote) | 0.45 | 0.00 | 0.62 |
| structural+behavioral | 45 | Decision Tree | 0.12 | 0.00 | 0.20 |
| structural+behavioral | 45 | 1-D CNN | 0.00 | 0.08 | 0.00 |

**Confound check:** a Random Forest that sees only `n_servers_mounted` reaches accuracy 0.51, recall 0.50, FPR 0.49 on the test set (majority-class accuracy would be 0.91). Server-count distributions are matched by construction in this Phase 9 dataset.

## 5. Supplementary: RepeatedStratifiedKFold(n_splits=5, n_repeats=5) on all 2220 sessions
| Model | Accuracy | Precision | Recall | F1 | FPR |
|---|---|---|---|---|---|
| Random Forest | 0.999 ± 0.001 | 0.995 ± 0.008 | 1.000 ± 0.000 | 0.997 ± 0.004 | 0.001 ± 0.002 |
| SVM (RBF) | 0.953 ± 0.012 | 0.793 ± 0.042 | 0.968 ± 0.018 | 0.871 ± 0.028 | 0.050 ± 0.013 |
| XGBoost | 0.999 ± 0.001 | 0.995 ± 0.008 | 1.000 ± 0.000 | 0.998 ± 0.004 | 0.001 ± 0.002 |
| RF + XGBoost (soft vote) | 0.999 ± 0.001 | 0.995 ± 0.008 | 1.000 ± 0.000 | 0.998 ± 0.004 | 0.001 ± 0.002 |
| Decision Tree | 0.999 ± 0.001 | 0.995 ± 0.008 | 1.000 ± 0.000 | 0.997 ± 0.004 | 0.001 ± 0.002 |
| 1-D CNN | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.000 ± 0.000 |

## 5a. Baseline duplicate check
19 of 680 baseline test sessions have an **exact feature-vector copy** in the training set (by group: {'benign': 19}). The dataset has 1515 distinct feature vectors among 2220 sessions. Few or no exact copies: the baseline split is not dominated by memorised sessions (near-duplicates can still exist; compare with the task-grouped results below).

## 5b. Task-grouped CV (more honest generalization estimate)
GroupKFold(n_splits=5) on task_id over 42 tasks: no task is in both train and test; every session is predicted out-of-fold and metrics are pooled.

| Model | Accuracy | Precision | Recall | F1 | FPR | Recall poisoned_tool | Recall sampling_injection | Recall shadowing |
|---|---|---|---|---|---|---|---|---|
| Random Forest | 0.927 | 1.000 | 0.550 | 0.710 | 0.000 | 1.00 | 0.00 | 0.65 |
| SVM (RBF) | 0.943 | 0.992 | 0.656 | 0.789 | 0.001 | 0.97 | 0.00 | 1.00 |
| XGBoost | 0.944 | 0.984 | 0.667 | 0.795 | 0.002 | 1.00 | 0.00 | 1.00 |
| RF + XGBoost (soft vote) | 0.944 | 0.984 | 0.667 | 0.795 | 0.002 | 1.00 | 0.00 | 1.00 |
| Decision Tree | 0.945 | 0.992 | 0.667 | 0.797 | 0.001 | 1.00 | 0.00 | 1.00 |
| 1-D CNN | 0.921 | 0.829 | 0.644 | 0.725 | 0.026 | 0.93 | 0.00 | 1.00 |
| Raw-traffic CNN | 0.892 | 1.000 | 0.333 | 0.500 | 0.000 | 1.00 | 0.00 | 0.00 |

Folds (held-out tasks): 1: db_add_log, fs_shadowing_probe, helpdesk_order_reply, multi_news_growth, web_docs_tour, web_faq_long, web_products_list (444 sessions); 2: fs_copy_notes, fs_json_summary, fs_sampling_probe, fs_summarize_notes, multi_db_report, multi_db_to_csv, web_about_team, web_getting_started (448 sessions); 3: calc_unit_report, db_country_counts, db_new_order, db_top_products, fs_search_reports, multi_news_to_file, multi_notes_to_log, multi_order_share (444 sessions); 4: calc_temperature, db_low_stock, db_recent_orders, db_user_lookup, fs_explore_documents, fs_write_todo, multi_price_check, multi_region_share, multi_web_db_prices, web_api_docs (444 sessions); 5: assist_summarize_text, assist_translate_notes, calc_add, db_error_logs, db_order_status, fs_find_data_files, fs_report_digest, helpdesk_triage_ticket, web_news (440 sessions)

## 5b-tuned. Nested task-grouped CV (hyperparameters tuned inside each outer fold)
Nested CV: for each outer fold, hyperparameters are searched on the outer training tasks only (inner GroupKFold(3) on task_id, pooled out-of-fold F1; ml/tuning.py), then the model is refitted with the winner and predicts the held-out tasks.

| Model | Precision | Recall | F1 | FPR | Recall poisoned_tool | Recall sampling_injection | Recall shadowing | Untuned F1 (5b) |
|---|---|---|---|---|---|---|---|---|
| Random Forest | 1.000 | 0.550 | 0.710 | 0.000 | 1.00 | 0.00 | 0.65 | 0.710 |
| SVM (RBF) | 0.805 | 0.667 | 0.730 | 0.031 | 1.00 | 0.00 | 1.00 | 0.789 |
| XGBoost | 0.972 | 0.667 | 0.791 | 0.004 | 1.00 | 0.00 | 1.00 | 0.795 |
| RF + XGBoost (soft vote) | 0.988 | 0.667 | 0.796 | 0.002 | 1.00 | 0.00 | 1.00 | 0.795 |
| Decision Tree | 0.968 | 0.667 | 0.789 | 0.004 | 1.00 | 0.00 | 1.00 | 0.797 |
| 1-D CNN | 0.763 | 0.653 | 0.704 | 0.039 | 0.96 | 0.00 | 1.00 | 0.725 |
| Raw-traffic CNN | 0.763 | 0.250 | 0.377 | 0.015 | 0.75 | 0.00 | 0.00 | 0.500 |

Settings chosen in each outer fold (fold 1 ... 5):

* Random Forest: {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 300}; {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 300}; {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 600}; {"max_depth": null, "max_features": 0.5, "min_samples_leaf": 1, "n_estimators": 300}; {"max_depth": null, "max_features": 0.5, "min_samples_leaf": 1, "n_estimators": 300}
* SVM (RBF): {"C": 10.0, "gamma": 0.01}; {"C": 1.0, "gamma": 0.01}; {"C": 10.0, "gamma": 0.01}; {"C": 10.0, "gamma": 0.01}; {"C": 100.0, "gamma": 0.001}
* XGBoost: {"learning_rate": 0.03, "max_depth": 6, "n_estimators": 100, "subsample": 0.8}; {"learning_rate": 0.3, "max_depth": 3, "n_estimators": 300, "subsample": 1.0}; {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 300, "subsample": 1.0}; {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 300, "subsample": 1.0}; {"learning_rate": 0.03, "max_depth": 6, "n_estimators": 100, "subsample": 1.0}
* RF + XGBoost (soft vote): {"random_forest": {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 300}, "xgboost": {"learning_rate": 0.03, "max_depth": 6, "n_estimators": 100, "subsample": 0.8}}; {"random_forest": {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 300}, "xgboost": {"learning_rate": 0.3, "max_depth": 3, "n_estimators": 300, "subsample": 1.0}}; {"random_forest": {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 600}, "xgboost": {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 300, "subsample": 1.0}}; {"random_forest": {"max_depth": null, "max_features": 0.5, "min_samples_leaf": 1, "n_estimators": 300}, "xgboost": {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 300, "subsample": 1.0}}; {"random_forest": {"max_depth": null, "max_features": 0.5, "min_samples_leaf": 1, "n_estimators": 300}, "xgboost": {"learning_rate": 0.03, "max_depth": 6, "n_estimators": 100, "subsample": 1.0}}
* Decision Tree: {"criterion": "gini", "max_depth": null, "min_samples_leaf": 10}; {"criterion": "gini", "max_depth": null, "min_samples_leaf": 1}; {"criterion": "gini", "max_depth": null, "min_samples_leaf": 1}; {"criterion": "gini", "max_depth": null, "min_samples_leaf": 1}; {"criterion": "gini", "max_depth": null, "min_samples_leaf": 1}
* 1-D CNN: {"channels": [16, 32], "dropout": 0.5, "epochs": 100, "learning_rate": 0.003}; {"channels": [32, 64], "dropout": 0.2, "epochs": 50, "learning_rate": 0.003}; {"channels": [16, 32], "dropout": 0.5, "epochs": 100, "learning_rate": 0.003}; {"channels": [32, 64], "dropout": 0.2, "epochs": 100, "learning_rate": 0.003}; {"channels": [32, 64], "dropout": 0.2, "epochs": 50, "learning_rate": 0.003}
* Raw-traffic CNN: {"dropout": 0.2, "learning_rate": 0.003, "max_len": 32768}; {"dropout": 0.2, "learning_rate": 0.001, "max_len": 8192}; {"dropout": 0.5, "learning_rate": 0.003, "max_len": 32768}; {"dropout": 0.5, "learning_rate": 0.001, "max_len": 32768}; {"dropout": 0.5, "learning_rate": 0.003, "max_len": 32768}

## 5c. Benign-only anomaly detection (task-grouped, no attack data used)
Fitted on benign sessions of the training tasks only; threshold = 0.95 quantile of their anomaly scores (target FPR about 5%). No attack data used for fitting or thresholds.

| Detector | Precision | Recall [95 % CI] | F1 [95 % CI] | FPR [95 % CI] | Recall poisoned_tool | Recall sampling_injection | Recall shadowing |
|---|---|---|---|---|---|---|---|
| Isolation Forest | 0.252 | 0.114 [0.02, 0.38] | 0.157 [0.03, 0.35] | 0.066 [0.03, 0.11] | 0.34 | 0.00 | 0.00 |
| One-Class SVM | 0.406 | 0.789 [0.57, 0.98] | 0.536 [0.23, 0.75] | 0.224 [0.11, 0.36] | 0.87 | 0.50 | 1.00 |

Intervals: task-cluster bootstrap (see the headline). A benign-only detector flags what is *unusual*, not what is malicious: on a closed-world lab dataset, unfamiliar benign tasks can look as unusual as attacks.

## 6. Most important Random Forest features (impurity-based)

| Feature | Category | Importance |
|---|---|---|
| `desc_len_std` | content | 0.377 |
| `max_desc_param_ratio` | content | 0.171 |
| `tools_call_req_size_mean` | structural | 0.061 |
| `desc_words_total` | content | 0.058 |
| `tool_name_mentions` | content | 0.055 |
| `desc_len_mean` | content | 0.038 |
| `model_address_count` | content | 0.036 |
| `second_person_count` | content | 0.032 |
| `tools_call_req_size_max` | structural | 0.024 |
| `n_distinct_method_bigrams` | behavioral | 0.018 |

Plot: `feature_importance_rf.png`

## 6a. Most important XGBoost features (share of total gain)

| Feature | Category | Importance |
|---|---|---|
| `desc_len_std` | content | 0.505 |
| `desc_words_total` | content | 0.282 |
| `param_desc_len_mean` | content | 0.083 |
| `tools_call_resp_size_max` | structural | 0.032 |
| `size_max` | structural | 0.015 |
| `second_person_count` | content | 0.013 |
| `n_distinct_method_bigrams` | behavioral | 0.013 |
| `max_desc_param_ratio` | content | 0.011 |
| `tool_name_mentions` | content | 0.010 |
| `tools_list_resp_size_max` | structural | 0.010 |

Plot: `feature_importance_xgb.png`

## 7. Interpretation and limitations
* **Closed-world benign metadata.** Benign servers advertise fixed tool descriptions in this lab, so *any* change to `tools/list` (size, wording) can separate the classes. Several single features do so perfectly on this data (see docs/ml.md). High scores here mostly reflect this; they do not show that the detector would work on real, varied MCP servers.
* **Small, controlled sample.** Repeated scenario seeds do not create independent server implementations or attack designs. Results are proof of concept, not real-world validation.
* **Template and author bias.** Benign descriptions are fixed and payload templates were written by the same project team; richer benign variation is needed.
* **Mock-agent limitation.** Obedience is simulated. Sampling success means the protocol exchange completed, not that an LLM was influenced.
* **Lexicon bias.** Content lexicons were written by people who knew the payloads.
* **No model ranking.** Differences between the models (Random Forest, SVM (RBF), XGBoost, RF + XGBoost (soft vote), Decision Tree, 1-D CNN, Raw-traffic CNN) are within what a different split could change and inside each other's task-bootstrap intervals; no statistical test supports calling one of them better. The ensemble cannot recover information that neither member has: an attack family missing from training stays missed.
