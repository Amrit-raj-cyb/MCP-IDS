# Task-grouped feature-group ablation: `data/combined_canonical_20261010_ml`

GroupKFold(n_splits=5) on task_id over 42 tasks, pooled out-of-fold predictions, seed 42.

| Features | # | Random Forest F1 / FPR | SVM (RBF) F1 / FPR | XGBoost F1 / FPR | RF + XGBoost (soft vote) F1 / FPR | Decision Tree F1 / FPR | 1-D CNN F1 / FPR |
|---|---:|---|---|---|---|---|---|
| all | 65 | 0.71 / 0.00 | 0.79 / 0.00 | 0.79 / 0.00 | 0.79 / 0.00 | 0.80 / 0.00 | 0.72 / 0.03 |
| all (no signatures) | 63 | 0.71 / 0.00 | 0.79 / 0.00 | 0.79 / 0.00 | 0.80 / 0.00 | 0.80 / 0.00 | 0.77 / 0.01 |
| structural | 26 | 0.22 / 0.00 | 0.11 / 0.16 | 0.26 / 0.00 | 0.25 / 0.00 | 0.20 / 0.00 | 0.13 / 0.07 |
| structural (no signatures) | 25 | 0.25 / 0.00 | 0.44 / 0.17 | 0.25 / 0.00 | 0.24 / 0.00 | 0.28 / 0.00 | 0.49 / 0.07 |
| behavioral | 19 | 0.11 / 0.25 | 0.10 / 0.24 | 0.11 / 0.24 | 0.11 / 0.24 | 0.22 / 0.26 | 0.11 / 0.23 |
| behavioral (no signatures) | 19 | 0.11 / 0.25 | 0.10 / 0.24 | 0.11 / 0.24 | 0.11 / 0.24 | 0.22 / 0.26 | 0.11 / 0.23 |
| content | 20 | 0.80 / 0.00 | 0.72 / 0.03 | 0.80 / 0.00 | 0.80 / 0.00 | 0.80 / 0.00 | 0.72 / 0.04 |
| content (no signatures) | 19 | 0.80 / 0.00 | 0.72 / 0.03 | 0.80 / 0.00 | 0.80 / 0.00 | 0.80 / 0.00 | 0.73 / 0.03 |
| structural+behavioral | 45 | 0.19 / 0.00 | 0.19 / 0.10 | 0.21 / 0.01 | 0.22 / 0.00 | 0.22 / 0.02 | 0.20 / 0.13 |
| structural+behavioral (no signatures) | 44 | 0.18 / 0.00 | 0.34 / 0.11 | 0.21 / 0.01 | 0.21 / 0.00 | 0.26 / 0.01 | 0.41 / 0.07 |
