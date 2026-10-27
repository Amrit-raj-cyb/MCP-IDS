# Evaluation report: exp_012_phase9_081_20261010

> **This experiment demonstrates the functionality of the ML pipeline, but the dataset is too small to establish strong real-world generalization.**

## Setup
* Dataset: `/lab/data/phase9_081_targeted` (read-only), SHA-256 `f0fd05d28c873b61...`
* Sessions: 180 (90 benign, 90 attack across poisoned_tool, sampling_injection, shadowing); protocol/mock success count (not real LLM influence): 49
* Features: 65 ({'structural': 26, 'behavioral': 19, 'content': 20}); lab marker/canary removed with `neutralize()`
* Split: stratified, seed 42, test size 0.3 → train 126 (63 benign / 63 attack), test 54 (27 benign / 27 attack)
* Positive class: `attack` = attack **attempted** (not success)

## Headline: task-grouped cross-validation with 95 % confidence intervals (hyperparameters tuned, nested)
Protocol: nested task-grouped cross-validation (GroupKFold(n_splits=5) on task_id, 6 tasks; hyperparameters tuned inside each outer training fold); no task is in both train and test, so seed-level near-duplicates cannot be memorised; the held-out tasks never influence the chosen settings. **Quote these numbers**, not the random split in section 2.

| Model | F1 [95 % CI] | Precision [95 % CI] | Recall [95 % CI] | FPR [95 % CI] | Recall poisoned_tool | Recall sampling_injection | Recall shadowing | Random-split F1 | Untuned F1 |
|---|---|---|---|---|---|---|---|---|---|
| Random Forest | 0.800 [0.35, 1.00] | 1.000 [1.00, 1.00] | 0.667 [0.21, 1.00] | 0.000 [0.00, 0.00] | 1.00 | 0.00 | 1.00 | 1.000 | 0.800 |
| SVM (RBF) | 0.764 [0.33, 1.00] | 0.895 [0.66, 1.00] | 0.667 [0.21, 1.00] | 0.078 [0.00, 0.32] | 1.00 | 0.00 | 1.00 | 1.000 | 0.764 |
| XGBoost | 0.800 [0.35, 1.00] | 1.000 [1.00, 1.00] | 0.667 [0.21, 1.00] | 0.000 [0.00, 0.00] | 1.00 | 0.00 | 1.00 | 1.000 | 0.800 |
| RF + XGBoost (soft vote) | 0.800 [0.35, 1.00] | 1.000 [1.00, 1.00] | 0.667 [0.21, 1.00] | 0.000 [0.00, 0.00] | 1.00 | 0.00 | 1.00 | 1.000 | 0.800 |
| Decision Tree | 0.800 [0.35, 1.00] | 1.000 [1.00, 1.00] | 0.667 [0.21, 1.00] | 0.000 [0.00, 0.00] | 1.00 | 0.00 | 1.00 | 1.000 | 0.800 |
| 1-D CNN | 0.800 [0.35, 1.00] | 1.000 [1.00, 1.00] | 0.667 [0.21, 1.00] | 0.000 [0.00, 0.00] | 1.00 | 0.00 | 1.00 | 1.000 | 0.800 |
| Raw-traffic CNN | 0.593 [0.28, 0.78] | 0.566 [0.50, 0.86] | 0.622 [0.18, 0.99] | 0.478 [0.06, 0.91] | 0.87 | 1.00 | 0.00 | 0.941 | 0.605 |

Intervals: task-cluster bootstrap, 2000 resamples of 6 groups (valid resamples: 2000). Sessions of one task are not independent, so whole tasks are resampled; with few tasks the intervals are wide. Per-session Wilson intervals, which ignore that dependence, are narrower (Random Forest recall [0.56, 0.76], FPR [0.00, 0.04]) and are stored in `metrics.json` for every model.

## 1. Baseline split: TRAINING metrics (not evidence of generalization)
| Model | Accuracy | Precision | Recall | F1 | FPR | Latency |
|---|---|---|---|---|---|---|
| Random Forest | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| SVM (RBF) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| XGBoost | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| RF + XGBoost (soft vote) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| Decision Tree | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| 1-D CNN | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| Raw-traffic CNN | 0.960 | 1.000 | 0.921 | 0.959 | 0.000 | - |

## 2. Baseline split: TEST metrics (random split; for comparison only, see the headline above)
| Model | Accuracy | Precision | Recall | F1 | FPR | Latency (model only, median) |
|---|---|---|---|---|---|---|
| Random Forest | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 44.63 ms |
| SVM (RBF) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 4.38 ms |
| XGBoost | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 5.44 ms |
| RF + XGBoost (soft vote) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 49.65 ms |
| Decision Tree | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 3.92 ms |
| 1-D CNN | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 4.98 ms |
| Raw-traffic CNN | 0.944 | 1.000 | 0.889 | 0.941 | 0.000 | 7.45 ms |

Confusion matrices (test): `confusion_matrix_rf.png`, `confusion_matrix_svm.png`, `confusion_matrix_xgb.png`, `confusion_matrix_rf_xgb.png`, `confusion_matrix_dt.png`, `confusion_matrix_cnn.png`, `confusion_matrix_cnn_raw.png`

* Random Forest: TN=27 FP=0 FN=0 TP=27; end-to-end latency (read logs + features + model) median 95.8 ms; recall on attacks that succeeded 1.0 (n=15), that did not succeed 1.0 (n=12)
* SVM (RBF): TN=27 FP=0 FN=0 TP=27; end-to-end latency (read logs + features + model) median 17.0 ms; recall on attacks that succeeded 1.0 (n=15), that did not succeed 1.0 (n=12)
* XGBoost: TN=27 FP=0 FN=0 TP=27; end-to-end latency (read logs + features + model) median 20.7 ms; recall on attacks that succeeded 1.0 (n=15), that did not succeed 1.0 (n=12)
* RF + XGBoost (soft vote): TN=27 FP=0 FN=0 TP=27; end-to-end latency (read logs + features + model) median 110.4 ms; recall on attacks that succeeded 1.0 (n=15), that did not succeed 1.0 (n=12)
* Decision Tree: TN=27 FP=0 FN=0 TP=27; end-to-end latency (read logs + features + model) median 17.4 ms; recall on attacks that succeeded 1.0 (n=15), that did not succeed 1.0 (n=12)
* 1-D CNN: TN=27 FP=0 FN=0 TP=27; end-to-end latency (read logs + features + model) median 18.7 ms; recall on attacks that succeeded 1.0 (n=15), that did not succeed 1.0 (n=12)
* Raw-traffic CNN: TN=27 FP=0 FN=3 TP=24; end-to-end latency (read logs + features + model) median 22.9 ms; recall on attacks that succeeded 0.9333 (n=15), that did not succeed 0.8333 (n=12)

Per payload style in the test set (n is tiny):

| Style | n | RF recall | SVM recall | XGB recall | RF+XGB recall | DT recall | CNN recall | Raw CNN recall |
|---|---|---|---|---|---|---|---|---|
| overt | 3 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| padded | 1 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| param | 3 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.67 |
| polite | 2 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.00 |

## 3. Hold-one-payload-style-out (generalization to an unseen style)
Train: benign-train + attacks of the other 4 styles. Test: benign-test + all attacks of the held-out style. Payload-style holdout, NOT a family holdout. Benign train/test: 63/27.

**This is a payload-style holdout within `poisoned_tool`, not the family holdout.** The three-family experiment follows below.

| Held-out poisoned-tool style | test attacks | Model | Recall | FPR | F1 |
|---|---:|---|---:|---:|---:|
| overt | 6 | Random Forest | 1.00 | 0.00 | 1.00 |
| overt | 6 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| overt | 6 | XGBoost | 1.00 | 0.00 | 1.00 |
| overt | 6 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| overt | 6 | Decision Tree | 1.00 | 0.00 | 1.00 |
| overt | 6 | 1-D CNN | 1.00 | 0.00 | 1.00 |
| overt | 6 | Raw-traffic CNN | 1.00 | 0.07 | 0.86 |
| padded | 6 | Random Forest | 1.00 | 0.00 | 1.00 |
| padded | 6 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| padded | 6 | XGBoost | 1.00 | 0.00 | 1.00 |
| padded | 6 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| padded | 6 | Decision Tree | 1.00 | 0.00 | 1.00 |
| padded | 6 | 1-D CNN | 1.00 | 0.00 | 1.00 |
| padded | 6 | Raw-traffic CNN | 1.00 | 0.19 | 0.71 |
| param | 6 | Random Forest | 0.00 | 0.00 | 0.00 |
| param | 6 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| param | 6 | XGBoost | 0.00 | 0.00 | 0.00 |
| param | 6 | RF + XGBoost (soft vote) | 0.00 | 0.00 | 0.00 |
| param | 6 | Decision Tree | 0.00 | 0.00 | 0.00 |
| param | 6 | 1-D CNN | 1.00 | 0.00 | 1.00 |
| param | 6 | Raw-traffic CNN | 1.00 | 0.19 | 0.71 |
| polite | 6 | Random Forest | 1.00 | 0.00 | 1.00 |
| polite | 6 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| polite | 6 | XGBoost | 1.00 | 0.00 | 1.00 |
| polite | 6 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| polite | 6 | Decision Tree | 1.00 | 0.00 | 1.00 |
| polite | 6 | 1-D CNN | 1.00 | 0.00 | 1.00 |
| polite | 6 | Raw-traffic CNN | 0.00 | 0.00 | 0.00 |
| tagged | 6 | Random Forest | 1.00 | 0.00 | 1.00 |
| tagged | 6 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| tagged | 6 | XGBoost | 1.00 | 0.00 | 1.00 |
| tagged | 6 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| tagged | 6 | Decision Tree | 1.00 | 0.00 | 1.00 |
| tagged | 6 | 1-D CNN | 1.00 | 0.00 | 1.00 |
| tagged | 6 | Raw-traffic CNN | 0.83 | 0.07 | 0.77 |

## 3a. Hold-one-attack-family-out
For each fold, train on benign training sessions and all other attack families; test on benign test sessions plus the held-out attack family. This is a family holdout.

| Held-out family | test attacks | Model | Recall | FPR | F1 |
|---|---:|---|---:|---:|---:|
| poisoned_tool | 30 | Random Forest | 0.43 | 0.00 | 0.60 |
| poisoned_tool | 30 | SVM (RBF) | 0.00 | 0.00 | 0.00 |
| poisoned_tool | 30 | XGBoost | 0.80 | 0.00 | 0.89 |
| poisoned_tool | 30 | RF + XGBoost (soft vote) | 0.80 | 0.00 | 0.89 |
| poisoned_tool | 30 | Decision Tree | 0.20 | 0.00 | 0.33 |
| poisoned_tool | 30 | 1-D CNN | 0.00 | 0.00 | 0.00 |
| poisoned_tool | 30 | Raw-traffic CNN | 0.00 | 0.00 | 0.00 |
| sampling_injection | 30 | Random Forest | 0.00 | 0.00 | 0.00 |
| sampling_injection | 30 | SVM (RBF) | 0.00 | 0.00 | 0.00 |
| sampling_injection | 30 | XGBoost | 0.00 | 0.00 | 0.00 |
| sampling_injection | 30 | RF + XGBoost (soft vote) | 0.00 | 0.00 | 0.00 |
| sampling_injection | 30 | Decision Tree | 0.00 | 0.00 | 0.00 |
| sampling_injection | 30 | 1-D CNN | 0.00 | 0.00 | 0.00 |
| sampling_injection | 30 | Raw-traffic CNN | 0.00 | 0.00 | 0.00 |
| shadowing | 30 | Random Forest | 1.00 | 0.00 | 1.00 |
| shadowing | 30 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| shadowing | 30 | XGBoost | 1.00 | 0.00 | 1.00 |
| shadowing | 30 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| shadowing | 30 | Decision Tree | 1.00 | 0.00 | 1.00 |
| shadowing | 30 | 1-D CNN | 1.00 | 0.00 | 1.00 |
| shadowing | 30 | Raw-traffic CNN | 0.00 | 0.00 | 0.00 |

## 4. Feature-group ablation (same split, test set)
| Features | # | Model | Recall | FPR | F1 |
|---|---:|---|---:|---:|---:|
| all | 65 | Random Forest | 1.00 | 0.00 | 1.00 |
| all | 65 | SVM (RBF) | 1.00 | 0.00 | 1.00 |
| all | 65 | XGBoost | 1.00 | 0.00 | 1.00 |
| all | 65 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| all | 65 | Decision Tree | 1.00 | 0.00 | 1.00 |
| all | 65 | 1-D CNN | 1.00 | 0.00 | 1.00 |
| structural | 26 | Random Forest | 1.00 | 0.00 | 1.00 |
| structural | 26 | SVM (RBF) | 0.63 | 0.00 | 0.77 |
| structural | 26 | XGBoost | 1.00 | 0.00 | 1.00 |
| structural | 26 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| structural | 26 | Decision Tree | 1.00 | 0.00 | 1.00 |
| structural | 26 | 1-D CNN | 0.96 | 0.00 | 0.98 |
| behavioral | 19 | Random Forest | 0.52 | 0.30 | 0.57 |
| behavioral | 19 | SVM (RBF) | 0.41 | 0.04 | 0.56 |
| behavioral | 19 | XGBoost | 0.52 | 0.30 | 0.57 |
| behavioral | 19 | RF + XGBoost (soft vote) | 0.52 | 0.30 | 0.57 |
| behavioral | 19 | Decision Tree | 0.52 | 0.26 | 0.58 |
| behavioral | 19 | 1-D CNN | 0.48 | 0.26 | 0.55 |
| content | 20 | Random Forest | 1.00 | 0.00 | 1.00 |
| content | 20 | SVM (RBF) | 0.78 | 0.00 | 0.88 |
| content | 20 | XGBoost | 0.96 | 0.00 | 0.98 |
| content | 20 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| content | 20 | Decision Tree | 1.00 | 0.00 | 1.00 |
| content | 20 | 1-D CNN | 1.00 | 0.00 | 1.00 |
| structural+behavioral | 45 | Random Forest | 1.00 | 0.00 | 1.00 |
| structural+behavioral | 45 | SVM (RBF) | 0.48 | 0.00 | 0.65 |
| structural+behavioral | 45 | XGBoost | 1.00 | 0.00 | 1.00 |
| structural+behavioral | 45 | RF + XGBoost (soft vote) | 1.00 | 0.00 | 1.00 |
| structural+behavioral | 45 | Decision Tree | 0.96 | 0.00 | 0.98 |
| structural+behavioral | 45 | 1-D CNN | 0.93 | 0.00 | 0.96 |

**Confound check:** a Random Forest that sees only `n_servers_mounted` reaches accuracy 0.39, recall 0.30, FPR 0.52 on the test set (majority-class accuracy would be 0.50). Server-count distributions are matched by construction in this Phase 9 dataset.

## 5. Supplementary: RepeatedStratifiedKFold(n_splits=5, n_repeats=5) on all 180 sessions
| Model | Accuracy | Precision | Recall | F1 | FPR |
|---|---|---|---|---|---|
| Random Forest | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.000 ± 0.000 |
| SVM (RBF) | 0.996 ± 0.010 | 0.992 ± 0.019 | 1.000 ± 0.000 | 0.996 ± 0.010 | 0.009 ± 0.020 |
| XGBoost | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.000 ± 0.000 |
| RF + XGBoost (soft vote) | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.000 ± 0.000 |
| Decision Tree | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.000 ± 0.000 |
| 1-D CNN | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.000 ± 0.000 |

## 5a. Baseline duplicate check
44 of 54 baseline test sessions have an **exact feature-vector copy** in the training set (by group: {'benign': 26, 'sampling_injection': 9, 'shadowing': 9}). The dataset has 53 distinct feature vectors among 180 sessions. High baseline scores on such a split largely reflect memorisation; use the task-grouped results below as the generalization estimate.

## 5b. Task-grouped CV (more honest generalization estimate)
GroupKFold(n_splits=5) on task_id over 6 tasks: no task is in both train and test; every session is predicted out-of-fold and metrics are pooled.

| Model | Accuracy | Precision | Recall | F1 | FPR | Recall poisoned_tool | Recall sampling_injection | Recall shadowing |
|---|---|---|---|---|---|---|---|---|
| Random Forest | 0.833 | 1.000 | 0.667 | 0.800 | 0.000 | 1.00 | 0.00 | 1.00 |
| SVM (RBF) | 0.794 | 0.895 | 0.667 | 0.764 | 0.078 | 1.00 | 0.00 | 1.00 |
| XGBoost | 0.833 | 1.000 | 0.667 | 0.800 | 0.000 | 1.00 | 0.00 | 1.00 |
| RF + XGBoost (soft vote) | 0.833 | 1.000 | 0.667 | 0.800 | 0.000 | 1.00 | 0.00 | 1.00 |
| Decision Tree | 0.833 | 1.000 | 0.667 | 0.800 | 0.000 | 1.00 | 0.00 | 1.00 |
| 1-D CNN | 0.833 | 1.000 | 0.667 | 0.800 | 0.000 | 1.00 | 0.00 | 1.00 |
| Raw-traffic CNN | 0.594 | 0.590 | 0.622 | 0.605 | 0.433 | 0.87 | 1.00 | 0.00 |

Folds (held-out tasks): 1: fs_shadowing_probe (60 sessions); 2: fs_sampling_probe (60 sessions); 3: multi_order_share, multi_region_share (28 sessions); 4: calc_temperature (16 sessions); 5: calc_add (16 sessions)

## 5b-tuned. Nested task-grouped CV (hyperparameters tuned inside each outer fold)
Nested CV: for each outer fold, hyperparameters are searched on the outer training tasks only (inner GroupKFold(3) on task_id, pooled out-of-fold F1; ml/tuning.py), then the model is refitted with the winner and predicts the held-out tasks.

| Model | Precision | Recall | F1 | FPR | Recall poisoned_tool | Recall sampling_injection | Recall shadowing | Untuned F1 (5b) |
|---|---|---|---|---|---|---|---|---|
| Random Forest | 1.000 | 0.667 | 0.800 | 0.000 | 1.00 | 0.00 | 1.00 | 0.800 |
| SVM (RBF) | 0.895 | 0.667 | 0.764 | 0.078 | 1.00 | 0.00 | 1.00 | 0.764 |
| XGBoost | 1.000 | 0.667 | 0.800 | 0.000 | 1.00 | 0.00 | 1.00 | 0.800 |
| RF + XGBoost (soft vote) | 1.000 | 0.667 | 0.800 | 0.000 | 1.00 | 0.00 | 1.00 | 0.800 |
| Decision Tree | 1.000 | 0.667 | 0.800 | 0.000 | 1.00 | 0.00 | 1.00 | 0.800 |
| 1-D CNN | 1.000 | 0.667 | 0.800 | 0.000 | 1.00 | 0.00 | 1.00 | 0.800 |
| Raw-traffic CNN | 0.566 | 0.622 | 0.593 | 0.478 | 0.87 | 1.00 | 0.00 | 0.605 |

Settings chosen in each outer fold (fold 1 ... 5):

* Random Forest: {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 300}; {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 600}; {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 300}; {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 300}; {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 300}
* SVM (RBF): {"C": 0.1, "gamma": 0.1}; {"C": 10.0, "gamma": 0.01}; {"C": 1.0, "gamma": 0.01}; {"C": 0.1, "gamma": "scale"}; {"C": 0.1, "gamma": "scale"}
* XGBoost: {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 300, "subsample": 0.8}; {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 100, "subsample": 0.8}; {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 300, "subsample": 1.0}; {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 300, "subsample": 1.0}; {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 300, "subsample": 1.0}
* RF + XGBoost (soft vote): {"random_forest": {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 300}, "xgboost": {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 300, "subsample": 0.8}}; {"random_forest": {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 600}, "xgboost": {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 100, "subsample": 0.8}}; {"random_forest": {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 300}, "xgboost": {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 300, "subsample": 1.0}}; {"random_forest": {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 300}, "xgboost": {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 300, "subsample": 1.0}}; {"random_forest": {"max_depth": null, "max_features": "sqrt", "min_samples_leaf": 1, "n_estimators": 300}, "xgboost": {"learning_rate": 0.3, "max_depth": 6, "n_estimators": 300, "subsample": 1.0}}
* Decision Tree: {"criterion": "gini", "max_depth": null, "min_samples_leaf": 1}; {"criterion": "gini", "max_depth": null, "min_samples_leaf": 1}; {"criterion": "gini", "max_depth": null, "min_samples_leaf": 1}; {"criterion": "gini", "max_depth": null, "min_samples_leaf": 1}; {"criterion": "gini", "max_depth": null, "min_samples_leaf": 1}
* 1-D CNN: {"channels": [16, 32], "dropout": 0.2, "epochs": 50, "learning_rate": 0.001}; {"channels": [16, 32], "dropout": 0.2, "epochs": 50, "learning_rate": 0.001}; {"channels": [32, 64], "dropout": 0.2, "epochs": 50, "learning_rate": 0.001}; {"channels": [32, 64], "dropout": 0.5, "epochs": 100, "learning_rate": 0.001}; {"channels": [32, 64], "dropout": 0.5, "epochs": 100, "learning_rate": 0.001}
* Raw-traffic CNN: {"dropout": 0.2, "learning_rate": 0.003, "max_len": 32768}; {"dropout": 0.2, "learning_rate": 0.003, "max_len": 32768}; {"dropout": 0.2, "learning_rate": 0.003, "max_len": 32768}; {"dropout": 0.5, "learning_rate": 0.001, "max_len": 32768}; {"dropout": 0.5, "learning_rate": 0.003, "max_len": 32768}

## 5c. Benign-only anomaly detection (task-grouped, no attack data used)
Fitted on benign sessions of the training tasks only; threshold = 0.95 quantile of their anomaly scores (target FPR about 5%). No attack data used for fitting or thresholds.

| Detector | Precision | Recall [95 % CI] | F1 [95 % CI] | FPR [95 % CI] | Recall poisoned_tool | Recall sampling_injection | Recall shadowing |
|---|---|---|---|---|---|---|---|
| Isolation Forest | 0.111 | 0.011 [0.00, 0.05] | 0.020 [0.00, 0.07] | 0.089 [0.00, 0.35] | 0.03 | 0.00 | 0.00 |
| One-Class SVM | 0.500 | 1.000 [1.00, 1.00] | 0.667 [0.67, 0.67] | 1.000 [1.00, 1.00] | 1.00 | 1.00 | 1.00 |

Intervals: task-cluster bootstrap (see the headline). A benign-only detector flags what is *unusual*, not what is malicious: on a closed-world lab dataset, unfamiliar benign tasks can look as unusual as attacks.

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

## 6a. Most important XGBoost features (share of total gain)

| Feature | Category | Importance |
|---|---|---|
| `desc_len_std` | content | 0.676 |
| `tool_name_mentions` | content | 0.104 |
| `n_distinct_tool_bigrams` | behavioral | 0.045 |
| `directive_word_count` | content | 0.039 |
| `tools_list_resp_size_mean` | structural | 0.029 |
| `size_mean` | structural | 0.027 |
| `size_std` | structural | 0.024 |
| `tools_call_resp_size_mean` | structural | 0.015 |
| `max_directive_density` | content | 0.014 |
| `max_calls_per_server` | behavioral | 0.010 |

Plot: `feature_importance_xgb.png`

## 7. Interpretation and limitations
* **Closed-world benign metadata.** Benign servers advertise fixed tool descriptions in this lab, so *any* change to `tools/list` (size, wording) can separate the classes. Several single features do so perfectly on this data (see docs/ml.md). High scores here mostly reflect this; they do not show that the detector would work on real, varied MCP servers.
* **Small, controlled sample.** Repeated scenario seeds do not create independent server implementations or attack designs. Results are proof of concept, not real-world validation.
* **Template and author bias.** Benign descriptions are fixed and payload templates were written by the same project team; richer benign variation is needed.
* **Mock-agent limitation.** Obedience is simulated. Sampling success means the protocol exchange completed, not that an LLM was influenced.
* **Lexicon bias.** Content lexicons were written by people who knew the payloads.
* **No model ranking.** Differences between the models (Random Forest, SVM (RBF), XGBoost, RF + XGBoost (soft vote), Decision Tree, 1-D CNN, Raw-traffic CNN) are within what a different split could change and inside each other's task-bootstrap intervals; no statistical test supports calling one of them better. The ensemble cannot recover information that neither member has: an attack family missing from training stays missed.
