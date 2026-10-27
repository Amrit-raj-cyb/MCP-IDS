# Task-grouped feature-group ablation: `/lab/data/phase9_081_ml`

GroupKFold(n_splits=5) on task_id over 6 tasks, pooled out-of-fold predictions, seed 42.

| Features | # | Random Forest F1 / FPR | SVM (RBF) F1 / FPR | XGBoost F1 / FPR | RF + XGBoost (soft vote) F1 / FPR |
|---|---:|---|---|---|---|
| all | 65 | 0.80 / 0.00 | 0.76 / 0.08 | 0.80 / 0.00 | 0.80 / 0.00 |
| all (no signatures) | 63 | 0.80 / 0.00 | 0.72 / 0.18 | 0.80 / 0.00 | 0.80 / 0.00 |
| structural | 26 | 0.42 / 0.24 | 0.56 / 0.24 | 0.46 / 0.08 | 0.47 / 0.08 |
| structural (no signatures) | 25 | 0.45 / 0.13 | 0.56 / 0.30 | 0.51 / 0.08 | 0.52 / 0.08 |
| behavioral | 19 | 0.45 / 0.34 | 0.55 / 0.51 | 0.51 / 0.51 | 0.51 / 0.51 |
| behavioral (no signatures) | 19 | 0.45 / 0.34 | 0.55 / 0.51 | 0.51 / 0.51 | 0.51 / 0.51 |
| content | 20 | 0.80 / 0.00 | 0.73 / 0.17 | 0.80 / 0.00 | 0.80 / 0.00 |
| content (no signatures) | 19 | 0.80 / 0.00 | 0.73 / 0.17 | 0.80 / 0.00 | 0.80 / 0.00 |
| structural+behavioral | 45 | 0.56 / 0.30 | 0.59 / 0.49 | 0.46 / 0.08 | 0.47 / 0.08 |
| structural+behavioral (no signatures) | 44 | 0.57 / 0.27 | 0.57 / 0.54 | 0.46 / 0.08 | 0.47 / 0.08 |
