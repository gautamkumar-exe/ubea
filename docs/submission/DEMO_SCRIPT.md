# UEBA Platform Demonstration Script (10–15 minutes)

## Before the presentation

- Use a local disposable database with synthetic records only. Do not point the backend at production or real security data.
- This repository's `docker-compose.yml` maps PostgreSQL host port **5433** to container port 5432. `backend/app/config.py` otherwise defaults to port 5432. The commands below explicitly set `DATABASE_URL` to the Compose host port and do not read or print the repository `.env`.
- Compose uses a persistent named volume. Do not remove volumes during a demo unless you intentionally want to delete local database contents.
- The backend requires schema migrations before serving requests.
- Keep the database, API, and frontend terminals open while presenting.

## 1. Start PostgreSQL (about 1 minute)

In Terminal 1, from the repository root:

```sh
POSTGRES_PASSWORD=change_me_local_only docker compose up -d db
docker compose ps
```

On a fresh local Compose volume, the command sets the documented development password explicitly so it matches the connection string below. For an existing volume, use the local password with which that volume was initialized; changing the Compose environment does not rotate a password already stored in PostgreSQL. Wait for the `db` service health check to report healthy. The service exposes PostgreSQL at `127.0.0.1:5433`.

## 2. Apply schema and start FastAPI (about 1 minute)

In Terminal 2:

```sh
cd backend
source ../.venv312/bin/activate
export DATABASE_URL='postgresql+psycopg://ueba_app:change_me_local_only@127.0.0.1:5433/ueba_db'
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

In a browser, FastAPI's interactive API documentation is at `http://127.0.0.1:8001/docs`. In another terminal, the health check can be verified with:

```sh
curl -sS http://127.0.0.1:8001/health
curl -sS http://127.0.0.1:8001/health/db
```

The checked-in Compose password is explicitly a local-development example. Do not expose this configuration beyond the machine.

## 3. Start React frontend (about 1 minute)

In Terminal 3:

```sh
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open `http://127.0.0.1:5173`. The strict port option prevents Vite silently switching to a port that the backend's local CORS configuration does not allow. The API client defaults to `http://127.0.0.1:8001`.

## 4. Add a small synthetic demonstration profile (about 2 minutes)

The repository has an ML synthetic CSV fixture but no database seed command. To create a minimal rule-workflow demonstration, post three synthetic baseline events, rebuild the baseline, then post and analyze one unusual event. Run in Terminal 4 from the repository root. This writes only to the local database configured above; do not substitute a production URL.

```sh
curl -sS -X POST http://127.0.0.1:8001/events \
  -H 'Content-Type: application/json' \
  -d '{"source":"college-demo","external_id":"demo-base-login-001","event_type":"login_success","user_id":"demo.user.001","entity_id":"demo-laptop.001","source_ip":"192.0.2.10","event_time":"2026-10-30T09:00:00Z","raw_event":{"demo":true,"description":"synthetic baseline login"}}'

curl -sS -X POST http://127.0.0.1:8001/events \
  -H 'Content-Type: application/json' \
  -d '{"source":"college-demo","external_id":"demo-base-file-002","event_type":"file_access","user_id":"demo.user.001","entity_id":"demo-laptop.001","source_ip":"192.0.2.10","event_time":"2026-10-30T09:15:00Z","raw_event":{"demo":true,"description":"synthetic file activity"}}'

curl -sS -X POST http://127.0.0.1:8001/events \
  -H 'Content-Type: application/json' \
  -d '{"source":"college-demo","external_id":"demo-base-login-003","event_type":"login_success","user_id":"demo.user.001","entity_id":"demo-laptop.001","source_ip":"192.0.2.10","event_time":"2026-10-31T10:00:00Z","raw_event":{"demo":true,"description":"synthetic baseline login"}}'

curl -sS -X POST http://127.0.0.1:8001/baselines/demo.user.001/rebuild

demo_event_id=$(curl -sS -X POST http://127.0.0.1:8001/events \
  -H 'Content-Type: application/json' \
  -d '{"source":"college-demo","external_id":"demo-unusual-login-004","event_type":"login_success","user_id":"demo.user.001","entity_id":"demo-laptop.001","source_ip":"203.0.113.77","event_time":"2026-11-01T02:05:00Z","raw_event":{"demo":true,"description":"synthetic unfamiliar-IP unusual-hour login"}}' \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')

curl -sS -X POST "http://127.0.0.1:8001/anomalies/analyze/${demo_event_id}"
```

The baseline contains the known IP and familiar event types at UTC hours 09 and 10. The final synthetic login uses a documentation-reserved IP and an unseen hour, so the current rule score should be 40 + 30 = 70 and severity `high`; the endpoint should return an `alert_id`. This is a deterministic illustration of the implemented rules, not an ML prediction. If `jq` is installed, append `| jq` to the `curl` commands for formatted JSON; `jq` is optional.

## 5. Presentation flow (6–8 minutes)

### SOC Overview (about 1 minute)

Show global total/open/investigating/resolved alert counts and severity distribution. Explain that these totals come from alert API pagination metadata. Recent alerts and events are separate backend lists; the alert API has no time-range filter.

### Security Alerts and investigation (about 1.5 minutes)

Open **Security Alerts**. Show the synthetic high-severity rule alert. Open its detail view and point out severity, rule risk score, explanation, linked event ID, evidence, status control, feedback form, and feedback history. Optionally change status to `investigating` and submit a test verdict using a fictional analyst ID. The ID is client-supplied because the project has no authentication system.

### Security Events (about 1 minute)

Open **Events**. Locate `demo.user.001`, open the synthetic login record, and show event ID, type, user/entity, source IP, timestamp, source, and explicitly synthetic payload metadata. Event filters are limited to user ID, event type, and source.

### User Analytics and baseline (about 1.5 minutes)

Open **User Analytics**, select/enter `demo.user.001`, and show observed event and alert activity plus the saved baseline. Explain that the UI's suggestions are based on a sample of API results, not a user directory. The baseline is rebuilt from all stored user events; for this example it was rebuilt before the unusual event was added. If demonstrating rebuild, confirm only when the audience understands it replaces the saved all-history aggregate.

### Offline Isolation Forest demo (about 1 minute)

First use the ML Analytics sidebar page and click **Run offline demonstration**. It calls read-only `GET /ml-analytics/demo`, which reads only the bundled synthetic fixture, computes results in memory, and does not query PostgreSQL or write artifacts. Alternatively, run the same service from Terminal 4:

```sh
cd backend
PYTHONPATH=. ../.venv312/bin/python -m scripts.demo_ml_anomaly
```

Point out that this script trains from the synthetic fixture's chronological training split, scores four in-memory examples, and evaluates the held-out synthetic test partition. It does not query PostgreSQL, create alerts, or persist artifacts. The UI and CLI show the seven features, decision scores, threshold decisions, and synthetic benchmark metrics. Do not call a score a probability or claim the context is feature attribution.

### Evaluation result and limitations (about 1 minute)

Run (or display pre-generated results from) the synthetic benchmark:

```sh
cd backend
PYTHONPATH=. ../.venv312/bin/python -m scripts.run_ml_experiment \
  --synthetic-benchmark \
  --fixture scripts/reports/synthetic_events.csv \
  --output-dir /private/tmp/ueba-college-demo-experiment \
  --contamination 0.05 --random-state 42 --n-estimators 100
```

Report precision 0.5641, recall 0.8800, F1 0.6875, FPR 0.0881 and confusion matrix `[[176,17],[3,22]]`, with actual classes `[normal, anomaly]` in rows and predictions in columns. The results use synthetic scenario labels only. Mention five-seed mean F1 0.7082 and leave-one-user-out FPR 15.0% as evidence that performance varies across seeds/users. Snapshot-mode records have no trusted labels and are not reported with supervised metrics.

## 6. Closing summary (30 seconds)

The project demonstrates event storage, an explainable user-baseline rule path, alert investigation, and analyst feedback. The ML path is reproducible but experimental and offline. Future work would require authentication, representative and labeled data, point-in-time baselines, wider validation, and a separate approval process before any inference/alert integration.

## Time plan

| Segment | Target |
| --- | ---: |
| Start/check services and create synthetic profile | 4 minutes |
| Overview, alerts, event detail, user baseline | 5.5 minutes |
| Offline ML demo and benchmark | 3 minutes |
| Limitations/conclusion | 1 minute |
| **Total** | **13.5 minutes** |

