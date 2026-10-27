# Evaluation report: exp_001_try6_baseline

> **This experiment demonstrates the functionality of the ML pipeline, but the dataset is too small to establish strong real-world generalization.**

## Setup
* Dataset: `C:\Projects\IDS\data\try6` (read-only), SHA-256 `0784a0f970421d70...`
* Sessions: 65 (40 benign, 25 attack, family `poisoned_tool` only); attacks that influenced the mock agent: 11
* Features: 62 ({'structural': 25, 'behavioral': 18, 'content': 19}); lab marker/canary removed with `neutralize()`
* Split: stratified, seed 42, test size 0.3 → train 45 (28 benign / 17 attack), test 20 (12 benign / 8 attack)
* Positive class: `attack` = attack **attempted** (not success)

## 1. Baseline split: TRAINING metrics (not evidence of generalization)
| Model | Accuracy | Precision | Recall | F1 | FPR | Latency |
|---|---|---|---|---|---|---|
| Random Forest | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |
| SVM (RBF) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | - |

## 2. Baseline split: TEST metrics
| Model | Accuracy | Precision | Recall | F1 | FPR | Latency (model only, median) |
|---|---|---|---|---|---|---|
| Random Forest | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 24.52 ms |
| SVM (RBF) | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 | 3.28 ms |

Confusion matrices (test): `confusion_matrix_rf.png`, `confusion_matrix_svm.png`

* Random Forest: TN=12 FP=0 FN=0 TP=8; end-to-end latency (read logs + features + model) median 68.6 ms; recall on attacks that succeeded 1.0 (n=2), that did not succeed 1.0 (n=6)
* SVM: TN=12 FP=0 FN=0 TP=8; end-to-end latency (read logs + features + model) median 13.8 ms; recall on attacks that succeeded 1.0 (n=2), that did not succeed 1.0 (n=6)

Per payload style in the test set (n is tiny):

| Style | n | RF recall | SVM recall |
|---|---|---|---|
| overt | 2 | 1.00 | 1.00 |
| padded | 2 | 1.00 | 1.00 |
| polite | 4 | 1.00 | 1.00 |

## 3. Hold-one-payload-style-out (generalization to an unseen style)
Train: benign-train + attacks of the other 4 styles. Test: benign-test + all attacks of the held-out style. Payload-style holdout, NOT a family holdout. Benign train/test: 28/12.

**This is NOT an attack-family holdout.** Only one family (`poisoned_tool`) exists.

| Held-out style | test attacks | RF recall | RF FPR | RF F1 | SVM recall | SVM FPR | SVM F1 |
|---|---|---|---|---|---|---|---|
| overt | 5 | 1.00 | 0.00 | 1.00 | 1.00 | 0.08 | 0.91 |
| padded | 5 | 1.00 | 0.00 | 1.00 | 1.00 | 0.08 | 0.91 |
| param | 5 | 0.00 | 0.00 | 0.00 | 0.80 | 0.08 | 0.80 |
| polite | 5 | 1.00 | 0.00 | 1.00 | 1.00 | 0.08 | 0.91 |
| tagged | 5 | 1.00 | 0.00 | 1.00 | 0.80 | 0.08 | 0.80 |

## 4. Feature-group ablation (same split, test set)
| Features | # | RF recall | RF FPR | RF F1 | SVM recall | SVM FPR | SVM F1 |
|---|---|---|---|---|---|---|---|
| all | 62 | 1.00 | 0.00 | 1.00 | 1.00 | 0.00 | 1.00 |
| structural | 25 | 1.00 | 0.00 | 1.00 | 0.75 | 0.75 | 0.52 |
| behavioral | 18 | 0.88 | 0.67 | 0.61 | 0.75 | 0.75 | 0.52 |
| content | 19 | 1.00 | 0.00 | 1.00 | 1.00 | 0.00 | 1.00 |
| structural+behavioral | 43 | 1.00 | 0.00 | 1.00 | 0.75 | 0.75 | 0.52 |

**Confound check:** a Random Forest that sees only `n_servers_mounted` reaches accuracy 0.45, recall 0.75, FPR 0.75 on the test set (majority-class accuracy would be 0.60). Attack scenarios mount 4 servers more often than benign ones, a dataset artefact a model could exploit.

## 5. Supplementary: RepeatedStratifiedKFold(n_splits=5, n_repeats=5) on all 65 sessions
| Model | Accuracy | Precision | Recall | F1 | FPR |
|---|---|---|---|---|---|
| Random Forest | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 1.000 ± 0.000 | 0.000 ± 0.000 |
| SVM (RBF) | 0.945 ± 0.041 | 0.929 ± 0.090 | 0.944 ± 0.090 | 0.929 ± 0.051 | 0.055 ± 0.071 |

## 6. Most important Random Forest features (impurity-based)

| Feature | Category | Importance |
|---|---|---|
| `directive_word_count` | content | 0.118 |
| `tools_list_resp_size_max` | structural | 0.111 |
| `second_person_count` | content | 0.108 |
| `model_address_count` | content | 0.104 |
| `tool_name_mentions` | content | 0.104 |
| `size_max` | structural | 0.084 |
| `uppercase_word_count` | content | 0.063 |
| `max_desc_param_ratio` | content | 0.041 |
| `desc_words_max` | content | 0.034 |
| `desc_len_std` | content | 0.028 |

Plot: `feature_importance_rf.png`

## 7. Interpretation and limitations
* **Closed-world benign metadata.** The four benign servers always advertise the same tool descriptions, so *any* change to `tools/list` (size, wording) separates the classes. Several single features do so perfectly on this data (see docs/ml.md). High scores here mostly reflect this; they do not show that the detector would work on real, varied MCP servers.
* **Small sample.** 65 sessions; the test split has 20 and each held-out style only 5 attacks. One misclassification changes recall by 0.2. Confidence intervals are wide.
* **One attack family, five templates written by the same authors.** No evidence about other families or paraphrased payloads.
* **Behaviour alone sees only successful attacks.** The poisoned-tool attempt is a metadata event; behavioural traces exist only when the agent obeyed (the extra canary call).
* **Lexicon bias.** Content lexicons were written by people who knew the payloads.
* **No model ranking.** Differences between RF and SVM are within what a different split could change; no statistical test supports calling either one better.
