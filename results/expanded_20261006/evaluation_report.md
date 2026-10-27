# Evaluation report: exp_006_expanded_20261006

> **This experiment demonstrates the functionality of the ML pipeline, but the dataset is too small to establish strong real-world generalization.**

## Setup
* Dataset: `/lab/data/combined_expanded_20261006` (read-only), SHA-256 `9ebcbb7d31a2445c...`
* Sessions: 1354 (994 benign, 360 attack across poisoned_tool, sampling_injection, shadowing); protocol/mock success count (not real LLM influence): 213
* Features: 65 ({'structural': 26, 'behavioral': 19, 'content': 20}); lab marker/canary removed with `neutralize()`
* Split: stratified, seed 42, test size 0.3 → train 947 (695 benign / 252 attack), test 407 (299 benign / 108 attack)
* Positive class: `attack` = attack **attempted** (not success)

## Headline: task-grouped cross-validation with 95 % confidence intervals
Protocol: task-grouped cross-validation (GroupKFold(n_splits=5) on task_id, 38 tasks); no task is in both train and test, so seed-level near-duplicates cannot be memorised. **Quote these numbers**, not the random split in section 2.

| Model | F1 [95 % CI] | Precision [95 % CI] | Recall [95 % CI] | FPR [95 % CI] | Recall poisoned_tool | Recall sampling_injection | Recall shadowing | Random-split F1 |
|---|---|---|---|---|---|---|---|---|
| Random Forest | 0.780 [0.31, 1.00] | 1.000 [1.00, 1.00] | 0.639 [0.18, 1.00] | 0.000 [0.00, 0.00] | 0.92 | 0.00 | 1.00 | 1.000 |
| SVM (RBF) | 0.759 [0.28, 0.99] | 1.000 [1.00, 1.00] | 0.611 [0.17, 0.98] | 0.000 [0.00, 0.00] | 0.83 | 0.00 | 1.00 | 1.000 |
| XGBoost | 0.800 [0.33, 1.00] | 1.000 [1.00, 1.00] | 0.667 [0.20, 1.00] | 0.000 [0.00, 0.00] | 1.00 | 0.00 | 1.00 | 1.000 |
| RF + XGBoost (soft vote) | 0.800 [0.33, 1.00] | 1.000 [1.00, 1.00] | 0.667 [0.20, 1.00] | 0.000 [0.00, 0.00] | 1.00 | 0.00 | 1.00 | 1.000 |

Intervals: task-cluster bootstrap, 2000 resamples of 38 groups (valid resamples: 1995). Sessions of one task are not independent, so whole tasks are resampled; with few tasks the intervals are wide. Per-session Wilson intervals, which ignore that dependence, are narrower (Random Forest recall [0.59, 0.69], FPR [0.00, 0.00]) and are stored in `metrics.json` for every model.

## 1. Baseline split: TRAINING metrics (not evidence of generalization)
| Model | Accuracy | Precision | Recall | F1 | FPR | Latency |
|---|---|---|---|---|---|---|
| Random Forest | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| SVM (RBF) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| XGBoost | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| RF + XGBoost (soft vote) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |

## 2. Baseline split: TEST metrics (random split; for comparison only, see the headline above)
| Model | Accuracy | Precision | Recall | F1 | FPR | Latency (model only, median) |
|---|---|---|---|---|---|---|
| Random Forest | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 27.70 ms |
| SVM (RBF) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 3.47 ms |
| XGBoost | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 3.95 ms |
| RF + XGBoost (soft vote) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 29.68 ms |

Confusion matrices (test): `confusion_matrix_rf.png`, `confusion_matrix_svm.png`, `confusion_matrix_xgb.png`, `confusion_matrix_rf_xgb.png`

* Random Forest: TN=299 FP=0 FN=0 TP=108; end-to-end latency (read logs + features + model) median 146.1 ms; recall on attacks that succeeded 1.0 (n=61), that did not succeed 1.0 (n=47)
* SVM (RBF): TN=299 FP=0 FN=0 TP=108; end-to-end latency (read logs + features + model) median 64.5 ms; recall on attacks that succeeded 1.0 (n=61), that did not succeed 1.0 (n=47)
* XGBoost: TN=299 FP=0 FN=0 TP=108; end-to-end latency (read logs + features + model) median 73.8 ms; recall on attacks that succeeded 1.0 (n=61), that did not succeed 1.0 (n=47)
* RF + XGBoost (soft vote): TN=299 FP=0 FN=0 TP=108; end-to-end latency (read logs + features + model) median 122.8 ms; recall on attacks that succeeded 1.0 (n=61), that did not succeed 1.0 (n=47)

Per payload style in the test set (n is tiny):

| Style | n | RF recall | SVM recall | XGB recall | RF+XGB recall |
|---|---|---|---|---|---|
| overt | 10 | 1.00 | 1.00 | 1.00 | 1.00 |
| padded | 7 | 1.00 | 1.00 | 1.00 | 1.00 |
| param | 5 | 1.00 | 1.00 | 1.00 | 1.00 |
| polite | 6 | 1.00 | 1.00 | 1.00 | 1.00 |
| tagged | 8 | 1.00 | 1.00 | 1.00 | 1.00 |

## 3. Hold-one-payload-style-out (generalization to an unseen style)
Train: benign-train + attacks of the other 4 styles. Test: benign-test + all attacks of the held-out style. Payload-style holdout, NOT a family holdout. Benign train/test: 695/299.

**This is a payload-style holdout within `poisoned_tool`, not the family holdout.** The three-family experiment follows below.

| Held-out poisoned-tool style | test attacks | Model | Recall | FPR | F1 |
|---|---:|---|---:|---:|---:|
| overt | 24 | Random Forest | 1.00 | 0.00 | 1.00 |
| overt | 24 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| overt | 24 | XGBoost | 1.00 | 0.00 | 1.00 |
| overt | 24 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| padded | 24 | Random Forest | 0.50 | 0.00 | 0.67 |
| padded | 24 | SVM (RBF) | 0.00 | 0.00 | 0.00 |
| padded | 24 | XGBoost | 0.00 | 0.00 | 0.00 |
| padded | 24 | RF + XGBoost (soft vote) | 0.00 | 0.00 | 0.00 |
| param | 24 | Random Forest | 0.00 | 0.00 | 0.00 |
| param | 24 | SVM (RBF) | 0.00 | 0.00 | 0.00 |
| param | 24 | XGBoost | 0.00 | 0.00 | 0.00 |
| param | 24 | RF + XGBoost (soft vote) | 0.00 | 0.00 | 0.00 |
| polite | 24 | Random Forest | 1.00 | 0.00 | 1.00 |
| polite | 24 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| polite | 24 | XGBoost | 0.00 | 0.00 | 0.00 |
| polite | 24 | RF + XGBoost (soft vote) | 0.00 | 0.00 | 0.00 |
| tagged | 24 | Random Forest | 1.00 | 0.00 | 1.00 |
| tagged | 24 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| tagged | 24 | XGBoost | 1.00 | 0.00 | 1.00 |
| tagged | 24 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |

## 3a. Hold-one-attack-family-out
For each fold, train on benign training sessions and all other attack families; test on benign test sessions plus the held-out attack family. This is a family holdout.

| Held-out family | test attacks | Model | Recall | FPR | F1 |
|---|---:|---|---:|---:|---:|
| poisoned_tool | 120 | Random Forest | 0.00 | 0.00 | 0.00 |
| poisoned_tool | 120 | SVM (RBF) | 0.00 | 0.00 | 0.00 |
| poisoned_tool | 120 | XGBoost | 0.00 | 0.00 | 0.00 |
| poisoned_tool | 120 | RF + XGBoost (soft vote) | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | Random Forest | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | SVM (RBF) | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | XGBoost | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | RF + XGBoost (soft vote) | 0.00 | 0.00 | 0.00 |
| shadowing | 120 | Random Forest | 0.65 | 0.00 | 0.79 |
| shadowing | 120 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| shadowing | 120 | XGBoost | 1.00 | 0.00 | 1.00 |
| shadowing | 120 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |

## 4. Feature-group ablation (same split, test set)
| Features | # | Model | Recall | FPR | F1 |
|---|---:|---|---:|---:|---:|
| all | 65 | Random Forest | 1.00 | 0.00 | 1.00 |
| all | 65 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| all | 65 | XGBoost | 1.00 | 0.00 | 1.00 |
| all | 65 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| structural | 26 | Random Forest | 1.00 | 0.00 | 1.00 |
| structural | 26 | SVM (RBF) | 0.86 | 0.32 | 0.63 |
| structural | 26 | XGBoost | 0.99 | 0.00 | 0.99 |
| structural | 26 | RF + XGBoost (soft vote) | 0.99 | 0.00 | 0.99 |
| behavioral | 19 | Random Forest | 0.65 | 0.22 | 0.57 |
| behavioral | 19 | SVM (RBF) | 0.64 | 0.19 | 0.59 |
| behavioral | 19 | XGBoost | 0.64 | 0.19 | 0.59 |
| behavioral | 19 | RF + XGBoost (soft vote) | 0.64 | 0.19 | 0.59 |
| content | 20 | Random Forest | 1.00 | 0.00 | 1.00 |
| content | 20 | SVM (RBF) | 0.83 | 0.06 | 0.83 |
| content | 20 | XGBoost | 1.00 | 0.00 | 1.00 |
| content | 20 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| structural+behavioral | 45 | Random Forest | 0.99 | 0.00 | 0.99 |
| structural+behavioral | 45 | SVM (RBF) | 0.87 | 0.24 | 0.69 |
| structural+behavioral | 45 | XGBoost | 0.97 | 0.00 | 0.98 |
| structural+behavioral | 45 | RF + XGBoost (soft vote) | 0.99 | 0.00 | 0.99 |

**Confound check:** a Random Forest that sees only `n_servers_mounted` reaches accuracy 0.72, recall 0.41, FPR 0.17 on the test set (majority-class accuracy would be 0.73). Server-count distributions are matched by construction in this Phase 9 dataset.

## 5. Supplementary: RepeatedStratifiedKFold(n_splits=5, n_repeats=5) on all 1354 sessions
| Model | Accuracy | Precision | Recall | F1 | FPR |
|---|---|---|---|---|---|
| Random Forest | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.000 ± 0.000 |
| SVM (RBF) | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.000 ± 0.000 |
| XGBoost | 0.999 ± 0.002 | 0.998 ± 0.007 | 1.000 ± 0.000 | 0.999 ± 0.004 | 0.001 ± 0.003 |
| RF + XGBoost (soft vote) | 0.999 ± 0.002 | 0.998 ± 0.007 | 1.000 ± 0.000 | 0.999 ± 0.004 | 0.001 ± 0.003 |

## 5a. Baseline duplicate check
185 of 407 baseline test sessions have an **exact feature-vector copy** in the training set (by group: {'benign': 103, 'poisoned_tool': 10, 'sampling_injection': 36, 'shadowing': 36}). The dataset has 725 distinct feature vectors among 1354 sessions. High baseline scores on such a split largely reflect memorisation; use the task-grouped results below as the generalization estimate.

## 5b. Task-grouped CV (more honest generalization estimate)
GroupKFold(n_splits=5) on task_id over 38 tasks: no task is in both train and test; every session is predicted out-of-fold and metrics are pooled.

| Model | Accuracy | Precision | Recall | F1 | FPR | Recall poisoned_tool | Recall sampling_injection | Recall shadowing |
|---|---|---|---|---|---|---|---|---|
| Random Forest | 0.904 | 1.000 | 0.639 | 0.780 | 0.000 | 0.92 | 0.00 | 1.00 |
| SVM (RBF) | 0.897 | 1.000 | 0.611 | 0.759 | 0.000 | 0.83 | 0.00 | 1.00 |
| XGBoost | 0.911 | 1.000 | 0.667 | 0.800 | 0.000 | 1.00 | 0.00 | 1.00 |
| RF + XGBoost (soft vote) | 0.911 | 1.000 | 0.667 | 0.800 | 0.000 | 1.00 | 0.00 | 1.00 |

Folds (held-out tasks): 1: db_order_status, db_top_products, fs_shadowing_probe, web_news (270 sessions); 2: db_add_log, fs_sampling_probe, multi_news_growth, web_faq_long (270 sessions); 3: db_country_counts, fs_copy_notes, fs_find_data_files, fs_json_summary, fs_search_reports, fs_summarize_notes, fs_write_todo, multi_news_to_file, web_api_docs, web_getting_started (272 sessions); 4: calc_add, calc_temperature, db_low_stock, db_new_order, db_recent_orders, db_user_lookup, multi_db_report, multi_notes_to_log, web_docs_tour, web_products_list (272 sessions); 5: calc_unit_report, db_error_logs, fs_explore_documents, fs_report_digest, multi_db_to_csv, multi_order_share, multi_price_check, multi_region_share, multi_web_db_prices, web_about_team (270 sessions)

## 5c. Benign-only anomaly detection (task-grouped, no attack data used)
Fitted on benign sessions of the training tasks only; threshold = 0.95 quantile of their anomaly scores (target FPR about 5%). No attack data used for fitting or thresholds.

| Detector | Precision | Recall [95 % CI] | F1 [95 % CI] | FPR [95 % CI] | Recall poisoned_tool | Recall sampling_injection | Recall shadowing |
|---|---|---|---|---|---|---|---|
| Isolation Forest | 0.345 | 0.136 [0.02, 0.50] | 0.195 [0.03, 0.45] | 0.094 [0.05, 0.17] | 0.41 | 0.00 | 0.00 |
| One-Class SVM | 0.571 | 0.969 [0.89, 0.99] | 0.719 [0.49, 0.87] | 0.264 [0.10, 0.46] | 0.91 | 1.00 | 1.00 |

Intervals: task-cluster bootstrap (see the headline). A benign-only detector flags what is *unusual*, not what is malicious: on a closed-world lab dataset, unfamiliar benign tasks can look as unusual as attacks.

## 6. Most important Random Forest features (impurity-based)

| Feature | Category | Importance |
|---|---|---|
| `desc_len_std` | content | 0.125 |
| `tool_name_mentions` | content | 0.122 |
| `max_desc_param_ratio` | content | 0.075 |
| `metadata_text_len_max` | content | 0.058 |
| `desc_len_max` | content | 0.052 |
| `desc_len_mean` | content | 0.048 |
| `server_initiated_request_count` | structural | 0.048 |
| `desc_words_max` | content | 0.043 |
| `n_distinct_method_bigrams` | behavioral | 0.041 |
| `model_address_count` | content | 0.030 |

Plot: `feature_importance_rf.png`

## 6a. Most important XGBoost features (share of total gain)

| Feature | Category | Importance |
|---|---|---|
| `desc_len_std` | content | 0.440 |
| `param_desc_len_mean` | content | 0.229 |
| `desc_words_total` | content | 0.195 |
| `server_initiated_request_count` | structural | 0.048 |
| `tool_name_mentions` | content | 0.042 |
| `desc_len_max` | content | 0.018 |
| `size_total` | structural | 0.011 |
| `client_share` | structural | 0.005 |
| `tools_call_resp_size_max` | structural | 0.004 |
| `model_address_count` | content | 0.002 |

Plot: `feature_importance_xgb.png`

## 7. Interpretation and limitations
* **Closed-world benign metadata.** Benign servers advertise fixed tool descriptions in this lab, so *any* change to `tools/list` (size, wording) can separate the classes. Several single features do so perfectly on this data (see docs/ml.md). High scores here mostly reflect this; they do not show that the detector would work on real, varied MCP servers.
* **Small, controlled sample.** Repeated scenario seeds do not create independent server implementations or attack designs. Results are proof of concept, not real-world validation.
* **Template and author bias.** Benign descriptions are fixed and payload templates were written by the same project team; richer benign variation is needed.
* **Mock-agent limitation.** Obedience is simulated. Sampling success means the protocol exchange completed, not that an LLM was influenced.
* **Lexicon bias.** Content lexicons were written by people who knew the payloads.
* **No model ranking.** Differences between the models (RF, SVM, XGBoost, RF + XGBoost) are within what a different split could change and inside each other's task-bootstrap intervals; no statistical test supports calling one of them better. The ensemble cannot recover information that neither member has: an attack family missing from training stays missed.
