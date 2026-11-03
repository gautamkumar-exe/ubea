# Updated UEBA Design Requirements

## Product direction
A Splunk-inspired SOC interface for the existing UEBA platform. The visual style remains compact, dark, high-density, keyboard-accessible, and analyst-oriented. This is an original UEBA product; do not claim Splunk protocol compatibility or use Splunk branding.

## Required navigation
- Overview
- Security Events
- Security Alerts
- User Analytics
- Entity Behavior
- Behavioral Baselines
- **ML Analytics** (new)
- Investigations
- Analyst Feedback
- **AI SOC Assistant** (new; planned capability)
- System Health
- Settings

Only expose working pages/actions when corresponding backend functionality exists. Planned capabilities must be marked Planned/Not connected, not represented as operational.

## ML-first requirements
- Add an ML Analytics workspace for model status, model/version metadata, training window, feature set, evaluation metrics, anomaly score distribution, and recent detections.
- Distinguish anomaly score from alert risk score.
- Show detection evidence and feature contributions only when produced by the actual model/pipeline.
- Include model lifecycle states: Not trained, Training, Ready, Failed, Stale.
- Restrict model training, deployment, and baseline rebuild to authorized roles; require confirmation and audit logging.
- Do not display fabricated accuracy, precision, recall, model version, or anomaly counts.

## AI SOC Assistant requirements (planned)
- Add a chat workspace for natural-language questions about authorized events, alerts, user behavior, baselines, and ML detections.
- Show cited event IDs and alert IDs for each answer.
- Display data time range and retrieval scope.
- Clearly label unsupported questions and insufficient evidence.
- The assistant is read-only by default; any future response action requires a separate authorized workflow and human confirmation.
- Do not claim chatbot is connected until the backend and LLM integration are implemented.

## Dashboard data integrity
- All KPI values, charts, tables, health states, timestamps, and user identities must come from the backend.
- Mark local fixture data as Demo data.
- Show Loading, Empty, Stale, Unavailable, and Error states.
- Never show “Connected”, “Healthy”, or “Live” before a successful health/API response.
- Use server-side filtering, sorting, and pagination for large event/alert datasets.

## Existing prototype scope
The supplied ZIP contains static HTML mockups, not the actual React application. Convert the approved layouts into React components in the existing Vite project; do not use these standalone HTML files as a replacement for the application or backend.
