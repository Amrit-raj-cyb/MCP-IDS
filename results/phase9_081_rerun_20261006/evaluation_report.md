# Evaluation report: exp_004_phase9_081_rerun_20261006

> **This experiment demonstrates the functionality of the ML pipeline, but the dataset is too small to establish strong real-world generalization.**

## Setup
* Dataset: `/lab/data/phase9_081_targeted` (read-only), SHA-256 `f0fd05d28c873b61...`
* Sessions: 180 (90 benign, 90 attack across poisoned_tool, sampling_injection, shadowing); protocol/mock success count (not real LLM influence): 49
* Features: 65 ({'structural': 26, 'behavioral': 19, 'content': 20}); lab marker/canary removed with `neutralize()`
* Split: stratified, seed 42, test size 0.3 → train 126 (63 benign / 63 attack), test 54 (27 benign / 27 attack)
* Positive class: `attack` = attack **attempted** (not success)

## 1. Baseline split: TRAINING metrics (not evidence of generalization)
| Model | Accuracy | Precision | Recall | F1 | FPR | Latency |
|---|---|---|---|---|---|---|
| Random Forest | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| SVM (RBF) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |

## 2. Baseline split: TEST metrics
| Model | Accuracy | Precision | Recall | F1 | FPR | Latency (model only, median) |
|---|---|---|---|---|---|---|
| Random Forest | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 14.29 ms |
| SVM (RBF) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 1.45 ms |

Confusion matrices (test): `confusion_matrix_rf.png`, `confusion_matrix_svm.png`

* Random Forest: TN=27 FP=0 FN=0 TP=27; end-to-end latency (read logs + features + model) median 55.6 ms; recall on attacks that succeeded 1.0 (n=15), that did not succeed 1.0 (n=12)
* SVM: TN=27 FP=0 FN=0 TP=27; end-to-end latency (read logs + features + model) median 28.9 ms; recall on attacks that succeeded 1.0 (n=15), that did not succeed 1.0 (n=12)

Per payload style in the test set (n is tiny):

| Style | n | RF recall | SVM recall |
|---|---|---|---|
| overt | 3 | 1.00 | 1.00 |
| padded | 1 | 1.00 | 1.00 |
| param | 3 | 1.00 | 1.00 |
| polite | 2 | 1.00 | 1.00 |

## 3. Hold-one-payload-style-out (generalization to an unseen style)
Train: benign-train + attacks of the other 4 styles. Test: benign-test + all attacks of the held-out style. Payload-style holdout, NOT a family holdout. Benign train/test: 63/27.

**This is a payload-style holdout within `poisoned_tool`, not the family holdout.** The three-family experiment follows below.

| Held-out poisoned-tool style | test attacks | RF recall | RF FPR | RF F1 | SVM recall | SVM FPR | SVM F1 |
|---|---|---|---|---|---|---|---|
| overt | 6 | 1.00 | 0.00 | 1.00 | 1.00 | 0.00 | 1.00 |
| padded | 6 | 1.00 | 0.00 | 1.00 | 1.00 | 0.00 | 1.00 |
| param | 6 | 0.00 | 0.00 | 0.00 | 1.00 | 0.00 | 1.00 |
| polite | 6 | 1.00 | 0.00 | 1.00 | 1.00 | 0.00 | 1.00 |
| tagged | 6 | 1.00 | 0.00 | 1.00 | 1.00 | 0.00 | 1.00 |

## 3a. Hold-one-attack-family-out
For each fold, train on benign training sessions and all other attack families; test on benign test sessions plus the held-out attack family. This is a family holdout.

| Held-out family | test attacks | RF recall | RF FPR | RF F1 | SVM recall | SVM FPR | SVM F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| poisoned_tool | 30 | 0.43 | 0.00 | 0.60 | 0.00 | 0.00 | 0.00 |
| sampling_injection | 30 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| shadowing | 30 | 1.00 | 0.00 | 1.00 | 1.00 | 0.00 | 1.00 |

## 4. Feature-group ablation (same split, test set)
| Features | # | RF recall | RF FPR | RF F1 | SVM recall | SVM FPR | SVM F1 |
|---|---|---|---|---|---|---|---|
| all | 65 | 1.00 | 0.00 | 1.00 | 1.00 | 0.00 | 1.00 |
| structural | 26 | 1.00 | 0.00 | 1.00 | 0.63 | 0.00 | 0.77 |
| behavioral | 19 | 0.52 | 0.30 | 0.57 | 0.41 | 0.04 | 0.56 |
| content | 20 | 1.00 | 0.00 | 1.00 | 0.78 | 0.00 | 0.88 |
| structural+behavioral | 45 | 1.00 | 0.00 | 1.00 | 0.48 | 0.00 | 0.65 |

**Confound check:** a Random Forest that sees only `n_servers_mounted` reaches accuracy 0.39, recall 0.30, FPR 0.52 on the test set (majority-class accuracy would be 0.50). Server-count distributions are matched by construction in this Phase 9 dataset.

## 5. Supplementary: RepeatedStratifiedKFold(n_splits=5, n_repeats=5) on all 180 sessions
| Model | Accuracy | Precision | Recall | F1 | FPR |
|---|---|---|---|---|---|
| Random Forest | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.000 ± 0.000 |
| SVM (RBF) | 0.996 ± 0.010 | 0.992 ± 0.019 | 1.000 ± 0.000 | 0.996 ± 0.010 | 0.009 ± 0.020 |

## 5a. Baseline duplicate check
44 of 54 baseline test sessions have an **exact feature-vector copy** in the training set (by group: {'benign': 26, 'sampling_injection': 9, 'shadowing': 9}). The dataset has 53 distinct feature vectors among 180 sessions. High baseline scores on such a split largely reflect memorisation; use the task-grouped results below as the generalization estimate.

## 5b. Task-grouped CV (more honest generalization estimate)
GroupKFold(n_splits=5) on task_id over 6 tasks: no task is in both train and test; every session is predicted out-of-fold and metrics are pooled.

| Model | Accuracy | Precision | Recall | F1 | FPR | Recall poisoned_tool | Recall sampling_injection | Recall shadowing |
|---|---|---|---|---|---|---|---|---|
| Random Forest | 0.833 | 1.000 | 0.667 | 0.800 | 0.000 | 1.00 | 0.00 | 1.00 |
| SVM (RBF) | 0.794 | 0.895 | 0.667 | 0.764 | 0.078 | 1.00 | 0.00 | 1.00 |

Folds (held-out tasks): 1: fs_shadowing_probe (60 sessions); 2: fs_sampling_probe (60 sessions); 3: multi_order_share, multi_region_share (28 sessions); 4: calc_temperature (16 sessions); 5: calc_add (16 sessions)

## 6. Most important Random Forest features (impurity-based)

| Feature | Category | Importance |
|---|---|---|
| `desc_len_std` | content | 0.164 |
| `max_desc_param_ratio` | content | 0.105 |
| `desc_len_mean` | content | 0.103 |
| `server_initiated_request_count` | structural | 0.053 |
| `metadata_text_len_max` | content | 0.050 |
| `tool_name_mentions` | content | 0.048 |
| `desc_words_max` | content | 0.047 |
| `desc_len_max` | content | 0.045 |
| `n_distinct_method_bigrams` | behavioral | 0.040 |
| `tools_list_resp_size_mean` | structural | 0.034 |

Plot: `feature_importance_rf.png`

## 7. Interpretation and limitations
* **Closed-world benign metadata.** Benign servers advertise fixed tool descriptions in this lab, so *any* change to `tools/list` (size, wording) can separate the classes. Several single features do so perfectly on this data (see docs/ml.md). High scores here mostly reflect this; they do not show that the detector would work on real, varied MCP servers.
* **Small, controlled sample.** Repeated scenario seeds do not create independent server implementations or attack designs. Results are proof of concept, not real-world validation.
* **Template and author bias.** Benign descriptions are fixed and payload templates were written by the same project team; richer benign variation is needed.
* **Mock-agent limitation.** Obedience is simulated. Sampling success means the protocol exchange completed, not that an LLM was influenced.
* **Lexicon bias.** Content lexicons were written by people who knew the payloads.
* **No model ranking.** Differences between RF and SVM are within what a different split could change; no statistical test supports calling either one better.
