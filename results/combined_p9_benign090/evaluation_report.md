# Evaluation report: exp_005_combined_p9_benign090

> **This experiment demonstrates the functionality of the ML pipeline, but the dataset is too small to establish strong real-world generalization.**

## Setup
* Dataset: `/lab/data/combined_p9_benign090` (read-only), SHA-256 `388251d5f768f3bd...`
* Sessions: 814 (724 benign, 90 attack across poisoned_tool, sampling_injection, shadowing); protocol/mock success count (not real LLM influence): 49
* Features: 65 ({'structural': 26, 'behavioral': 19, 'content': 20}); lab marker/canary removed with `neutralize()`
* Split: stratified, seed 42, test size 0.3 → train 569 (506 benign / 63 attack), test 245 (218 benign / 27 attack)
* Positive class: `attack` = attack **attempted** (not success)

## 1. Baseline split: TRAINING metrics (not evidence of generalization)
| Model | Accuracy | Precision | Recall | F1 | FPR | Latency |
|---|---|---|---|---|---|---|
| Random Forest | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| SVM (RBF) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |

## 2. Baseline split: TEST metrics
| Model | Accuracy | Precision | Recall | F1 | FPR | Latency (model only, median) |
|---|---|---|---|---|---|---|
| Random Forest | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 41.91 ms |
| SVM (RBF) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 5.40 ms |

Confusion matrices (test): `confusion_matrix_rf.png`, `confusion_matrix_svm.png`

* Random Forest: TN=218 FP=0 FN=0 TP=27; end-to-end latency (read logs + features + model) median 163.7 ms; recall on attacks that succeeded 1.0 (n=16), that did not succeed 1.0 (n=11)
* SVM: TN=218 FP=0 FN=0 TP=27; end-to-end latency (read logs + features + model) median 95.1 ms; recall on attacks that succeeded 1.0 (n=16), that did not succeed 1.0 (n=11)

Per payload style in the test set (n is tiny):

| Style | n | RF recall | SVM recall |
|---|---|---|---|
| overt | 2 | 1.00 | 1.00 |
| param | 3 | 1.00 | 1.00 |
| polite | 3 | 1.00 | 1.00 |
| tagged | 1 | 1.00 | 1.00 |

## 3. Hold-one-payload-style-out (generalization to an unseen style)
Train: benign-train + attacks of the other 4 styles. Test: benign-test + all attacks of the held-out style. Payload-style holdout, NOT a family holdout. Benign train/test: 506/218.

**This is a payload-style holdout within `poisoned_tool`, not the family holdout.** The three-family experiment follows below.

| Held-out poisoned-tool style | test attacks | RF recall | RF FPR | RF F1 | SVM recall | SVM FPR | SVM F1 |
|---|---|---|---|---|---|---|---|
| overt | 6 | 1.00 | 0.00 | 1.00 | 1.00 | 0.00 | 1.00 |
| padded | 6 | 1.00 | 0.00 | 1.00 | 0.00 | 0.00 | 0.00 |
| param | 6 | 1.00 | 0.00 | 1.00 | 0.83 | 0.00 | 0.91 |
| polite | 6 | 1.00 | 0.00 | 1.00 | 1.00 | 0.00 | 1.00 |
| tagged | 6 | 1.00 | 0.00 | 1.00 | 1.00 | 0.00 | 1.00 |

## 3a. Hold-one-attack-family-out
For each fold, train on benign training sessions and all other attack families; test on benign test sessions plus the held-out attack family. This is a family holdout.

| Held-out family | test attacks | RF recall | RF FPR | RF F1 | SVM recall | SVM FPR | SVM F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| poisoned_tool | 30 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| sampling_injection | 30 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| shadowing | 30 | 0.63 | 0.00 | 0.78 | 1.00 | 0.00 | 1.00 |

## 4. Feature-group ablation (same split, test set)
| Features | # | RF recall | RF FPR | RF F1 | SVM recall | SVM FPR | SVM F1 |
|---|---|---|---|---|---|---|---|
| all | 65 | 1.00 | 0.00 | 1.00 | 1.00 | 0.00 | 1.00 |
| structural | 26 | 1.00 | 0.00 | 1.00 | 0.93 | 0.09 | 0.69 |
| behavioral | 19 | 0.70 | 0.15 | 0.49 | 0.81 | 0.20 | 0.48 |
| content | 20 | 1.00 | 0.00 | 1.00 | 0.74 | 0.01 | 0.80 |
| structural+behavioral | 45 | 1.00 | 0.00 | 1.00 | 0.89 | 0.08 | 0.70 |

**Confound check:** a Random Forest that sees only `n_servers_mounted` reaches accuracy 0.86, recall 0.30, FPR 0.07 on the test set (majority-class accuracy would be 0.89). Server-count distributions are matched by construction in this Phase 9 dataset.

## 5. Supplementary: RepeatedStratifiedKFold(n_splits=5, n_repeats=5) on all 814 sessions
| Model | Accuracy | Precision | Recall | F1 | FPR |
|---|---|---|---|---|---|
| Random Forest | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.000 ± 0.000 |
| SVM (RBF) | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.000 ± 0.000 |

## 5a. Baseline duplicate check
51 of 245 baseline test sessions have an **exact feature-vector copy** in the training set (by group: {'benign': 33, 'sampling_injection': 9, 'shadowing': 9}). The dataset has 637 distinct feature vectors among 814 sessions. Few or no exact copies: the baseline split is not dominated by memorised sessions (near-duplicates can still exist; compare with the task-grouped results below).

## 5b. Task-grouped CV (more honest generalization estimate)
GroupKFold(n_splits=5) on task_id over 38 tasks: no task is in both train and test; every session is predicted out-of-fold and metrics are pooled.

| Model | Accuracy | Precision | Recall | F1 | FPR | Recall poisoned_tool | Recall sampling_injection | Recall shadowing |
|---|---|---|---|---|---|---|---|---|
| Random Forest | 0.950 | 1.000 | 0.544 | 0.705 | 0.000 | 1.00 | 0.00 | 0.63 |
| SVM (RBF) | 0.948 | 0.833 | 0.667 | 0.741 | 0.017 | 1.00 | 0.00 | 1.00 |

Folds (held-out tasks): 1: db_top_products, fs_explore_documents, fs_search_reports, multi_order_share, multi_web_db_prices, web_products_list (162 sessions); 2: db_add_log, db_country_counts, db_low_stock, fs_shadowing_probe, multi_news_growth, multi_region_share, web_faq_long (162 sessions); 3: calc_temperature, calc_unit_report, fs_sampling_probe, fs_summarize_notes, multi_db_to_csv, multi_news_to_file, web_about_team, web_getting_started (164 sessions); 4: db_error_logs, db_new_order, db_recent_orders, db_user_lookup, fs_json_summary, fs_write_todo, multi_db_report, multi_notes_to_log (164 sessions); 5: calc_add, db_order_status, fs_copy_notes, fs_find_data_files, fs_report_digest, multi_price_check, web_api_docs, web_docs_tour, web_news (162 sessions)

## 6. Most important Random Forest features (impurity-based)

| Feature | Category | Importance |
|---|---|---|
| `desc_len_std` | content | 0.154 |
| `max_desc_param_ratio` | content | 0.115 |
| `desc_len_mean` | content | 0.061 |
| `tool_name_mentions` | content | 0.051 |
| `metadata_text_len_max` | content | 0.048 |
| `desc_len_max` | content | 0.048 |
| `server_initiated_request_count` | structural | 0.044 |
| `desc_words_max` | content | 0.042 |
| `tools_call_req_size_mean` | structural | 0.038 |
| `desc_sentences_max` | content | 0.036 |

Plot: `feature_importance_rf.png`

## 7. Interpretation and limitations
* **Closed-world benign metadata.** Benign servers advertise fixed tool descriptions in this lab, so *any* change to `tools/list` (size, wording) can separate the classes. Several single features do so perfectly on this data (see docs/ml.md). High scores here mostly reflect this; they do not show that the detector would work on real, varied MCP servers.
* **Small, controlled sample.** Repeated scenario seeds do not create independent server implementations or attack designs. Results are proof of concept, not real-world validation.
* **Template and author bias.** Benign descriptions are fixed and payload templates were written by the same project team; richer benign variation is needed.
* **Mock-agent limitation.** Obedience is simulated. Sampling success means the protocol exchange completed, not that an LLM was influenced.
* **Lexicon bias.** Content lexicons were written by people who knew the payloads.
* **No model ranking.** Differences between RF and SVM are within what a different split could change; no statistical test supports calling either one better.
