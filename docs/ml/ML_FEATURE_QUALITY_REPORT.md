# ML Feature Quality Report

## Scope and method

This audit covers the seven features in `backend/app/services/ml_anomaly.py::FEATURE_NAMES`, the causal helper `backend/app/services/ml_features.py::features_for_event`, the offline snapshot builder in `backend/app/services/ml_dataset.py`, and the existing benchmark/training scripts. Measurements below use only the checked-in deterministic synthetic fixture `backend/scripts/reports/synthetic_events.csv`; no production or development database was queried.

Reproduce feature summaries and correlations from the repository root:

```sh
cd backend
PYTHONPATH=. ../.venv312/bin/python -m scripts.analyze_ml_quality \
  --fixture scripts/reports/synthetic_events.csv \
  --output /private/tmp/ueba_ml_quality.json
```

The fixture has 1,515 records across five generated users: 1,485 normal, 15 unfamiliar-IP and 15 unusual-hour examples. All seven features were finite and present for all 1,515 rows in this fixture. That describes the synthetic file only and is not a production missingness estimate. The benchmark reader rejects rows missing required source columns. The separate controlled PostgreSQL malformed-row test exercises a blank event type, missing user, and invalid IP; the snapshot pipeline records invalid feature data and does not silently assign a normal label.

## Measured feature distributions

The table gives the full fixture distribution. Counts are records; p05/median/p95 are empirical percentiles. Binary features are shown as proportions of ones.

| Feature | Mean | Std. dev. | p05 | Median | p95 | Min–max | Quality observation |
|---|---:|---:|---:|---:|---:|---:|---|
| `hour_sin` | -0.3869 | 0.5690 | -0.9979 | -0.5556 | 0.6593 | -1.0000–0.8767 | UTC cyclical time encoding; generated normal activity is concentrated in daytime hours. |
| `hour_cos` | -0.5897 | 0.4229 | -0.9979 | -0.7518 | 0.1951 | -1.0000–0.9998 | Complementary coordinate to `hour_sin`, not a standalone hour measurement. |
| `is_login` | 0.6469 | 0.4779 | 0 | 1 | 1 | 0–1 | 64.7% of fixture rows match the event-type substring heuristic. |
| `is_known_ip` | 0.9802 | 0.1393 | 1 | 1 | 1 | 0–1 | 1.98% are unseen at event time; mostly synthetic unfamiliar-IP cases and cold starts. |
| `is_known_event_type` | 0.9901 | 0.0990 | 1 | 1 | 1 | 0–1 | 0.99% are not yet observed in that user's earlier history. |
| `user_event_frequency` | 1.6768 | 0.3131 | 1.0986 | 1.7918 | 2.0794 | 0–2.3979 | `log1p` of same-user events in the prior 24 hours. |
| `source_ip_frequency` | 3.6060 | 0.9922 | 1.6094 | 3.9120 | 4.5951 | 0–4.7875 | `log1p` of prior same-user occurrences of the current IP; the current helper/snapshot implementation uses all prior history, not a bounded window. |

Normal versus synthetic anomaly means:

| Feature | Normal | Unfamiliar IP | Unusual hour |
|---|---:|---:|---:|
| `hour_sin` | -0.3945 | -0.4415 | 0.4179 |
| `hour_cos` | -0.6037 | -0.6346 | 0.8504 |
| `is_login` | 0.6397 | 1.0000 | 1.0000 |
| `is_known_ip` | 0.9899 | 0.0000 | 1.0000 |
| `is_known_event_type` | 0.9899 | 1.0000 | 1.0000 |
| `user_event_frequency` | 1.6757 | 1.6723 | 1.7861 |
| `source_ip_frequency` | 3.6334 | 0.0000 | 4.4997 |

These differences largely reflect how the generator defines each scenario: unfamiliar-IP events have no prior count for the injected address, and unusual-hour events occur at 00:00–04:00 UTC. They establish that the features encode the generated rules, not that those patterns generalize to real attacks.

## Correlation and redundancy

Pearson correlations on all fixture rows:

| Pair | r |
|---|---:|
| `is_known_ip` / `source_ip_frequency` | 0.517 |
| `is_known_ip` / `is_known_event_type` | 0.464 |
| `is_known_event_type` / `source_ip_frequency` | 0.328 |
| `hour_sin` / `hour_cos` | -0.588 |
| `user_event_frequency` / `source_ip_frequency` | 0.200 |

The strongest overlap is structural: with valid identity and IP data, `is_known_ip` is exactly the indicator that the prior IP count is positive, while `source_ip_frequency` is `log1p` of that count. They share the novelty signal, but frequency retains count magnitude after the first observation; they are related rather than strictly identical. The hour pair is also deliberately related: both coordinates jointly encode a circular value. Linear correlation alone is not a reason to remove one coordinate.

`is_known_event_type` is near-constant in this generated dataset, so it contributes little discrimination here. Its value could differ materially on sources with changing event vocabularies. `is_login` is not a validated authentication feature: it is a case-insensitive substring check on `event_type`. Authentication success/failure is not represented.

## Behavior, missingness, and implementation consistency

- The seven inputs do not include user IDs, event IDs, timestamps, or the `scenario` label. User identity affects feature construction by scoping history, rather than being passed into Isolation Forest.
- `hour_sin`/`hour_cos`, known-type/IP flags, and event counts represent point-in-time behavior from strictly earlier, same-user history. Equal-time events cannot influence peers, and duplicate `(source, external_id)` history identities are counted once where that identity exists.
- `user_event_frequency` uses a trailing 24-hour window. `source_ip_frequency` is cumulative over the available history. Different effective windows make the magnitudes hard to compare and cumulative counts can drift with account age or poisoned history.
- Version `ueba-seven-v2` resolves the former parity differences through `backend/app/services/ml_feature_engine.py`, shared by `features_for_event` and the snapshot builder. It canonicalizes IPv4/IPv6, preserves seconds and microseconds after aware-time normalization to UTC, trims event types, strictly scopes history by user and time, and aligns equal-time behavior. Missing/malformed IP, missing user, and blank event type make the affected feature values unavailable (`None`) in both paths; a valid unfamiliar IP/type remains a real zero familiarity value.
- The checked-in fixture contains canonical IP strings, no missing values, no subsecond timestamps, and properly scoped histories. Consequently, v2 produced the same fixture feature values and the same detection measurements as the v1 baseline. Parity fixes improve semantics for edge cases, not measured benchmark performance.
- The experiment loader excludes any incomplete feature vector and records exclusions; it does not silently replace unavailable values with zero.
- User identity is not a feature, but the temporal benchmark includes the same generated users in train and test. The separate leave-one-user-out analysis is needed to measure unseen-user behavior.

## Overlapping-feature ablation

For comparison, one column at a time was held constant at zero (or both IP columns together) without changing the Isolation Forest algorithm. Each variant used the same chronological split, five seeds, contamination 0.05, 100 estimators, and test-only final scoring. The threshold for the primary table below is the existing fixed zero rule.

| Ablation | Mean test F1 across five seeds | F1 range | Mean test FPR | FPR range |
|---|---:|---:|---:|---:|
| Keep all seven (baseline and v2) | 0.708 | 0.658–0.746 | 10.2% | 8.8%–13.5% |
| Hold `is_known_ip` constant | 0.694 | 0.629–0.762 | 10.4% | 7.3%–12.4% |
| Hold `source_ip_frequency` constant | 0.809 | 0.794–0.820 | 6.1% | 5.7%–6.7% |
| Hold both IP signals constant | 0.552 | 0.536–0.556 | 7.5% | 7.3%–8.3% |
| Hold `is_known_event_type` constant | 0.725 | 0.694–0.769 | 9.8% | 7.8%–11.4% |

The benchmark suggests that the binary unfamiliar-IP indicator carries more useful signal than the cumulative IP count for these two generated scenarios. Removing the count feature improved the measured five-seed F1 and FPR; removing both IP features reduced F1, indicating that the familiarity signal matters. The fixture contains no rate/frequency anomaly scenario and only two anomaly types, so this is not enough evidence to delete `source_ip_frequency` from the general UEBA feature contract. Likewise, the modest `is_known_event_type` ablation gain is not decisive because the benchmark has no injected novel-event-type scenario. Both features remain in v2 pending broader labeled evaluation.

## Findings and recommendations

1. Keep the seven feature names/order but use schema `ueba-seven-v2`; v1 snapshots are rejected and must be regenerated. The fixture's measured model metrics are unchanged because its data does not exercise the fixed edge cases.
2. The ablation supports `is_known_ip` as the clearer signal for the current unfamiliar-IP scenario. Revisit `source_ip_frequency` only with a high-volume/known-IP repetition scenario and trustworthy labels; do not generalize the current synthetic gain.
3. Add a controlled novel-event-type scenario before judging `is_known_event_type`; the current 99.0% known rate is produced by the narrow fixture vocabulary.
4. Define a bounded, point-in-time contract for `source_ip_frequency` and preserve an explicit unavailable state for missing identity/IP.
5. Replace the login substring heuristic only after an event-type taxonomy or source-specific authentication outcome contract is approved.
6. Current source lacks local timezone, authentication outcome, verified baseline snapshots, and trustworthy event labels. Do not infer those values from `raw_event`, alert state, or generated scenario labels.

All values in this report are synthetic fixture measurements. No production distributions, missingness, correlation, or behavioral validity have been established.
