# Task-grouped feature-group ablation: `/lab/data/expanded_20261008_ml`

GroupKFold(n_splits=5) on task_id over 38 tasks, pooled out-of-fold predictions, seed 42.

| Features | # | Random Forest F1 / FPR | SVM (RBF) F1 / FPR | XGBoost F1 / FPR | RF + XGBoost (soft vote) F1 / FPR |
|---|---:|---|---|---|---|
| all | 65 | 0.78 / 0.00 | 0.76 / 0.00 | 0.80 / 0.00 | 0.80 / 0.00 |
| all (no signatures) | 63 | 0.77 / 0.00 | 0.72 / 0.00 | 0.80 / 0.00 | 0.80 / 0.00 |
| structural | 26 | 0.15 / 0.00 | 0.37 / 0.24 | 0.29 / 0.05 | 0.28 / 0.05 |
| structural (no signatures) | 25 | 0.17 / 0.00 | 0.43 / 0.27 | 0.38 / 0.05 | 0.14 / 0.05 |
| behavioral | 19 | 0.39 / 0.18 | 0.39 / 0.21 | 0.45 / 0.24 | 0.39 / 0.18 |
| behavioral (no signatures) | 19 | 0.39 / 0.18 | 0.39 / 0.21 | 0.45 / 0.24 | 0.39 / 0.18 |
| content | 20 | 0.80 / 0.00 | 0.73 / 0.06 | 0.79 / 0.00 | 0.80 / 0.00 |
| content (no signatures) | 19 | 0.80 / 0.00 | 0.73 / 0.06 | 0.79 / 0.00 | 0.79 / 0.00 |
| structural+behavioral | 45 | 0.00 / 0.00 | 0.37 / 0.21 | 0.15 / 0.05 | 0.15 / 0.05 |
| structural+behavioral (no signatures) | 44 | 0.00 / 0.00 | 0.37 / 0.21 | 0.15 / 0.05 | 0.15 / 0.05 |
