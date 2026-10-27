# Evaluation report: exp_007_phase9_expanded_20261006

> **This experiment demonstrates the functionality of the ML pipeline, but the dataset is too small to establish strong real-world generalization.**

## Setup
* Dataset: `/lab/data/phase9_expanded_20261006` (read-only), SHA-256 `c92b8258343313c8...`
* Sessions: 720 (360 benign, 360 attack across poisoned_tool, sampling_injection, shadowing); protocol/mock success count (not real LLM influence): 213
* Features: 65 ({'structural': 26, 'behavioral': 19, 'content': 20}); lab marker/canary removed with `neutralize()`
* Split: stratified, seed 42, test size 0.3 → train 504 (252 benign / 252 attack), test 216 (108 benign / 108 attack)
* Positive class: `attack` = attack **attempted** (not success)

## Headline: task-grouped cross-validation with 95 % confidence intervals
Protocol: task-grouped cross-validation (GroupKFold(n_splits=5) on task_id, 6 tasks); no task is in both train and test, so seed-level near-duplicates cannot be memorised. **Quote these numbers**, not the random split in section 2.

| Model | F1 [95 % CI] | Precision [95 % CI] | Recall [95 % CI] | FPR [95 % CI] | Recall poisoned_tool | Recall sampling_injection | Recall shadowing | Random-split F1 |
|---|---|---|---|---|---|---|---|---|
| Random Forest | 0.800 [0.33, 1.00] | 1.000 [1.00, 1.00] | 0.667 [0.20, 1.00] | 0.000 [0.00, 0.00] | 1.00 | 0.00 | 1.00 | 1.000 |
| SVM (RBF) | 0.775 [0.33, 1.00] | 0.927 [0.72, 1.00] | 0.667 [0.20, 1.00] | 0.053 [0.00, 0.21] | 1.00 | 0.00 | 1.00 | 1.000 |
| XGBoost | 0.800 [0.33, 1.00] | 1.000 [1.00, 1.00] | 0.667 [0.20, 1.00] | 0.000 [0.00, 0.00] | 1.00 | 0.00 | 1.00 | 1.000 |
| RF + XGBoost (soft vote) | 0.800 [0.33, 1.00] | 1.000 [1.00, 1.00] | 0.667 [0.20, 1.00] | 0.000 [0.00, 0.00] | 1.00 | 0.00 | 1.00 | 1.000 |

Intervals: task-cluster bootstrap, 2000 resamples of 6 groups (valid resamples: 2000). Sessions of one task are not independent, so whole tasks are resampled; with few tasks the intervals are wide. Per-session Wilson intervals, which ignore that dependence, are narrower (Random Forest recall [0.62, 0.71], FPR [0.00, 0.01]) and are stored in `metrics.json` for every model.

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
| Random Forest | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 27.94 ms |
| SVM (RBF) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 3.75 ms |
| XGBoost | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 3.90 ms |
| RF + XGBoost (soft vote) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 30.05 ms |

Confusion matrices (test): `confusion_matrix_rf.png`, `confusion_matrix_svm.png`, `confusion_matrix_xgb.png`, `confusion_matrix_rf_xgb.png`

* Random Forest: TN=108 FP=0 FN=0 TP=108; end-to-end latency (read logs + features + model) median 165.3 ms; recall on attacks that succeeded 1.0 (n=68), that did not succeed 1.0 (n=40)
* SVM (RBF): TN=108 FP=0 FN=0 TP=108; end-to-end latency (read logs + features + model) median 71.1 ms; recall on attacks that succeeded 1.0 (n=68), that did not succeed 1.0 (n=40)
* XGBoost: TN=108 FP=0 FN=0 TP=108; end-to-end latency (read logs + features + model) median 73.4 ms; recall on attacks that succeeded 1.0 (n=68), that did not succeed 1.0 (n=40)
* RF + XGBoost (soft vote): TN=108 FP=0 FN=0 TP=108; end-to-end latency (read logs + features + model) median 118.0 ms; recall on attacks that succeeded 1.0 (n=68), that did not succeed 1.0 (n=40)

Per payload style in the test set (n is tiny):

| Style | n | RF recall | SVM recall | XGB recall | RF+XGB recall |
|---|---|---|---|---|---|
| overt | 6 | 1.00 | 1.00 | 1.00 | 1.00 |
| padded | 8 | 1.00 | 1.00 | 1.00 | 1.00 |
| param | 5 | 1.00 | 1.00 | 1.00 | 1.00 |
| polite | 7 | 1.00 | 1.00 | 1.00 | 1.00 |
| tagged | 10 | 1.00 | 1.00 | 1.00 | 1.00 |

## 3. Hold-one-payload-style-out (generalization to an unseen style)
Train: benign-train + attacks of the other 4 styles. Test: benign-test + all attacks of the held-out style. Payload-style holdout, NOT a family holdout. Benign train/test: 252/108.

**This is a payload-style holdout within `poisoned_tool`, not the family holdout.** The three-family experiment follows below.

| Held-out poisoned-tool style | test attacks | Model | Recall | FPR | F1 |
|---|---:|---|---:|---:|---:|
| overt | 24 | Random Forest | 1.00 | 0.00 | 1.00 |
| overt | 24 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| overt | 24 | XGBoost | 1.00 | 0.00 | 1.00 |
| overt | 24 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| padded | 24 | Random Forest | 1.00 | 0.00 | 1.00 |
| padded | 24 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| padded | 24 | XGBoost | 1.00 | 0.00 | 1.00 |
| padded | 24 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| param | 24 | Random Forest | 0.00 | 0.00 | 0.00 |
| param | 24 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| param | 24 | XGBoost | 0.00 | 0.00 | 0.00 |
| param | 24 | RF + XGBoost (soft vote) | 0.00 | 0.00 | 0.00 |
| polite | 24 | Random Forest | 1.00 | 0.00 | 1.00 |
| polite | 24 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| polite | 24 | XGBoost | 1.00 | 0.00 | 1.00 |
| polite | 24 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| tagged | 24 | Random Forest | 1.00 | 0.00 | 1.00 |
| tagged | 24 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| tagged | 24 | XGBoost | 1.00 | 0.00 | 1.00 |
| tagged | 24 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |

## 3a. Hold-one-attack-family-out
For each fold, train on benign training sessions and all other attack families; test on benign test sessions plus the held-out attack family. This is a family holdout.

| Held-out family | test attacks | Model | Recall | FPR | F1 |
|---|---:|---|---:|---:|---:|
| poisoned_tool | 120 | Random Forest | 0.42 | 0.00 | 0.60 |
| poisoned_tool | 120 | SVM (RBF) | 0.00 | 0.00 | 0.00 |
| poisoned_tool | 120 | XGBoost | 0.80 | 0.00 | 0.89 |
| poisoned_tool | 120 | RF + XGBoost (soft vote) | 0.80 | 0.00 | 0.89 |
| sampling_injection | 120 | Random Forest | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | SVM (RBF) | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | XGBoost | 0.00 | 0.00 | 0.00 |
| sampling_injection | 120 | RF + XGBoost (soft vote) | 0.00 | 0.00 | 0.00 |
| shadowing | 120 | Random Forest | 1.00 | 0.00 | 1.00 |
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
| structural | 26 | SVM (RBF) | 0.73 | 0.00 | 0.84 |
| structural | 26 | XGBoost | 1.00 | 0.00 | 1.00 |
| structural | 26 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| behavioral | 19 | Random Forest | 0.55 | 0.02 | 0.70 |
| behavioral | 19 | SVM (RBF) | 0.55 | 0.02 | 0.70 |
| behavioral | 19 | XGBoost | 0.55 | 0.02 | 0.70 |
| behavioral | 19 | RF + XGBoost (soft vote) | 0.55 | 0.02 | 0.70 |
| content | 20 | Random Forest | 1.00 | 0.00 | 1.00 |
| content | 20 | SVM (RBF) | 0.81 | 0.21 | 0.80 |
| content | 20 | XGBoost | 1.00 | 0.00 | 1.00 |
| content | 20 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| structural+behavioral | 45 | Random Forest | 1.00 | 0.00 | 1.00 |
| structural+behavioral | 45 | SVM (RBF) | 0.73 | 0.00 | 0.84 |
| structural+behavioral | 45 | XGBoost | 1.00 | 0.00 | 1.00 |
| structural+behavioral | 45 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |

**Confound check:** a Random Forest that sees only `n_servers_mounted` reaches accuracy 0.49, recall 0.92, FPR 0.94 on the test set (majority-class accuracy would be 0.50). Server-count distributions are matched by construction in this Phase 9 dataset.

## 5. Supplementary: RepeatedStratifiedKFold(n_splits=5, n_repeats=5) on all 720 sessions
| Model | Accuracy | Precision | Recall | F1 | FPR |
|---|---|---|---|---|---|
| Random Forest | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.000 ± 0.000 |
| SVM (RBF) | 0.999 ± 0.004 | 0.998 ± 0.008 | 1.000 ± 0.000 | 0.999 ± 0.004 | 0.002 ± 0.008 |
| XGBoost | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.000 ± 0.000 |
| RF + XGBoost (soft vote) | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.000 ± 0.000 |

## 5a. Baseline duplicate check
190 of 216 baseline test sessions have an **exact feature-vector copy** in the training set (by group: {'benign': 108, 'poisoned_tool': 10, 'sampling_injection': 36, 'shadowing': 36}). The dataset has 116 distinct feature vectors among 720 sessions. High baseline scores on such a split largely reflect memorisation; use the task-grouped results below as the generalization estimate.

## 5b. Task-grouped CV (more honest generalization estimate)
GroupKFold(n_splits=5) on task_id over 6 tasks: no task is in both train and test; every session is predicted out-of-fold and metrics are pooled.

| Model | Accuracy | Precision | Recall | F1 | FPR | Recall poisoned_tool | Recall sampling_injection | Recall shadowing |
|---|---|---|---|---|---|---|---|---|
| Random Forest | 0.833 | 1.000 | 0.667 | 0.800 | 0.000 | 1.00 | 0.00 | 1.00 |
| SVM (RBF) | 0.807 | 0.927 | 0.667 | 0.775 | 0.053 | 1.00 | 0.00 | 1.00 |
| XGBoost | 0.833 | 1.000 | 0.667 | 0.800 | 0.000 | 1.00 | 0.00 | 1.00 |
| RF + XGBoost (soft vote) | 0.833 | 1.000 | 0.667 | 0.800 | 0.000 | 1.00 | 0.00 | 1.00 |

Folds (held-out tasks): 1: fs_shadowing_probe (240 sessions); 2: fs_sampling_probe (240 sessions); 3: calc_add, multi_region_share (120 sessions); 4: multi_order_share (60 sessions); 5: calc_temperature (60 sessions)

## 5c. Benign-only anomaly detection (task-grouped, no attack data used)
Fitted on benign sessions of the training tasks only; threshold = 0.95 quantile of their anomaly scores (target FPR about 5%). No attack data used for fitting or thresholds.

| Detector | Precision | Recall [95 % CI] | F1 [95 % CI] | FPR [95 % CI] | Recall poisoned_tool | Recall sampling_injection | Recall shadowing |
|---|---|---|---|---|---|---|---|
| Isolation Forest | 0.254 | 0.044 [0.00, 0.18] | 0.076 [0.00, 0.25] | 0.131 [0.03, 0.44] | 0.13 | 0.00 | 0.00 |
| One-Class SVM | 0.500 | 1.000 [1.00, 1.00] | 0.667 [0.67, 0.67] | 1.000 [1.00, 1.00] | 1.00 | 1.00 | 1.00 |

Intervals: task-cluster bootstrap (see the headline). A benign-only detector flags what is *unusual*, not what is malicious: on a closed-world lab dataset, unfamiliar benign tasks can look as unusual as attacks.

## 6. Most important Random Forest features (impurity-based)

| Feature | Category | Importance |
|---|---|---|
| `desc_len_std` | content | 0.161 |
| `desc_len_mean` | content | 0.106 |
| `max_desc_param_ratio` | content | 0.104 |
| `tool_name_mentions` | content | 0.057 |
| `server_initiated_request_count` | structural | 0.053 |
| `desc_len_max` | content | 0.051 |
| `metadata_text_len_max` | content | 0.047 |
| `desc_words_max` | content | 0.040 |
| `n_distinct_method_bigrams` | behavioral | 0.036 |
| `desc_sentences_max` | content | 0.033 |

Plot: `feature_importance_rf.png`

## 6a. Most important XGBoost features (share of total gain)

| Feature | Category | Importance |
|---|---|---|
| `desc_len_std` | content | 0.759 |
| `size_max` | structural | 0.213 |
| `tool_name_mentions` | content | 0.017 |
| `tools_list_resp_size_mean` | structural | 0.004 |
| `max_directive_density` | content | 0.003 |
| `desc_len_mean` | content | 0.002 |
| `size_std` | structural | 0.001 |
| `cross_server_transition_share` | behavioral | 0.000 |
| `desc_words_total` | content | 0.000 |
| `desc_words_max` | content | 0.000 |

Plot: `feature_importance_xgb.png`

## 7. Interpretation and limitations
* **Closed-world benign metadata.** Benign servers advertise fixed tool descriptions in this lab, so *any* change to `tools/list` (size, wording) can separate the classes. Several single features do so perfectly on this data (see docs/ml.md). High scores here mostly reflect this; they do not show that the detector would work on real, varied MCP servers.
* **Small, controlled sample.** Repeated scenario seeds do not create independent server implementations or attack designs. Results are proof of concept, not real-world validation.
* **Template and author bias.** Benign descriptions are fixed and payload templates were written by the same project team; richer benign variation is needed.
* **Mock-agent limitation.** Obedience is simulated. Sampling success means the protocol exchange completed, not that an LLM was influenced.
* **Lexicon bias.** Content lexicons were written by people who knew the payloads.
* **No model ranking.** Differences between the models (RF, SVM, XGBoost, RF + XGBoost) are within what a different split could change and inside each other's task-bootstrap intervals; no statistical test supports calling one of them better. The ensemble cannot recover information that neither member has: an attack family missing from training stays missed.
