# ML Labeling Policy

**Purpose:** define evidence-based labels for a future supervised evaluation or training dataset. This policy is not an implementation and does not convert current alerts, feedback, statuses, or synthetic scenarios into production labels.

## Current label-related fields

- `AnalystFeedback.verdict` is constrained to `true_positive`, `false_positive`, `benign`, or `inconclusive`.
- Feedback rows are keyed to `alert_id`, with a supplied `analyst_id`, free-text comment, and `created_at`. The feedback schema has no `event_id`; the linked `Alert.event_id` is nullable, so some feedback cannot be unambiguously mapped to an event.
- An alert has `event_id`, nullable `user_id`, `severity`, `risk_score`, `status`, `explanation`, JSON `evidence`, and creation time. The active anomaly route writes rule evidence (`detection_method: rule_based`). Severity and rule risk score are detector outputs, not ground-truth labels.
- Alert workflow statuses (`open`, `investigating`, `resolved`, `dismissed`) describe handling state. They do not say whether an event is malicious or benign.
- The synthetic CSV's `scenario` values are generated experiment labels. They are not analyst-confirmed labels and are absent from the production event schema.

The current feedback endpoint accepts an `analyst_id` value but the repository has no authenticated analyst identity/RBAC implementation to verify it. A future label pipeline must not treat this field alone as proof of reviewer identity or authority.

## Label taxonomy and evidence requirements

Labels must be scoped to a subject and a time window. A single alert/event verdict should not silently label every event for that user or all neighboring events.

| Label state | Meaning | Minimum evidence / policy |
| --- | --- | --- |
| **Normal / reviewed benign** | The specific event or bounded activity window was reviewed and found consistent with authorized or expected activity for the defined scope. | Positive human review or a trusted, documented source of benign ground truth. Record scope and review provenance. “No alert,” “no feedback,” or “seen before” is not normal ground truth. |
| **Confirmed malicious** | The specific event or bounded activity was confirmed as malicious through incident, forensic, or otherwise approved investigation evidence. | Human-reviewed incident evidence with a verifiable event/time/entity link. Record the evidence reference and the confirmation time. A detector flag or analyst “true positive” click without a resolved incident is not sufficient on its own. |
| **Suspicious, unconfirmed** | Activity warrants investigation, but the evidence does not establish maliciousness or benignness. | Preserve as a separate review state. Do not use as a positive or negative supervised label. Exclude from normal-only training unless a separately approved unsupervised contamination policy addresses it. |
| **False positive (detector-specific)** | A particular detection/alert was reviewed and judged not to be a valid detection under that detector's stated purpose. | Link to the detector output/version and its event. This labels detection correctness; it does not automatically mean every event field, action, or user was benign. |
| **Unknown / unlabeled** | No adequate review or ground truth exists, evidence is ambiguous, or the record cannot be linked reliably. | Default state. Keep out of supervised loss and labelled metrics. Do not convert absence of a label into normal. |
| **Inconclusive** | A reviewer examined the case but could not make a reliable determination. | Retain as inconclusive/unknown for training and binary metrics. Preserve the review event separately from a final class label. |

“False negative” is not a directly observed event label without a source of ground truth. It is a metric outcome only when a confirmed positive sample was scored by a specified detector/version and missed.

## How existing feedback can contribute

1. Resolve `AnalystFeedback.alert_id` to the alert. Require a non-null, verified `Alert.event_id` before mapping the feedback to an event-level candidate label. Keep unlinked alerts as alert-level review data only.
2. Treat `true_positive` as “reviewer marked this alert as a true detection” pending the policy's evidence threshold. Promote it to **confirmed malicious** only when incident evidence and event scope meet the confirmed-malicious definition.
3. Treat `false_positive` as detector-specific false-alarm evidence. Promote the event to **normal / reviewed benign** only if the reviewer explicitly establishes benign activity for that event/window; do not infer that from the alert verdict alone.
4. Treat `benign` as candidate benign review for the linked scope, subject to verified reviewer provenance and sufficient evidence.
5. Treat `inconclusive`, missing feedback, stale/unresolved alerts, and unknown event links as unlabeled.
6. Do not use free-text feedback comments as model features or labels. They may contain personal data, secrets, speculation, or unstructured context; separate review and redaction would be required.

Existing alert severity, risk score, rule evidence, alert status, model prediction, and synthetic `scenario` are not substitutes for an independent label. In particular, do not train from “dismissed” as normal or “open” as malicious.

## Label provenance and adjudication

For any future label dataset, preserve a versioned label record with at least:

- target type and stable target reference: event, alert/detection, entity, or explicitly bounded activity window;
- label state and taxonomy version;
- source: incident outcome, analyst review, external adjudicated source, or synthetic fixture;
- reviewer identity resolved through an authenticated identity system, review time, and evidence/reference;
- detector/method/version when the verdict concerns detection correctness;
- confidence or review quality only if its definition and capture process are approved;
- supersession/conflict linkage, so corrected labels do not erase audit history.

If reviewers disagree, retain both assertions and route the record for adjudication. Do not silently choose the latest verdict, average contradictory labels, or count all analyst feedback rows as independent samples. Deduplicate at the target/scope level and keep the provenance of every included label.

## Dataset inclusion rules

- **Normal-only training:** include only approved, sufficiently reviewed benign/normal samples from the training period. Current synthetic `scenario == normal` is useful only for the generated experiment, not evidence of real benign telemetry.
- **Supervised training/evaluation:** include only adjudicated positive and negative examples with valid event linkage, scope, and label source. Keep unconfirmed/inconclusive/unknown outside binary metrics.
- **Unsupervised training:** unlabeled does not guarantee normal. Define an explicit contamination review/selection process, quarantine known suspicious periods where justified, and record the sample policy and expected contamination uncertainty.
- Keep labels temporally after the event when they come from later investigations. Split data by event time before using review outcomes, and ensure later labels do not create leakage through feature fields such as alert outcome or investigation metadata.
- Report the number excluded by missing linkage, unknown, inconclusive, conflict, and insufficient evidence. Do not hide selection bias from which cases received analyst review.

## Governance and safeguards

- Keep adjudicated labels versioned and access-controlled; maintain an audit trail for corrections and exports.
- Minimize comment/payload access; use evidence references rather than copying sensitive narrative into training files.
- Do not feed ML-generated predictions back as labels for the same detector without separately approved human review; this creates self-reinforcing feedback loops.
- Keep a frozen, independently reviewed evaluation label set. Do not tune to the final holdout.
- Treat label policy changes as dataset-version changes and re-evaluate comparability of metrics.

