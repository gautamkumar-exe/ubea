# Screenshot Capture Checklist

## Capture rules

- Capture the real running application; do not recreate screens in a drawing or presentation tool and present them as application screenshots.
- Use the synthetic `college-demo` events in [DEMO_SCRIPT.md](DEMO_SCRIPT.md), or another controlled/sanitized local dataset.
- Avoid showing `.env`, API keys, HMAC keys, terminal history containing secrets, real analyst identities, customer names, or real security-event payloads.
- Use the browser's built-in screenshot tool or an OS screenshot utility. For consistent browser captures, use a desktop viewport around 1440×900 and browser zoom 100%; do not crop out context needed to understand the screen.
- Save captures under `docs/submission/screenshots/` using the filenames below. For command-line output, capture the actual terminal text after the command completes. Never type synthetic results into an image editor.
- After capture, open each image and verify legibility and that only sanitized example data is visible.

## Required captures

| File | Page/command to open | What should be visible | Why it matters |
| --- | --- | --- | --- |
| `soc-overview.png` | Open the app's Overview page after loading local synthetic data. | Dark SOC shell, global alert metrics, severity distribution, recent alert/event tables. | Shows the overall product and backend-derived dashboard. |
| `security-alerts.png` | Click **Security Alerts**. | Alert table, severity/status values, supported filters and pagination. | Shows alert triage workflow. |
| `alert-investigation.png` | Open the synthetic high-severity alert from the table. | Alert ID, linked event, risk/severity, explanation/evidence, status control, feedback form/history if space permits. | Demonstrates analyst investigation and feedback. |
| `security-events.png` | Click **Events**. | Event ID, event type, user/entity ID, source IP, timestamp, pagination/filter controls. | Shows stored source activity rather than alert summaries. |
| `event-details.png` | Open a synthetic event. | Actual event fields and source metadata marked as synthetic. | Shows event-level investigation context. |
| `user-analytics-baseline.png` | Click **User Analytics**, load `demo.user.001`. | Saved baseline counts and observed related alerts/events, with baseline and live activity labels. | Demonstrates user-centered context and distinction from current activity. |
| `ml-normal-prediction.png` | Run the command below; capture the JSON section for `normal_login`. | Input event, all seven features, score, “NOT FLAGGED”, and non-probability caveat. | Shows a normal controlled example and what the output means. |
| `ml-anomalous-prediction.png` | Same command; capture `unusual_login_hour`, `unfamiliar_source_ip`, or high-frequency result. | Input, feature vector, negative decision score, “ANOMALY”, and caveat. | Shows a controlled anomaly example without claiming certainty. |
| `ml-evaluation-results.png` | Run `scripts.run_ml_experiment --synthetic-benchmark` as in the demo guide. | Synthetic-only status, confusion matrix, precision/recall/F1, fixture/split warning. | Makes the experiment measurable and its limits visible. |
| `system-architecture.png` | Render/export the Mermaid diagrams in [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) using a Mermaid-capable Markdown preview. | Operational rule-based flow and the separate dashed offline ML flow. | Makes the system/data boundary clear to reviewers. |

## Exact ML screenshot commands

From the repository root:

```sh
cd backend
PYTHONPATH=. ../.venv312/bin/python -m scripts.demo_ml_anomaly
```

Then capture the actual output for the scenario rows. For the evaluation screenshot:

```sh
PYTHONPATH=. ../.venv312/bin/python -m scripts.run_ml_experiment \
  --synthetic-benchmark \
  --fixture scripts/reports/synthetic_events.csv \
  --output-dir /private/tmp/ueba-screenshot-experiment \
  --contamination 0.05 --random-state 42 --n-estimators 100
```

The experiment directory is outside the repository. Show the console JSON output or open its `evaluation.json`; do not include model artifacts in the repository unless intentionally requested.

## Final review

- [ ] All captures are from the actual current app or actual command output.
- [ ] All identities and payloads are synthetic or sanitized.
- [ ] No secrets, HMAC keys, or database credentials are visible.
- [ ] The ML captures say “experimental”/synthetic and do not imply operational alert integration.
- [ ] Screenshot filenames and Markdown references in `FINAL_PROJECT_REPORT.md` match the files present.

