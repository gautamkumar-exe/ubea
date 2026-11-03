# UEBA AI SOC Assistant

## Purpose and architecture

The AI SOC Assistant is a separate, advisory investigation feature. FastAPI serves `GET /ai-assistant/status` and `POST /ai-assistant/chat`. The service reads alert, security-event, and user-baseline records through the existing SQLAlchemy session and uses the official OpenAI Python SDK pointed at Groq's OpenAI-compatible API, calling its Responses API. It does not use the experimental Isolation Forest, operational rule detection, internal HTTP calls, or subprocesses.

The frontend keeps conversation history in memory for the current page session. No conversation database table is created. The UI distinguishes provider-generated interpretation from backend record references.

## Configuration

From `backend/`, copy `.env.example` to `.env`, keep `.env` local, and set:

```dotenv
GROQ_API_KEY=your_groq_key_here
GROQ_MODEL=openai/gpt-oss-20b
GROQ_MAX_OUTPUT_TOKENS=900
GROQ_TIMEOUT_SECONDS=30
```

`GROQ_MODEL` can be changed without code edits. The default is `openai/gpt-oss-20b`; the Groq developer API base URL is `https://api.groq.com/openai/v1`. The backend never returns the API key. Do not put it in Vite variables or frontend code. If the key is absent, the status endpoint reports `not_configured` and all other platform features continue to work. Groq developer-tier availability and rate limits are controlled by Groq and may apply.

Install backend requirements (including the official `openai` SDK) and run the app as usual:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set GROQ_API_KEY in backend/.env, then start the existing API command.
uvicorn app.main:app --reload --port 8001
```

Do not commit `.env`, API keys, prompts containing customer data, or conversation exports.

## API

### `GET /ai-assistant/status`

Returns `configured`, `api_key_available`, `model` (only when configured), and `availability_status`. It never returns secret values. This indicates that configuration is present; it does not make a live provider health request.

### `POST /ai-assistant/chat`

Example request:

```json
{
  "message": "Explain the selected alert and suggest next checks.",
  "mode": "explain_alert",
  "alert_id": "00000000-0000-4000-8000-000000000001",
  "history": [
    { "role": "user", "content": "What activity was observed?" },
    { "role": "assistant", "content": "The alert links to a login event." }
  ]
}
```

Supported modes are `general`, `explain_alert`, and `incident_summary`. IDs must be UUIDs. The current message is at most 4,000 characters; optional history is limited to 12 user/assistant messages, each at most 2,000 characters. Extra fields (including client-supplied system instructions) are rejected.

The response includes assistant text, record references and their lookup status, context types used, whether any security context was available, and the configured model ID. Missing records are reported as `not_found`; the assistant is instructed not to make record-specific claims without evidence.

## Evidence retrieval and minimization

- Selected alerts include actual title, severity, score, status, explanation, creation time, and bounded sanitized evidence.
- Selected and linked events include event type, source, time, and minimized user/entity/IP references. Up to eight related events are considered for the selected entity.
- Historical behavioral baselines are reconstructed from same-user security events strictly before the selected alert event time (exclusive cutoff). The assistant does not use the saved `UserProfile.baseline` aggregate for historical claims because baseline rebuild currently summarizes the user's complete event set and can include activity after an alert.
- The alert-triggering or selected event is labeled separately. Related records after the reference time are labeled as subsequent events; same-time records are labeled contemporaneous. Neither is included in the historical baseline. Raw event payloads and raw IP-count maps are excluded.
- User and entity identifiers are replaced with per-request aliases such as `ENTITY-1`; IP literals are replaced by consistent aliases such as `IP-1`.
- Payload, credential, secret, token, authorization, raw-event, and direct identifier fields are omitted from alert evidence. Context size and field lengths are bounded.
- The database code uses read-only `get` and `select` operations. It does not commit, mutate alerts, rebuild baselines, or write events.

Exact selected record IDs are returned to the frontend as context references so the analyst can see which local records were used; those UUIDs are not placed in the model context. Avoid using real sensitive records for a college demo unless you have authorization to send the minimized fields to the configured provider.

## Prompt behavior and safety boundaries

The backend supplies fixed system instructions. User history and database values are treated as untrusted data; embedded instructions in event or alert content must be ignored. The assistant is instructed to distinguish observations from inferences, state uncertainty, recommend analyst checks, and avoid asserting compromise without evidence.

The service constructs the existing OpenAI SDK client with `base_url="https://api.groq.com/openai/v1"` and uses `client.responses.create(...)`, a bounded timeout and output token count, and `store=False`. No tools are passed to the model: there is no web search, shell, SQL execution, database tool, alert status update, automatic remediation, or event write. `store=False` disables this response's API storage behavior; it is not a broader data-retention guarantee.

Provider errors are translated into concise user-facing messages. The service does not log request prompts, security context, or API keys. Provider status codes are used only to select a safe response category.

## Manual testing

1. Start the existing backend and frontend, with a local development database configured.
2. Visit the AI SOC Assistant sidebar entry and check provider status.
3. Submit a general security question.
4. Open an alert in Security Alerts and choose **Ask AI SOC Assistant about this alert**; submit the explain-alert prompt.
5. Open an event in Events and choose **Ask AI SOC Assistant**; ask for a concise event summary.
6. Confirm the context panel shows available record references, or a clear no-context state if a record is missing.
7. Temporarily remove `GROQ_API_KEY` and restart the backend; verify the UI shows an unavailable configuration state while Overview, Alerts, Events, and User Analytics still load.
8. Review that alerts/events remain unchanged after chat requests.

Automated backend tests mock the OpenAI SDK client configured with the Groq base URL and do not require a real API key or network access. Frontend compilation is verified with `npm run build`.

## Limitations

- This is a college-project demonstration, not a validated production SOC copilot.
- The assistant depends on Groq API availability, account access, developer-tier limits, and the configured model.
- The current database has no conversation persistence, tenant/authorization model, or configurable retention workflow.
- Identifier minimization is not anonymization. Alert explanation/evidence can contain sensitive text; direct identifier and known IP references are replaced and payload-like keys are excluded, but data review is still necessary before provider submission.
- Provider output is generated interpretation and may be incorrect. Analysts must verify recommendations against source systems.
- The assistant does not perform automatic threat detection and does not use Isolation Forest predictions.
