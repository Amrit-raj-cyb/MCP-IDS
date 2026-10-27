# Task-grouped feature-group ablation: `/lab/data/phase9_expanded_20261006_ml`

GroupKFold(n_splits=5) on task_id over 6 tasks, pooled out-of-fold predictions, seed 42.

| Features | # | Random Forest F1 / FPR | SVM (RBF) F1 / FPR | XGBoost F1 / FPR | RF + XGBoost (soft vote) F1 / FPR |
|---|---:|---|---|---|---|
| all | 65 | 0.80 / 0.00 | 0.78 / 0.05 | 0.80 / 0.00 | 0.80 / 0.00 |
| all (no signatures) | 63 | 0.80 / 0.00 | 0.78 / 0.05 | 0.80 / 0.00 | 0.80 / 0.00 |
| structural | 26 | 0.59 / 0.21 | 0.64 / 0.42 | 0.48 / 0.04 | 0.48 / 0.04 |
| structural (no signatures) | 25 | 0.48 / 0.04 | 0.62 / 0.47 | 0.54 / 0.04 | 0.54 / 0.04 |
| behavioral | 19 | 0.42 / 0.22 | 0.43 / 0.24 | 0.43 / 0.24 | 0.43 / 0.24 |
| behavioral (no signatures) | 19 | 0.42 / 0.22 | 0.43 / 0.24 | 0.43 / 0.24 | 0.43 / 0.24 |
| content | 20 | 0.80 / 0.00 | 0.73 / 0.17 | 0.80 / 0.00 | 0.80 / 0.00 |
| content (no signatures) | 19 | 0.80 / 0.00 | 0.73 / 0.17 | 0.80 / 0.00 | 0.80 / 0.00 |
| structural+behavioral | 45 | 0.66 / 0.37 | 0.63 / 0.43 | 0.48 / 0.04 | 0.48 / 0.04 |
| structural+behavioral (no signatures) | 44 | 0.59 / 0.21 | 0.63 / 0.43 | 0.48 / 0.04 | 0.48 / 0.04 |
