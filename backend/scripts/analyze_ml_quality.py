"""Measure feature and detection quality on the existing generated benchmark."""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Sequence

import numpy as np

from app.services.ml_anomaly import FEATURE_NAMES
from app.services.ml_experiments import (
    fit_detector,
    load_synthetic_benchmark,
)

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_FIXTURE = SCRIPT_DIR / "reports" / "synthetic_events.csv"
CONTAMINATIONS = (0.01, 0.02, 0.03, 0.05)
SEEDS = (7, 21, 42, 84, 123)


def _metrics(scenarios: Sequence[str], scores: Sequence[float], threshold: float) -> dict[str, object]:
    actual = [scenario != "normal" for scenario in scenarios]
    predicted = [score < threshold for score in scores]
    tp = sum(y and p for y, p in zip(actual, predicted))
    fp = sum((not y) and p for y, p in zip(actual, predicted))
    fn = sum(y and (not p) for y, p in zip(actual, predicted))
    tn = sum((not y) and (not p) for y, p in zip(actual, predicted))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "threshold": float(threshold),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "support": len(actual),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": fp / (fp + tn) if fp + tn else None,
    }


def _select_validation_threshold(
    scenarios: Sequence[str], scores: Sequence[float]
) -> float:
    """Choose max validation F1; ties prefer precision, then fewer alerts."""
    candidates = [float(np.nextafter(score, math.inf)) for score in sorted(set(scores))]
    candidates.append(float(np.nextafter(min(scores), -math.inf)))
    return max(
        candidates,
        key=lambda threshold: (
            _metrics(scenarios, scores, threshold)["f1"],
            _metrics(scenarios, scores, threshold)["precision"],
            -_metrics(scenarios, scores, threshold)["tp"],
        ),
    )


def _select_validation_fpr_threshold(
    scenarios: Sequence[str], scores: Sequence[float], max_fpr: float = 0.05
) -> float:
    """Choose the lowest threshold meeting the validation normal FPR budget."""
    normal_scores = [score for scenario, score in zip(scenarios, scores) if scenario == "normal"]
    if not normal_scores:
        raise ValueError("Validation split must include normal examples for FPR thresholding")
    candidates = [float(np.nextafter(score, math.inf)) for score in sorted(set(normal_scores))]
    candidates.append(float(np.nextafter(min(normal_scores), -math.inf)))
    acceptable = [
        threshold for threshold in candidates
        if _metrics(scenarios, scores, threshold)["false_positive_rate"] <= max_fpr
    ]
    if not acceptable:
        return float(np.nextafter(min(normal_scores), -math.inf))
    return max(acceptable)


def _distribution(values: Sequence[float]) -> dict[str, float] | None:
    if not values:
        return None
    array = np.asarray(values, dtype=float)
    return {
        "count": int(array.size),
        "mean": float(np.mean(array)),
        "std": float(np.std(array)),
        "min": float(np.min(array)),
        "p05": float(np.percentile(array, 5)),
        "median": float(np.median(array)),
        "p95": float(np.percentile(array, 95)),
        "max": float(np.max(array)),
    }


def _load_user_ids(path: Path) -> dict[int, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {index: row["user_id"] for index, row in enumerate(csv.DictReader(handle))}


def analyze(fixture: Path) -> dict[str, object]:
    benchmark = load_synthetic_benchmark(fixture)
    user_ids = _load_user_ids(fixture)
    rows = list(benchmark.rows)
    if not rows or any(len(row.features) != len(FEATURE_NAMES) for row in rows):
        raise ValueError("Benchmark does not contain the approved seven features")
    if any(not np.isfinite(row.features).all() for row in rows):
        raise ValueError("Benchmark contains invalid feature values")

    X = np.asarray([row.features for row in rows], dtype=float)
    scenarios = [row.scenario for row in rows]
    split_scenarios: dict[str, list[str]] = defaultdict(list)
    split_features: dict[str, list[tuple[float, ...]]] = defaultdict(list)
    split_user_ids: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        split_scenarios[row.split].append(row.scenario)
        split_features[row.split].append(row.features)
        split_user_ids[row.split].append(user_ids[row.row_number])

    feature_report: dict[str, object] = {
        "feature_order": list(FEATURE_NAMES),
        "records": len(rows),
        "missing_or_invalid_values": {
            name: int(sum(not math.isfinite(float(value)) for value in X[:, index]))
            for index, name in enumerate(FEATURE_NAMES)
        },
        "overall_distributions": {},
        "distribution_by_scenario": {},
        "pearson_correlation": {},
        "unique_users": len(set(user_ids.values())),
        "scenario_counts": dict(sorted(Counter(scenarios).items())),
        "split_scenario_counts": {
            split: dict(sorted(Counter(values).items()))
            for split, values in split_scenarios.items()
        },
    }
    overall: dict[str, object] = {}
    by_scenario: dict[str, object] = {}
    for index, name in enumerate(FEATURE_NAMES):
        overall[name] = _distribution(X[:, index].tolist())
        by_scenario[name] = {
            scenario: _distribution([
                float(row.features[index]) for row in rows if row.scenario == scenario
            ])
            for scenario in sorted(set(scenarios))
        }
    feature_report["overall_distributions"] = overall
    feature_report["distribution_by_scenario"] = by_scenario
    corr = np.corrcoef(X, rowvar=False)
    feature_report["pearson_correlation"] = {
        name: {
            other: (float(corr[i, j]) if math.isfinite(float(corr[i, j])) else None)
            for j, other in enumerate(FEATURE_NAMES)
        }
        for i, name in enumerate(FEATURE_NAMES)
    }

    train_indices = [i for i, row in enumerate(rows) if row.split == "train"]
    validation_indices = [i for i, row in enumerate(rows) if row.split == "validation"]
    test_indices = [i for i, row in enumerate(rows) if row.split == "test"]
    X_train = X[train_indices]
    validation_labels = [scenarios[i] for i in validation_indices]
    test_labels = [scenarios[i] for i in test_indices]
    X_validation = X[validation_indices]
    X_test = X[test_indices]

    base_model = fit_detector(X_train, contamination=0.05, random_state=42, n_estimators=100)
    validation_scores = [base_model.score(row)["decision_score"] for row in X_validation]
    selected_f1 = _select_validation_threshold(validation_labels, validation_scores)
    selected_fpr = _select_validation_fpr_threshold(validation_labels, validation_scores)
    # Only score the held-out test partition after validation thresholds are fixed.
    test_scores = [base_model.score(row)["decision_score"] for row in X_test]
    threshold_results = {
        "fixed_zero": {
            "selected_using": "training contamination offset; no validation/test labels",
            "validation": _metrics(validation_labels, validation_scores, 0.0),
            "test": _metrics(test_labels, test_scores, 0.0),
        },
        "validation_max_f1": {
            "selected_using": "validation labels only; maximizes validation F1, then precision, then fewer true positives",
            "threshold": selected_f1,
            "validation": _metrics(validation_labels, validation_scores, selected_f1),
            "test": _metrics(test_labels, test_scores, selected_f1),
        },
        "validation_max_fpr_5pct": {
            "selected_using": "validation normal labels only; largest threshold with validation FPR <= 5%",
            "threshold": selected_fpr,
            "validation": _metrics(validation_labels, validation_scores, selected_fpr),
            "test": _metrics(test_labels, test_scores, selected_fpr),
        },
        "test_labels_used_for_threshold_selection": False,
    }

    feature_ablation = {}
    ablation_sets = {
        "remove_is_known_ip": ("is_known_ip",),
        "remove_source_ip_frequency": ("source_ip_frequency",),
        "remove_is_known_event_type": ("is_known_event_type",),
        "remove_both_ip_signals": ("is_known_ip", "source_ip_frequency"),
    }
    for variant, removed_names in ablation_sets.items():
        train_variant = X_train.copy()
        validation_variant = X_validation.copy()
        test_variant = X_test.copy()
        for name in removed_names:
            column = FEATURE_NAMES.index(name)
            train_variant[:, column] = 0.0
            validation_variant[:, column] = 0.0
            test_variant[:, column] = 0.0
        variant_seed_results = []
        seed_42_threshold = None
        seed_42_selected_metrics = None
        for seed in SEEDS:
            variant_model = fit_detector(
                train_variant, contamination=0.05, random_state=seed, n_estimators=100
            )
            variant_validation_scores = [
                variant_model.score(row)["decision_score"] for row in validation_variant
            ]
            variant_threshold = _select_validation_threshold(
                validation_labels, variant_validation_scores
            )
            variant_test_scores = [
                variant_model.score(row)["decision_score"] for row in test_variant
            ]
            fixed_metrics = _metrics(test_labels, variant_test_scores, 0.0)
            selected_metrics = _metrics(test_labels, variant_test_scores, variant_threshold)
            variant_seed_results.append({"seed": seed, **fixed_metrics})
            if seed == 42:
                seed_42_threshold = variant_threshold
                seed_42_selected_metrics = selected_metrics
        f1_values = [float(result["f1"]) for result in variant_seed_results]
        fpr_values = [float(result["false_positive_rate"]) for result in variant_seed_results]
        feature_ablation[variant] = {
            "features_held_constant": list(removed_names),
            "fixed_zero_by_seed": variant_seed_results,
            "fixed_zero_test_f1_mean": float(np.mean(f1_values)),
            "fixed_zero_test_f1_std": float(np.std(f1_values)),
            "fixed_zero_test_f1_range": [min(f1_values), max(f1_values)],
            "fixed_zero_test_fpr_mean": float(np.mean(fpr_values)),
            "fixed_zero_test_fpr_range": [min(fpr_values), max(fpr_values)],
            "seed_42_validation_max_f1_threshold": seed_42_threshold,
            "seed_42_validation_max_f1_test": seed_42_selected_metrics,
        }

    by_scenario_test = {}
    for scenario in sorted(set(test_labels)):
        indices = [i for i, label in enumerate(test_labels) if label == scenario]
        selected = [test_scores[i] for i in indices]
        scenario_actual = [scenario] * len(indices)
        by_scenario_test[scenario] = {
            "support": len(indices),
            "score_distribution": _distribution(selected),
            "fixed_zero": _metrics(scenario_actual, selected, 0.0),
            "validation_max_f1": _metrics(scenario_actual, selected, selected_f1),
            "validation_max_fpr_5pct": _metrics(scenario_actual, selected, selected_fpr),
        }

    per_user = {}
    test_users = [user_ids[rows[index].row_number] for index in test_indices]
    for user in sorted(set(test_users)):
        indices = [i for i, value in enumerate(test_users) if value == user]
        user_scenarios = [test_labels[i] for i in indices]
        user_scores = [test_scores[i] for i in indices]
        per_user[user] = {
            "support": len(indices),
            "scenario_counts": dict(sorted(Counter(user_scenarios).items())),
            "fixed_zero": _metrics(user_scenarios, user_scores, 0.0),
        }

    contamination_sweep = []
    for contamination in CONTAMINATIONS:
        detector = fit_detector(X_train, contamination=contamination, random_state=42, n_estimators=100)
        scores = [detector.score(row)["decision_score"] for row in X_test]
        row = _metrics(test_labels, scores, 0.0)
        row["contamination"] = contamination
        contamination_sweep.append(row)

    seed_rows = []
    for seed in SEEDS:
        detector = fit_detector(X_train, contamination=0.05, random_state=seed, n_estimators=100)
        val_scores = [detector.score(row)["decision_score"] for row in X_validation]
        threshold = _select_validation_threshold(validation_labels, val_scores)
        heldout_scores = [detector.score(row)["decision_score"] for row in X_test]
        fixed = _metrics(test_labels, heldout_scores, 0.0)
        tuned = _metrics(test_labels, heldout_scores, threshold)
        seed_rows.append({
            "seed": seed,
            "validation_selected_threshold": threshold,
            "fixed_zero_test": fixed,
            "validation_max_f1_test": tuned,
        })
    thresholds = [float(row["validation_selected_threshold"]) for row in seed_rows]
    stability = {
        "seed_count": len(SEEDS),
        "seeds": list(SEEDS),
        "selected_thresholds": thresholds,
        "threshold_mean": float(np.mean(thresholds)),
        "threshold_std": float(np.std(thresholds)),
        "threshold_min": min(thresholds),
        "threshold_max": max(thresholds),
        "test_f1_range_fixed_zero": [
            min(row["fixed_zero_test"]["f1"] for row in seed_rows),
            max(row["fixed_zero_test"]["f1"] for row in seed_rows),
        ],
        "test_f1_range_validation_selected": [
            min(row["validation_max_f1_test"]["f1"] for row in seed_rows),
            max(row["validation_max_f1_test"]["f1"] for row in seed_rows),
        ],
        "per_seed": seed_rows,
    }

    leave_user_out = {}
    all_users = sorted(set(user_ids.values()))
    for heldout_user in all_users:
        train_rows = [
            row.features for row in rows
            if row.split == "train" and user_ids[row.row_number] != heldout_user
        ]
        detector = fit_detector(train_rows, contamination=0.05, random_state=42, n_estimators=100)
        selected_rows = [
            row for row in rows
            if row.split == "test" and user_ids[row.row_number] == heldout_user
        ]
        labels = [row.scenario for row in selected_rows]
        scores = [detector.score(row.features)["decision_score"] for row in selected_rows]
        leave_user_out[heldout_user] = {
            "training_users": len(all_users) - 1,
            "training_rows": len(train_rows),
            "test_support": len(selected_rows),
            "scenario_counts": dict(sorted(Counter(labels).items())),
            "fixed_zero": _metrics(labels, scores, 0.0),
        }
    loo_metrics = [entry["fixed_zero"] for entry in leave_user_out.values()]
    loo_tp = sum(int(metric["tp"]) for metric in loo_metrics)
    loo_fp = sum(int(metric["fp"]) for metric in loo_metrics)
    loo_tn = sum(int(metric["tn"]) for metric in loo_metrics)
    loo_fn = sum(int(metric["fn"]) for metric in loo_metrics)
    loo_precision = loo_tp / (loo_tp + loo_fp) if loo_tp + loo_fp else 0.0
    loo_recall = loo_tp / (loo_tp + loo_fn) if loo_tp + loo_fn else 0.0
    loo_f1 = (
        2 * loo_precision * loo_recall / (loo_precision + loo_recall)
        if loo_precision + loo_recall else 0.0
    )
    leave_user_out_report = {
        "by_user": leave_user_out,
        "aggregate": {
            "tp": loo_tp,
            "fp": loo_fp,
            "tn": loo_tn,
            "fn": loo_fn,
            "precision": loo_precision,
            "recall": loo_recall,
            "f1": loo_f1,
            "false_positive_rate": loo_fp / (loo_fp + loo_tn) if loo_fp + loo_tn else None,
        },
    }

    return {
        "dataset": {
            "kind": "checked_in_deterministic_synthetic_fixture",
            "fixture_sha256": benchmark.fixture_id,
            "rows": len(rows),
            "users": len(set(user_ids.values())),
            "split_cutoffs_utc": benchmark.split_cutoffs,
            "split_counts": dict(sorted(Counter(row.split for row in rows).items())),
            "label_counts": dict(sorted(Counter(scenarios).items())),
        },
        "feature_quality": feature_report,
        "model": {
            "type": "IsolationForest",
            "features": list(FEATURE_NAMES),
            "training_split_only": True,
            "training_rows": len(train_indices),
            "validation_rows": len(validation_indices),
            "test_rows": len(test_indices),
            "threshold_analysis": threshold_results,
            "feature_ablation": feature_ablation,
            "test_metrics_by_scenario": by_scenario_test,
            "test_metrics_by_user": per_user,
            "contamination_sweep_fixed_zero": contamination_sweep,
            "seed_stability": stability,
            "leave_one_user_out": leave_user_out_report,
            "labels_used_for_training_or_preprocessing": False,
            "test_labels_used_for_threshold_selection": False,
        },
        "warning": "All scores are synthetic benchmark measurements and are not production performance.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--output", type=Path, help="optional JSON report path")
    args = parser.parse_args()
    result = analyze(args.fixture)
    rendered = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
