# UEBA College Project — 12-Slide Presentation Outline

| # | Slide title | Key content | Suggested visual | Presenter explanation |
|---:|---|---|---|---|
| 1 | UEBA Security Operations Platform | Project title, student/team, department, guide, date. | `soc-overview.png` or title slide with app logo. | Introduce a local project for event investigation, user baselines, and experimental anomaly analysis. |
| 2 | Problem Statement | Analysts face large event volumes; user-specific context and investigation notes need structure. | Simple flow: many event sources → analyst triage. | Explain the project problem without claiming comprehensive attack detection. |
| 3 | Objectives | Ingest/browse events; build baselines; explain rule matches; manage alerts and feedback; experiment offline with ML. | Objective icons or requirement checklist. | Emphasize operational workflow and ML experiment are separate objectives. |
| 4 | Introduction to UEBA | Event vs alert; entity/user baseline; SOC triage; anomaly is a signal for investigation. | Event → baseline comparison → analyst review. | Define UEBA and clarify that unusual does not necessarily mean malicious. |
| 5 | System Architecture | React SPA, FastAPI APIs, PostgreSQL; active rule-based alert path; separate synthetic-only ML demo endpoint. | Export/render [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) Mermaid diagram. | Trace an event through ingestion, baseline, explicit rule analysis, alert, and feedback; show the ML demo route's fixture-only boundary. |
| 6 | Technology Stack | React, TypeScript, Vite; Python, FastAPI, Pydantic; PostgreSQL, SQLAlchemy, Alembic; scikit-learn, pytest. | Stack diagram or small logos. | Explain each tool's role using the actual repository stack. |
| 7 | SOC Dashboard and Investigation Features | Overview, alert filters/detail/status/feedback, event list/details, user lookup/baseline. | `soc-overview.png`, `alert-investigation.png`, `event-details.png`. | Demonstrate how analysts move from summary to event evidence and record an outcome. |
| 8 | Behavioral Baselines and Feature Engineering | All-history baseline values; `ueba-seven-v2`; seven features and point-in-time history rule. | `user-analytics-baseline.png` plus compact feature table. | Explain time-cycle, login/familiarity, and event/IP frequency inputs. Mention all-history baseline limitation. |
| 9 | Isolation Forest Methodology | Unsupervised experimental candidate; train-only scaling/fit; chronological splits; zero threshold; no operational inference. | Offline ML workflow diagram and tree/isolation conceptual visual. | Explain why used for an experiment when real labels are missing, and that it is not selected for production. |
| 10 | Experimental Results | Synthetic confusion matrix, precision/recall/F1/FPR; five-seed mean F1; leave-one-user-out. | `ml-evaluation-results.png` or confusion-matrix table. | State all values are synthetic. Explain the FP/FN tradeoff and generalization warning. |
| 11 | Limitations and Future Scope | No auth; all-history baseline; small synthetic data; no real labels; no ML alerting, registry, or deployment. | Limitations/future-work two-column list. | Explain what evidence and safeguards would be required before operational ML. |
| 12 | Conclusion | Working local rule-based investigation flow; separate reproducible synthetic ML demo page/API; controlled next steps. | Final architecture summary or `ml-anomalous-prediction.png`. | Close by stating what works today and what remains experimental/planned. |

## Presentation accuracy reminders

- Call benchmark metrics **synthetic experimental results**, never production performance.
- A `decision_function` value is not a probability or confidence percentage.
- Rule-based analysis currently creates operational alerts; Isolation Forest does not.
- Show only sanitized synthetic identities and event data in screenshots.

