# ML Model Quality and Detection Validation

## Scope and reproducibility

This report measures the existing experimental Isolation Forest on the checked-in synthetic benchmark only. It does not report production performance. Snapshot-mode datasets have no trustworthy ground-truth event labels, so their results remain separate and are limited to score distributions and anomaly rates.

Reproduce the fixed-threshold experiment and quality analysis from the repository root:

```sh
cd backend
PYTHONPATH=. ../.venv312/bin/python -m scripts.run_ml_experiment \
  --synthetic-benchmark \
  --fixture scripts/reports/synthetic_events.csv \
  --output-dir /private/tmp/ueba-quality-benchmark \
  --contamination 0.05 --random-state 42 --n-estimators 100

PYTHONPATH=. ../.venv312/bin/python -m scripts.analyze_ml_quality \
  --fixture scripts/reports/synthetic_events.csv \
  --output /private/tmp/ueba_ml_quality.json
```

Fixture SHA-256: `4ca8bf982e39ff911a3aec05a82ccb8ab356e2e0982f629f5cdec719a6f58a8e`. The current evaluator makes a chronological unique-timestamp 70/15/15 split: 1,077 train rows, 220 validation rows, and 218 test rows. It fits preprocessing and Isolation Forest on train rows only. Synthetic scenario labels are not passed to fit. Validation labels are used only in the explicitly marked threshold-selection experiments below; test labels are used only for final evaluation after the threshold has been selected.

The source generator creates five users, each with 4–6 normal events/day and slightly different normal UTC activity windows: users 1 and 4 around 09:00–18:00, users 2 and 5 around 10:00–19:00, and user 3 around 08:00–17:00. It injects unfamiliar-IP and unusual-hour examples only on later days. Therefore, this is a small, deliberately patterned benchmark with a substantial temporal change in scenario mix.

## Reproduced held-out test result at the existing threshold

The existing decision rule is `decision_function < 0`. Isolation Forest's offset is fit using the training split and configured contamination `0.05`; it is not selected using test labels.

| Test outcome | Count |
|---|---:|
| True positive | 22 |
| False positive | 17 |
| True negative | 176 |
| False negative | 3 |
| Test records | 218 |
| Precision | 0.5641 |
| Recall | 0.8800 |
| F1 | 0.6875 |
| False-positive rate (17 / 193 normal) | 0.0881 |

Confusion matrix, rows actual `[normal, anomaly]`, columns predicted `[normal, anomaly]`:

```text
[[176, 17],
 [  3, 22]]
```

The overall fixture is 1.98% generated anomalies, but the held-out test window is 25/218 (11.47%) anomalous because the generator places anomalies late in the timeline. Validation has 5/220 anomalies (2.27%), all unfamiliar-IP; it contains no unusual-hour cases. Training contains 1,077 rows and no injected anomalies. This temporal scenario shift is a major reason not to interpret the single test result as a stable operating characteristic.

## Scenario-level detection and scores

| Test scenario | Support | Fixed-zero detections | Detection rate | Score mean | Score median | Score p05–p95 |
|---|---:|---:|---:|---:|---:|---:|
| Normal | 193 | 17 false positives | 8.8% false-positive rate | 0.0542 | 0.0603 | -0.0089–0.0976 |
| Unfamiliar IP | 10 | 10 true positives | 100% | -0.1263 | -0.1211 | -0.1529–-0.1148 |
| Unusual hour | 15 | 12 true positives, 3 false negatives | 80% | -0.0166 | -0.0147 | -0.0525–0.0086 |

The unfamiliar-IP score band is well separated in this generated fixture. Unusual-hour scores overlap the normal band and cross zero, producing the three missed cases. The test set contains only 10 unfamiliar-IP and 15 unusual-hour cases.

## Threshold analysis (validation selection; test evaluation)

Two alternatives were selected using validation labels only, then evaluated once on test. No test label or score was used to choose either threshold.

| Rule | Threshold | Validation result | Held-out test result |
|---|---:|---|---|
| Existing fixed zero | 0.0000 | TP 5, FP 5, FN 0; P 0.500, R 1.000, F1 0.667, FPR 2.3% | TP 22, FP 17, FN 3; P 0.564, R 0.880, F1 0.688, FPR 8.8% |
| Validation maximum F1 | -0.1090 | TP 5, FP 0, FN 0; P 1.000, R 1.000, F1 1.000, FPR 0% | TP 10, FP 0, FN 15; P 1.000, R 0.400, F1 0.571, FPR 0% |
| Largest threshold with validation normal FPR ≤ 5% | 0.0049 | TP 5, FP 10, FN 0; P 0.333, R 1.000, F1 0.500, FPR 4.7% | TP 23, FP 22, FN 2; P 0.511, R 0.920, F1 0.657, FPR 11.4% |

The maximum-F1 threshold looks perfect on validation because its five positive examples are all unfamiliar-IP and those scores are unusually distinct. At that threshold it catches 10/10 unfamiliar-IP test cases but 0/15 unusual-hour cases. This is a concrete example of scenario coverage failure and validation overfit. A validation FPR budget of 5% also does not hold on test: test FPR rises to 11.4%. Threshold selection needs multiple representative validation windows and scenario coverage before being considered useful.

## Contamination sensitivity at fixed zero

All rows below use the same train/validation/test partitions and random state 42; only the training-configured contamination changes. Test labels are evaluation-only.

| Contamination | TP | FP | TN | FN | Precision | Recall | F1 | Test FPR |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.01 | 0 | 0 | 193 | 25 | 0.000 | 0.000 | 0.000 | 0.0% |
| 0.02 | 10 | 0 | 193 | 15 | 1.000 | 0.400 | 0.571 | 0.0% |
| 0.03 | 15 | 1 | 192 | 10 | 0.938 | 0.600 | 0.732 | 0.5% |
| 0.05 | 22 | 17 | 176 | 3 | 0.564 | 0.880 | 0.688 | 8.8% |

The operating point changes sharply with contamination. These figures are not evidence that `0.03` is a better setting outside this fixture; they show that contamination and the fixed zero rule jointly control alert volume and sensitivity.

## Seed stability

Five random seeds were run on the same temporal partitions, with contamination `0.05` and 100 estimators. Results are held-out test metrics.

| Seed | Fixed-zero precision | Recall | F1 | FPR | Validation-max-F1 threshold | Threshold-selected test F1 |
|---:|---:|---:|---:|---:|---:|---:|
| 7 | 0.556 | 1.000 | 0.714 | 10.4% | -0.0945 | 0.529 |
| 21 | 0.581 | 1.000 | 0.735 | 9.3% | -0.1168 | 0.529 |
| 42 | 0.564 | 0.880 | 0.688 | 8.8% | -0.1090 | 0.571 |
| 84 | 0.595 | 1.000 | 0.746 | 8.8% | -0.0906 | 0.529 |
| 123 | 0.490 | 1.000 | 0.658 | 13.5% | -0.0859 | 0.387 |

The fixed-zero test F1 range is 0.658–0.746, with FPR 8.8%–13.5%. Validation-selected thresholds span -0.1168 to -0.0859 (standard deviation 0.0116); their test F1 range is 0.387–0.571. The validation-tuned threshold is less stable in held-out utility than the fixed threshold on this fixture, and its test FPR is zero only because it is overly conservative for the unusual-hour scenario.

## User and activity-profile generalization

The main temporal test uses the same five users present in training. Per-user results at the fixed-zero rule:

| Generated user profile | Test support | TP | FP | FN | Precision | Recall | F1 | FPR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| U1, 09:00–18:00 UTC | 41 | 4 | 0 | 1 | 1.000 | 0.800 | 0.889 | 0.0% |
| U2, 10:00–19:00 UTC | 45 | 4 | 1 | 1 | 0.800 | 0.800 | 0.800 | 2.5% |
| U3, 08:00–17:00 UTC | 41 | 5 | 6 | 0 | 0.455 | 1.000 | 0.625 | 16.7% |
| U4, 09:00–18:00 UTC | 46 | 5 | 3 | 0 | 0.625 | 1.000 | 0.769 | 7.3% |
| U5, 10:00–19:00 UTC | 45 | 4 | 7 | 1 | 0.364 | 0.800 | 0.500 | 17.5% |

A leave-one-user-out check fit on the other four users' train rows, then evaluated the held-out user's test rows. Across the five held-out folds, aggregate counts were TP 25, FP 29, TN 164, FN 0 (precision 0.463, recall 1.000, F1 0.633, FPR 15.0%). Per-user FPR ranged from 0% to 32.5%. Each user contributes only five injected test anomalies, so the recall values have wide uncertainty and should not be generalized.

This does test different generated work-hour windows and unseen synthetic identities, but not broad behavioral profiles: event volume is only 4–6 generated normal events/day, anomaly scenarios are only unfamiliar IP and unusual UTC hour, and all users share the same generator structure.

## Snapshot-mode separation

Snapshot experiments do not have trustworthy event-level labels. Their `evaluation.json` keeps precision, recall, F1, confusion matrix, false-positive analysis, and false-negative analysis unavailable. It reports score distributions and predicted anomaly counts/rates by temporal split only. No snapshot results were used in the labeled tables above.

## Findings and recommendations

1. Keep Isolation Forest experimental. The controlled benchmark demonstrates sensitivity to contamination, seed, user profile, and scenario coverage, with test false-positive rates between 8.8% and 13.5% across seeds at the nominal configuration.
2. Do not adopt the validation-max-F1 threshold: it misses an anomaly scenario absent from validation. Build temporally separated validation windows that cover each anomaly family and normal profile before assessing thresholds.
3. Do not claim a 5% production FPR from the validation constraint; measured synthetic test FPR was 11.4%.
4. Extend the synthetic benchmark only with clearly specified controlled scenarios and broader normal profiles (including volume and event-type variation), then preserve scenario labels strictly outside model fit.
5. Seek an approved source of adjudicated event outcomes before estimating operational precision, recall, false-positive cost, or selecting an alert threshold.
6. Reconcile the snapshot and event-helper feature semantics documented in `ML_FEATURE_QUALITY_REPORT.md` before comparing future snapshots to these benchmark results.

Every result here is from a generated fixture. It does not establish production precision, recall, FPR, robustness, or security efficacy.
