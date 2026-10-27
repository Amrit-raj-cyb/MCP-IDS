# Experiments

`exp_001_try6_baseline` below is the historical Phase 6 proof-of-concept run.
**The current headline experiment is `exp_017_combined_canonical_20261010`** (2026-10-10, last
section): 2,220 sessions, seven tuned models, nested task-grouped CV; best model RF + XGBoost,
F1 0.796 [0.33, 1.00], false-positive rate 0.2 %. Earlier sections are kept as a dated log.

Each experiment has its own folder `experiments/<experiment_id>/`, written
automatically by `python -m ml.evaluate`:

| File | Content |
|---|---|
| `config.json` | experiment ID, dataset path + SHA-256, feature dir, model dir, split (seed, sizes, class counts), model parameters and pipeline steps, feature count, library versions |
| `metrics.json` | all results: `headline` (task-grouped CV with 95 % CIs), train and test metrics **kept separate**, per-style recall, holdout folds, ablation, CV, grouped CV, duplicate check, benign-only anomaly detection, latency, feature importance |
| `notes.md` | pointer to the full report and the small-dataset caveat |

The full human-readable report is `results/<run>/evaluation_report.md`.

## exp_001_try6_baseline

| Item | Value |
|---|---|
| Date | 2026-10-03 |
| Dataset | `data/try6` (Phase 6, read-only), SHA-256 `0784a0f9…7337` |
| Sessions | 65: 40 benign, 25 `poisoned_tool` (5 styles × 5); 11 attacks influenced the mock agent |
| Features | 62 (25 structural, 18 behavioural, 19 content), `neutralize()` applied; `data/try6_ml/` |
| Split | stratified on label, `test_size=0.3`, seed 42 → train 45 (28/17), test 20 (12/8) |
| Models | Random Forest (300 trees, balanced) and SVM (RBF, C=1, balanced, standardized); shared imputer |
| Tuning | none |
| Library versions | Python 3.12.6, scikit-learn 1.9.1, numpy 2.5.3, pandas 3.0.6, joblib 1.6.0 |
| Outputs | `models/try6/`, `results/try6/`, `experiments/exp_001_try6_baseline/` |

### Results
| Experiment | Random Forest | SVM |
|---|---|---|
| Train (n=45): F1 / FPR | 1.000 / 0.000 | 1.000 / 0.000 |
| **Test (n=20): F1 / FPR** | 1.000 / 0.000 | 1.000 / 0.000 |
| 5×5 CV: F1 (mean ± std) / FPR | 1.000 ± 0.000 / 0.000 | 0.930 ± 0.051 / 0.055 ± 0.071 |
| Holdout `param` style: recall / FPR | **0.00** / 0.00 | 0.80 / 0.08 |
| Holdout other 4 styles: recall / FPR | 1.00 / 0.00 each | 0.80–1.00 / 0.08 each |
| Behavioural features only: recall / FPR | 0.88 / 0.67 | 0.75 / 0.75 |
| Model-only latency (median) | ≈ 25–30 ms | ≈ 3 ms |

### Observations
1. Perfect baseline scores are explained by a **closed-world effect**: benign
   tool metadata never varies in this lab, so four single features already
   separate the classes perfectly.
2. The **payload-style holdout** is the informative result: an instruction
   placed in a *parameter* description (`param`) is invisible to an RF trained
   only on description-placed payloads.
3. **Behaviour alone** detects poorly; poisoned-tool attempts are visible
   mainly in metadata (content + `tools/list` size).
4. The **server-count confound** exists but is weak on its own (accuracy 0.45
   vs 0.60 majority).
5. The baseline test set contained no `param` or `tagged` attacks (label-only
   stratification).

### Limitations
This experiment demonstrates the functionality of the ML pipeline, but the
dataset is too small to establish strong real-world generalization. One
family, five author-written templates, constant benign metadata, mock agent,
20 test sessions. See [ml.md](ml.md#limitations).

### Reproduce
```bash
python -m features.extractor --data-dir data/try6 --out data/try6_ml
python -m ml.train --features data/try6_ml --models models/try6 --seed 42 --test-size 0.3
python -m ml.evaluate --features data/try6_ml --models models/try6 --results results/try6 --experiment-id exp_001_try6_baseline
```
All metrics except latency are deterministic for the same dataset, seed and
library versions.

## exp_003_phase9_081

| Item | Value |
|---|---|
| Date | 2026-10-04 |
| Dataset | `data/phase9_081_targeted` (lab 0.8.1), 180 sessions; 90 benign and 30 per each of three attack families |
| Attack outcome counts | 49 succeeded / 41 not succeeded: poisoned-tool 10/30; sampling protocol 30/30; shadowing 9/30 |
| Dataset SHA-256 | `055c758b…e22f38`; derived feature data hash `f0fd05d2…4415728e` |
| Traffic verification | 180/180 OK; 6,334 log events (4,222 MCP events); 30 `sampling/createMessage` requests and 30 responses |
| Server-count balance | benign = attack: 1 server 8, 2 servers 37, 6 servers 45 |
| Features | 65 (26 structural, 19 behavioural, 20 content); `neutralize()` applied |
| Split | Stratified on `label+attack_family`, seed 42, test size 0.30: train 126 (63/63), test 54 (27/27) |
| Models | RF 300 trees / balanced; SVM RBF / C=1 / balanced / scaled; no test tuning |
| Outputs | `data/phase9_081_ml/`, `models/phase9_081/`, `results/phase9_081/` |

### Results

| Model | Train accuracy / F1 / FPR | Test accuracy / precision / recall / F1 / FPR | Test confusion TN/FP/FN/TP | Median model latency |
|---|---|---|---|---:|
| Random Forest | 1.000 / 1.000 / 0.000 | 1.000 / 1.000 / 1.000 / 1.000 / 0.000 | 27/0/0/27 | 26.972 ms |
| SVM | 1.000 / 1.000 / 0.000 | 1.000 / 1.000 / 1.000 / 1.000 / 0.000 | 27/0/0/27 | 3.468 ms |

The train/test baseline is perfect, but this must be read with the holdout
results and limitations. Hold-one-family-out recall (FPR was zero for all
folds):

| Held-out family | RF recall | SVM recall |
|---|---:|---:|
| `poisoned_tool` | 0.433 | 0.000 |
| `sampling_injection` | 0.000 | 0.000 |
| `shadowing` | 1.000 | 1.000 |

RF missed the held-out `param` payload style (0.000 recall); other held-out
styles scored 1.000. Repeated 5×5 CV F1: RF `1.000 ± 0.000`; SVM
`0.996 ± 0.010`. These results show proof-of-functionality on a small,
repeated, closed-world lab dataset and do not establish real-world detection.
Fixed benign descriptions, author/template bias, and the mock agent are major
limitations. Sampling success means a simulated protocol exchange completed,
not that a real model was influenced. See [ml.md](ml.md#current-multi-family-run-exp_003_phase9_081).

### Reproduce

```bash
docker compose build
docker compose run --rm lab python -m scripts.generate_phase9 --output /lab/data/phase9_081_targeted --seed 9000 --parallel 4 --sessions-per-family 30
docker compose run --rm lab python -m scripts.generate_phase9 --output /lab/data/phase9_081_targeted --verify-only
docker compose run --rm lab python -m features.extractor --data-dir /lab/data/phase9_081_targeted --out /lab/data/phase9_081_ml
docker compose run --rm lab python -m ml.train --features /lab/data/phase9_081_ml --models /lab/models/phase9_081 --seed 42 --test-size 0.3
docker compose run --rm lab python -m ml.evaluate --features /lab/data/phase9_081_ml --models /lab/models/phase9_081 --results /lab/results/phase9_081 --experiment-id exp_003_phase9_081
```

## exp_004_phase9_081_rerun_20261006 and held-out benign evaluation

| Item | Value |
|---|---|
| Date | 2026-10-06 |
| Rerun | `exp_003` re-run from scratch in Docker: `data/phase9_081_ml_rerun_20261006/`, `models/phase9_081_rerun_20261006/`, `results/phase9_081_rerun_20261006/` |
| Rerun result | all shared metrics identical to `exp_003` (excluding timing/paths); new sections `baseline_duplicates`, `grouped_cv` |
| Held-out benign data | `data/benign_unique_081` (200 benign sessions, 22 tasks, 44 scenarios, lab 0.8.1, Docker); features `data/benign_unique_081_ml/` |
| External evaluation | `results/benign_unique_081_eval/`, `results/phase9_081_cross_model_eval/` |

| Model | FP on 200 unseen benign | FPR (95 % CI) |
|---|---|---|
| `exp_003` RF | 1 | 0.005 (0.001–0.028) |
| `exp_003` SVM | 93 | 0.465 (0.397–0.534) |
| try6 RF | 0 | 0.000 (0.000–0.019) |

Observation: the SVM's perfect `exp_003` test score did not transfer to
unseen benign tasks; the RF did. See [ml.md](ml.md#held-out-unique-benign-corpus-2026-10-06-does-anything-change).

### Reproduce
```bash
docker compose build
docker compose run --rm lab python -m features.extractor --data-dir /lab/data/phase9_081_targeted --out /lab/data/phase9_081_ml_rerun_20261006
docker compose run --rm lab python -m ml.train --features /lab/data/phase9_081_ml_rerun_20261006 --models /lab/models/phase9_081_rerun_20261006 --seed 42 --test-size 0.3
docker compose run --rm lab python -m ml.evaluate --features /lab/data/phase9_081_ml_rerun_20261006 --models /lab/models/phase9_081_rerun_20261006 --results /lab/results/phase9_081_rerun_20261006 --experiment-id exp_004_phase9_081_rerun_20261006
docker compose run --rm lab python -m scripts.generate_benign_corpus --output /lab/data/benign_unique_081
docker compose run --rm lab python -m features.extractor --data-dir /lab/data/benign_unique_081 --out /lab/data/benign_unique_081_ml
python -m ml.evaluate_external --features data/benign_unique_081_ml --model models/phase9_081/random_forest.joblib --model models/phase9_081/svm.joblib --model models/try6/random_forest.joblib --results results/benign_unique_081_eval
```

## exp_005_combined_p9_benign090 (lab 0.9.0) and wording-robustness test

| Item | Value |
|---|---|
| Training data | `data/combined_p9_benign090`: `phase9_081_targeted` (180) + `benign_unique_090` (634) = 814 sessions (90 attack / 724 benign), `verify` consistent; `composition.json` lists source hashes |
| Features | `data/combined_p9_benign090_ml/` (65 features) |
| Split | stratified on label+family, seed 42, test 0.30: train 569 (506/63), test 245 (218/27) |
| Outputs | `models/combined_p9_benign090/`, `results/combined_p9_benign090/`, `experiments/exp_005_combined_p9_benign090/` |
| Robustness test | `data/benign_varied_090` (317) → `results/benign_varied_090_eval/` |

Results: see [ml.md](ml.md#lab-090-more-benign-variety-retraining-and-a-wording-robustness-test).
Headline: task-grouped SVM FPR 7.8 % → 1.7 %; but every model flags all
benign sessions whose descriptions use second-person prose.

### Reproduce
```bash
docker compose build
docker compose run --rm lab python -m scripts.generate_benign_corpus --output /lab/data/benign_unique_090
docker compose run --rm lab python -m scripts.generate_benign_corpus --output /lab/data/benign_varied_090 --server-mix all --description-variant cycle
python -m scripts.compose_dataset --source data/phase9_081_targeted --source data/benign_unique_090 --output data/combined_p9_benign090
docker compose run --rm lab python -m features.extractor --data-dir /lab/data/combined_p9_benign090 --out /lab/data/combined_p9_benign090_ml
docker compose run --rm lab python -m ml.train --features /lab/data/combined_p9_benign090_ml --models /lab/models/combined_p9_benign090 --seed 42 --test-size 0.3
docker compose run --rm lab python -m ml.evaluate --features /lab/data/combined_p9_benign090_ml --models /lab/models/combined_p9_benign090 --results /lab/results/combined_p9_benign090 --experiment-id exp_005_combined_p9_benign090
docker compose run --rm lab python -m features.extractor --data-dir /lab/data/benign_varied_090 --out /lab/data/benign_varied_090_ml
docker compose run --rm lab python -m ml.evaluate_external --features /lab/data/benign_varied_090_ml --model /lab/models/phase9_081/random_forest.joblib --model /lab/models/phase9_081/svm.joblib --model /lab/models/combined_p9_benign090/random_forest.joblib --model /lab/models/combined_p9_benign090/svm.joblib --results /lab/results/benign_varied_090_eval
```

## exp_006_expanded_20261006 and exp_007_phase9_expanded_20261006

Both experiments use lab 0.9.0, Python 3.12.15 in Docker, feature extractor
1.0, fixed model seed 42, and the existing RF/SVM pipeline.

| Experiment | Data | Split | Result summary |
|---|---|---|---|
| `exp_006_expanded_20261006` | `data/combined_expanded_20261006`: 1,354 sessions (994 benign / 360 attack), 65 features, 31,388 wire events | 70/30, stratified label+family; train 947, test 407 | Both models: random-split test F1 1.000; task-grouped CV RF F1 0.780, SVM 0.759; both miss sampling. 185/407 test rows duplicate training vectors. |
| `exp_007_phase9_expanded_20261006` | `data/phase9_expanded_20261006`: 720 matched sessions (360 / 360), 120 attacks per family, 65 features | 70/30, stratified label+family; train 504, test 216 | Both random-split test F1 1.000; task-grouped RF recall 0.667/FPR 0.000, SVM recall 0.667/FPR 0.053; both miss sampling. |

The family-holdout result is the key limitation: in exp_006, poisoned-tool
and sampling-injection recall are 0 for both models; shadowing recall is
0.650 RF / 1.000 SVM. In exp_007, sampling recall is 0, poisoned-tool is
0.425 RF / 0 SVM, and shadowing is 1.000 for both. Do not report the random
split scores alone as generalization evidence.

External checks of the paired-only exp_007 models found 396/634 (62.5%) RF and
496/634 (78.2%) SVM false alarms on the new reworded benign corpus; on the
canonical benign corpus the rates were 3/634 (0.5%) and 255/634 (40.2%). The
reworded corpus was not used for this paired-only training. The exp_006 combined
models have zero false alarms on the existing canonical and prose corpora, but
those checks share tasks and include 43/634 and 70/317 exact feature-vector
copies respectively; they are not independent real-world validation.

Dataset generation seeds: benign plan search base 70000 (`search=2000`), Phase
9 seed 90000 and 120 sessions/family; both generators used Docker concurrency 4.
Model split seed 42, test size 0.30. Source dataset SHA-256 values and full
configs are preserved in each dataset's metadata/config files and
`data/combined_expanded_20261006/composition.json`.

### Reproduce the expanded collections and combined model
```bash
docker compose run --rm lab python -m scripts.generate_benign_corpus --output /lab/data/benign_varied_090_expanded_20261006 --seed-base 70000 --search 2000 --parallel 4 --server-mix both --description-variant cycle
docker compose run --rm lab python -m scripts.generate_phase9 --output /lab/data/phase9_expanded_20261006 --seed 90000 --parallel 4 --sessions-per-family 120
docker compose run --rm lab python -m scripts.compose_dataset --source /lab/data/phase9_expanded_20261006 --source /lab/data/benign_varied_090_expanded_20261006 --output /lab/data/combined_expanded_20261006
docker compose run --rm lab python -m features.extractor --data-dir /lab/data/combined_expanded_20261006 --out /lab/data/expanded_20261006_ml
docker compose run --rm lab python -m ml.train --features /lab/data/expanded_20261006_ml --models /lab/models/expanded_20261006 --seed 42 --test-size 0.3
docker compose run --rm lab python -m ml.evaluate --features /lab/data/expanded_20261006_ml --models /lab/models/expanded_20261006 --results /lab/results/expanded_20261006 --experiment-id exp_006_expanded_20261006 --experiments-dir /lab/experiments
```

The matched-only `exp_007` analysis and external benign checks can be recreated
from the generated sources as follows:
```bash
docker compose run --rm lab python -m features.extractor --data-dir /lab/data/phase9_expanded_20261006 --out /lab/data/phase9_expanded_20261006_ml
docker compose run --rm lab python -m ml.train --features /lab/data/phase9_expanded_20261006_ml --models /lab/models/phase9_expanded_20261006 --seed 42 --test-size 0.3
docker compose run --rm lab python -m ml.evaluate --features /lab/data/phase9_expanded_20261006_ml --models /lab/models/phase9_expanded_20261006 --results /lab/results/phase9_expanded_20261006 --experiment-id exp_007_phase9_expanded_20261006 --experiments-dir /lab/experiments
docker compose run --rm lab python -m features.extractor --data-dir /lab/data/benign_varied_090_expanded_20261006 --out /lab/data/benign_varied_090_expanded_20261006_ml
docker compose run --rm lab python -m ml.evaluate_external --features /lab/data/benign_varied_090_expanded_20261006_ml --model /lab/models/phase9_expanded_20261006/random_forest.joblib --model /lab/models/phase9_expanded_20261006/svm.joblib --results /lab/results/phase9_expanded_20261006_external_varied
```

## Re-run 2026-10-07: task-grouped headline, confidence intervals, anomaly detection

`exp_003`, `exp_006` and `exp_007` were re-evaluated with the updated
`ml.evaluate` (same models, data and seed). Every previously saved metric is
identical apart from timing; the reports now start with the task-grouped
headline and its 95 % task-bootstrap intervals, and include sections 5a
(duplicates), 5b (grouped CV) and 5c (benign-only anomaly detection). Results:
[ml.md](ml.md#headline-protocol-confidence-intervals-and-benign-only-anomaly-detection-2026-10-07).

```bash
docker compose build
docker compose run --rm lab python -m ml.evaluate --features /lab/data/phase9_081_ml --models /lab/models/phase9_081 --results /lab/results/phase9_081 --experiment-id exp_003_phase9_081 --experiments-dir /lab/experiments
docker compose run --rm lab python -m ml.evaluate --features /lab/data/phase9_expanded_20261006_ml --models /lab/models/phase9_expanded_20261006 --results /lab/results/phase9_expanded_20261006 --experiment-id exp_007_phase9_expanded_20261006 --experiments-dir /lab/experiments
docker compose run --rm lab python -m ml.evaluate --features /lab/data/expanded_20261006_ml --models /lab/models/expanded_20261006 --results /lab/results/expanded_20261006 --experiment-id exp_006_expanded_20261006 --experiments-dir /lab/experiments
```
From Git Bash on Windows, set `MSYS_NO_PATHCONV=1` first, otherwise `/lab/...`
arguments are rewritten to Windows paths.

## Added models 2026-10-08: XGBoost and RF + XGBoost

`exp_003`, `exp_006` and `exp_007` now also evaluate XGBoost and the RF +
XGBoost soft-voting ensemble (see [ml.md](ml.md#phases-1112-models)). The new
models were added to the existing model folders without retraining RF/SVM
(`--only`; the split is recomputed and must equal `split.json`). Every
experiment in `ml.evaluate` (headline grouped CV, holdouts, ablation, repeated
CV, duplicate check) now runs all four models; RF/SVM numbers are unchanged.
Previous outputs were backed up before overwriting.

```bash
docker compose build
docker compose run --rm lab python -m ml.train --features /lab/data/phase9_081_ml --models /lab/models/phase9_081 --seed 42 --test-size 0.3 --only xgboost rf_xgb
docker compose run --rm lab python -m ml.train --features /lab/data/phase9_expanded_20261006_ml --models /lab/models/phase9_expanded_20261006 --seed 42 --test-size 0.3 --only xgboost rf_xgb
docker compose run --rm lab python -m ml.train --features /lab/data/expanded_20261006_ml --models /lab/models/expanded_20261006 --seed 42 --test-size 0.3 --only xgboost rf_xgb
docker compose run --rm lab python -m ml.evaluate --features /lab/data/phase9_081_ml --models /lab/models/phase9_081 --results /lab/results/phase9_081 --experiment-id exp_003_phase9_081 --experiments-dir /lab/experiments
docker compose run --rm lab python -m ml.evaluate --features /lab/data/phase9_expanded_20261006_ml --models /lab/models/phase9_expanded_20261006 --results /lab/results/phase9_expanded_20261006 --experiment-id exp_007_phase9_expanded_20261006 --experiments-dir /lab/experiments
docker compose run --rm lab python -m ml.evaluate --features /lab/data/expanded_20261006_ml --models /lab/models/expanded_20261006 --results /lab/results/expanded_20261006 --experiment-id exp_006_expanded_20261006 --experiments-dir /lab/experiments
```
For a new dataset, plain `python -m ml.train` (without `--only`) trains all
four models.

External benign checks were re-run with all four models of each folder
(`results/*_external_*`, `results/benign_unique_081_eval` on the host,
`results/benign_varied_090_eval`); the task-grouped ablation for every model is
reproduced with:
```bash
docker compose run --rm lab python -m scripts.grouped_ablation --features /lab/data/phase9_081_ml --out /lab/results/phase9_081/grouped_ablation.json
docker compose run --rm lab python -m scripts.grouped_ablation --features /lab/data/phase9_expanded_20261006_ml --out /lab/results/phase9_expanded_20261006/grouped_ablation.json
docker compose run --rm lab python -m scripts.grouped_ablation --features /lab/data/expanded_20261006_ml --out /lab/results/expanded_20261006/grouped_ablation.json
python -m scripts.plot_model_comparison --out results/model_comparison_20261008.png
```
Results: [ml.md](ml.md#xgboost-and-rf--xgboost-ensemble-results-2026-10-08).

## exp_008_expanded_20261008: full re-run on the largest dataset (2026-10-08)

Project-wide audit and retraining on the largest available dataset,
`data/combined_expanded_20261006/` (1,354 sessions). All outputs go to new
folders; nothing earlier was overwritten.

| Step | Result |
|---|---|
| `orchestrator.main verify` | 1,354 manifest entries consistent with the logs |
| Feature re-extraction → `data/expanded_20261008_ml/` | `features.csv` and `feature_schema.json` byte-identical to `data/expanded_20261006_ml/` |
| `ml.train` (all four models, from scratch) → `models/expanded_20261008/` | every model's predictions on all 1,354 sessions identical to `models/expanded_20261006/` |
| `ml.evaluate` → `results/expanded_20261008/`, `experiments/exp_008_expanded_20261008/` | every metric identical to exp_006 (timing excluded); headline grouped F1: RF 0.780, SVM 0.759, XGBoost 0.800, RF + XGBoost 0.800 |
| `scripts.grouped_ablation` | identical to exp_006 |
| External benign checks (`results/expanded_20261008_external_{original,prose,unique}`) | 0 false alarms for all four models on 634 / 317 / 200 sessions (43 / 70 / 25 rows are exact training copies; all tasks occur in training) |

```bash
docker compose run --rm lab python -m orchestrator.main --data-dir /lab/data/combined_expanded_20261006 verify
docker compose run --rm lab python -m features.extractor --data-dir /lab/data/combined_expanded_20261006 --out /lab/data/expanded_20261008_ml
docker compose run --rm lab python -m ml.train --features /lab/data/expanded_20261008_ml --models /lab/models/expanded_20261008 --seed 42 --test-size 0.3
docker compose run --rm lab python -m ml.evaluate --features /lab/data/expanded_20261008_ml --models /lab/models/expanded_20261008 --results /lab/results/expanded_20261008 --experiment-id exp_008_expanded_20261008 --experiments-dir /lab/experiments
docker compose run --rm lab python -m scripts.grouped_ablation --features /lab/data/expanded_20261008_ml --out /lab/results/expanded_20261008/grouped_ablation.json
```

Audit findings: static checks (`compileall`, `ruff` with pyflakes, bugbear,
pylint-error and security rules) found no bugs (the SQL-string warnings in the
SQLite server are on allow-listed table and column names). One bug was found
and fixed: the live detector reported a probability ("confidence") only for
models named `random_forest`, so XGBoost and RF + XGBoost alerts showed none;
it now uses `ml.models.is_probabilistic` (regression test in
`tests/test_detector.py`). The complete test suite, including the slow
all-task integration test that used to be deselected (it completes in about
150 s), passes in Docker (193 passed, 1 skipped after the later default-model test) and on the Windows host.

### Why unseen families are missed (feature evidence, 2026-10-08)

```bash
docker compose run --rm lab python -m scripts.holdout_feature_analysis --features /lab/data/phase9_081_ml --features /lab/data/phase9_expanded_20261006_ml --features /lab/data/expanded_20261008_ml --out /lab/results/expanded_20261008/holdout_feature_analysis.md
```
Repeats the family holdout for RF and XGBoost and reports the features each relies
on. Sampling: `server_initiated_request_count` is constant (0) in every training
fold that excludes sampling, so it cannot be learned. Poisoning: on the 180/720
sets 80–100% of poisoned sessions exceed every benign session on description
spread, longest description, directive words and second-person address, so a
shadowing-trained model still catches them (XGBoost 0.80); the 634 reworded
benign sessions of the 1,354 set cover that range (0–40% exceed), the models fall
back on shadowing's description-to-parameter ratio, and recall drops to 0. Used
in the papers (conference Table VIII, report Section 12.5).

## exp_009–exp_011: Decision Tree and 1-D CNN added (2026-10-09)

Two models were added to every experiment: a **Decision Tree** (CART, class-balanced) and a
**1-D CNN** over the 65 standardised features (PyTorch, `ml/cnn.py`). All six models were
trained on the three datasets into new folders (`models/*_20261009`, `results/*_20261009`,
`experiments/exp_009…exp_011`), on the Windows host venv with the same pinned library versions
as the lab image; the four existing models reproduced their earlier Docker numbers exactly.

| Dataset | Decision Tree F1 (task-grouped) | 1-D CNN F1 (task-grouped) |
|---|---|---|
| Main (180) | 0.800 [0.35, 1.00] | 0.800 [0.35, 1.00] |
| Matched (720) | 0.800 [0.33, 1.00] | 0.800 [0.33, 1.00] |
| Combined (1,354) | 0.749 [0.24, 1.00] | 0.773 [0.30, 0.99] |

The 1-D CNN generalised best to unseen poisoning wording (held-out padded and polite styles
1.00, XGBoost 0.00). On the 200 held-out benign sessions the 180-session models raised 3
(Decision Tree) and 7 (1-D CNN) false alarms; Random Forest 1, SVM 93.

## 2026-10-10: tuning, raw-traffic CNN, benign sampling servers, task-grouped split

Four changes, each motivated by a finding, all evaluated with **nested** task-grouped CV:

| Change | Code | Why |
|---|---|---|
| Hyperparameter tuning of every model on training tasks only | `ml/tuning.py`, `ml.train --tune`, `ml.evaluate --nested-tuning` | settings were library defaults |
| Raw-traffic CNN: byte-level CNN over the masked wire messages | `ml/raw.py`, `ml/raw_cnn.py` | no hand-made features |
| Benign servers that legitimately use MCP sampling (`writing_assistant`, `helpdesk`), 4 benign-only tasks, lab 0.9.1 | `servers/benign/*`, `agent/tasks.py`, `orchestrator/scenarios.py` | before, only the attack ever sampled |
| Task-grouped baseline train/test split | `ml/train.py --split task-grouped` (default) | the random split had 185 of 407 test sessions copied from training |

Not changed: the attack scenarios. All 120 sampling attacks still come from one task.

### Datasets (all composed with `scripts.compose_dataset`, verified consistent)

| Dataset | Sessions | Content |
|---|---|---|
| `data/benign_sampling_091` | 232 benign | 4 sampling tasks × 29 distinct plans × 2 server mixes × 4 description wordings |
| `data/combined_sampling_20261010` | 1,586 (1,226 / 360) | `combined_expanded_20261006` + `benign_sampling_091` |
| `data/combined_canonical_20261010` | **2,220 (1,860 / 360)** | the above + `benign_unique_090` (634 benign, original wording) |

### Results (nested task-grouped CV, 5 outer folds, 42 tasks)

| Model | exp_015 (1,586) | exp_016 (1,586, raw-CNN fix) | **exp_017 (2,220, final)** |
|---|---|---|---|
| RF + XGBoost | 0.797 | 0.797 | **0.796** [0.33, 1.00], FPR 0.002 |
| XGBoost | 0.797 | 0.797 | 0.791 [0.33, 1.00], FPR 0.004 |
| Decision Tree | 0.795 | 0.795 | 0.789 [0.33, 1.00], FPR 0.004 |
| SVM | 0.643 | 0.643 | 0.730 [0.26, 0.99], FPR 0.031 |
| Random Forest | 0.800 | 0.800 | 0.710 [0.33, 1.00], FPR 0.000 |
| 1-D CNN | 0.744 | 0.744 | 0.704 [0.24, 0.98], FPR 0.039 |
| Raw-traffic CNN | 0.438 | 0.726 | 0.377 [0.00, 0.88], FPR 0.015 |

Every feature model misses every sampling attack (recall 0); in exp_017 the Random Forest also
misses 35% of shadowing attacks when that task is held out (recall 0.65). Other findings:

* **Split fix.** The saved models' test set is 14 whole unseen tasks. exp_016: 0 of 470 test
  sessions copy a training session (old random split: 185 of 407); exp_017: 19 of 680 share a
  feature vector with a session of a *different* training task, none shares a task.
* **Benign sampling.** The 2026-10-09 models, trained without benign samplers, false-alarmed on
  the 232 new sessions: SVM 103, 1-D CNN 169, the tree models 0
  (`results/benign_sampling_091_eval_20261009_models`). After retraining (exp_017) the tree
  models raise 0 false alarms on the held-out sampling tasks, the SVM 56, the 1-D CNN 71.
* **Raw-CNN bug (fixed between exp_015 and exp_016).** The first version used a stride-4 first
  convolution and memorised byte alignments: shifting a training attack by one byte made it
  undetected (all 40 tested attacks flipped at some 1–7 byte shift). A stride-1 convolution with
  local max pooling and random 0–3 position shifts during training fixed it (0 of 40 flip);
  regression tests in `tests/test_raw_cnn.py`.
* **Wording confound (fixed by exp_017).** In the 1,586-session data every attack used the
  original tool wording while 808 benign sessions used reworded descriptions. The raw CNN learned
  the shortcut: 123 of 200 outside benign sessions (original wording) flagged in exp_016, 0 in
  exp_017. Without the shortcut its F1 falls from 0.726 to 0.377: a negative result for
  byte-level models on 42 tasks of lab traffic.
* **Tuning** changed the Random Forest, SVM, XGBoost, 1-D CNN and raw CNN settings
  (`models/combined_canonical_20261010/tuning.json`); nested results show it does not always
  transfer (exp_017 SVM 0.789 untuned vs 0.730 tuned).
* **Content features carry the detection** (task-grouped ablation, exp_017): content alone
  0.72–0.80, structural alone 0.11–0.26, behavioural alone 0.10–0.22.
* **External benign test** (`results/benign_unique_081_eval_combined_canonical_20261010`): 0
  false alarms for every model on all 200 sessions, 104 of them from tasks the models never
  trained on.

The live detector's default model is now `models/combined_canonical_20261010/rf_xgb.joblib`.
The earlier `models/phase9_081_20261010` (180 sessions, tuned, stratified split, first raw CNN)
and `models/phase9_expanded_20261010` (trained, never evaluated) come from a run that was stopped
when the fixes above were made; treat them as superseded.

### Reproduce (Docker for data, host venv or Docker for ML)

```bash
docker compose build   # lab 0.9.1 image, CPU-only PyTorch (see docker/wheels/README.txt if downloads are slow)
for v in 0 1 2 3; do docker compose run --rm lab python -m scripts.generate_benign_corpus --output /lab/data/benign_sampling_091_v$v --tasks assist_summarize_text,assist_translate_notes,helpdesk_triage_ticket,helpdesk_order_reply --seed-base 80000 --search 2000 --parallel 3 --server-mix both --description-variant $v; done
docker compose run --rm lab python -m scripts.compose_dataset --source /lab/data/benign_sampling_091_v0 --source /lab/data/benign_sampling_091_v1 --source /lab/data/benign_sampling_091_v2 --source /lab/data/benign_sampling_091_v3 --output /lab/data/benign_sampling_091
docker compose run --rm lab python -m scripts.compose_dataset --source /lab/data/combined_expanded_20261006 --source /lab/data/benign_sampling_091 --output /lab/data/combined_sampling_20261010
docker compose run --rm lab python -m scripts.compose_dataset --source /lab/data/combined_sampling_20261010 --source /lab/data/benign_unique_090 --output /lab/data/combined_canonical_20261010
docker compose run --rm lab python -m orchestrator.main --data-dir /lab/data/combined_canonical_20261010 verify
docker compose run --rm lab python -m features.extractor --data-dir /lab/data/combined_canonical_20261010 --out /lab/data/combined_canonical_20261010_ml
python -m ml.train --features data/combined_canonical_20261010_ml --models models/combined_canonical_20261010 --seed 42 --test-size 0.3 --tune
python -m ml.evaluate --features data/combined_canonical_20261010_ml --models models/combined_canonical_20261010 --results results/combined_canonical_20261010 --experiment-id exp_017_combined_canonical_20261010 --nested-tuning
python -m scripts.grouped_ablation --features data/combined_canonical_20261010_ml --out results/combined_canonical_20261010/grouped_ablation.json
python -m ml.evaluate_external --features data/benign_unique_081_ml --results results/benign_unique_081_eval_combined_canonical_20261010 --model models/combined_canonical_20261010/rf_xgb.joblib  # add --model for each of the seven
python -m scripts.plot_model_comparison --run 20261010
```

Runtime on the project laptop: tuned training about 40 minutes, nested evaluation about 8 hours
(the raw CNN dominates). Tests: 225 passed, 2 skipped on the Windows host; 226 passed, 1 skipped
in Docker (2026-10-10).
