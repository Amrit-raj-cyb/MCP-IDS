# Task-grouped feature-group ablation: `data/combined_sampling_20261010_ml`

GroupKFold(n_splits=5) on task_id over 42 tasks, pooled out-of-fold predictions, seed 42.

| Features | # | Random Forest F1 / FPR | SVM (RBF) F1 / FPR | XGBoost F1 / FPR | RF + XGBoost (soft vote) F1 / FPR | Decision Tree F1 / FPR | 1-D CNN F1 / FPR |
|---|---:|---|---|---|---|---|---|
| all | 65 | 0.80 / 0.00 | 0.78 / 0.00 | 0.80 / 0.00 | 0.80 / 0.00 | 0.75 / 0.00 | 0.73 / 0.04 |
| all (no signatures) | 63 | 0.80 / 0.00 | 0.78 / 0.00 | 0.80 / 0.00 | 0.80 / 0.00 | 0.75 / 0.00 | 0.77 / 0.01 |
| structural | 26 | 0.31 / 0.00 | 0.32 / 0.22 | 0.33 / 0.01 | 0.34 / 0.00 | 0.19 / 0.00 | 0.33 / 0.14 |
| structural (no signatures) | 25 | 0.37 / 0.00 | 0.49 / 0.21 | 0.39 / 0.01 | 0.41 / 0.00 | 0.27 / 0.00 | 0.48 / 0.14 |
| behavioral | 19 | 0.13 / 0.26 | 0.13 / 0.27 | 0.17 / 0.28 | 0.17 / 0.29 | 0.12 / 0.31 | 0.22 / 0.31 |
| behavioral (no signatures) | 19 | 0.13 / 0.26 | 0.13 / 0.27 | 0.17 / 0.28 | 0.17 / 0.29 | 0.12 / 0.31 | 0.22 / 0.31 |
| content | 20 | 0.80 / 0.00 | 0.72 / 0.05 | 0.80 / 0.00 | 0.80 / 0.00 | 0.79 / 0.00 | 0.73 / 0.05 |
| content (no signatures) | 19 | 0.80 / 0.00 | 0.72 / 0.05 | 0.80 / 0.00 | 0.80 / 0.00 | 0.79 / 0.00 | 0.73 / 0.05 |
| structural+behavioral | 45 | 0.31 / 0.00 | 0.41 / 0.20 | 0.28 / 0.01 | 0.29 / 0.00 | 0.17 / 0.00 | 0.25 / 0.15 |
| structural+behavioral (no signatures) | 44 | 0.31 / 0.00 | 0.40 / 0.21 | 0.28 / 0.01 | 0.29 / 0.00 | 0.17 / 0.00 | 0.29 / 0.09 |
