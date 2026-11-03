# UEBA SOC Design Package — Security Review & Required Fixes

## Scope and limitation

This ZIP contains three static HTML/Tailwind design prototypes and a design-system Markdown file. It does **not** contain the React/TypeScript application, FastAPI backend, database models/migrations, authentication implementation, deployment configuration, or tests. Therefore this review can identify risks in the supplied prototype and define required security controls, but it cannot certify or patch vulnerabilities in the running UEBA system.

The HTML files are mockups, not production pages. Their displayed users, IPs, event IDs, alert counts, model versions, API status, and timestamps are illustrative and must never be treated as real telemetry. The updated mockups now label this explicitly and include ML Analytics and AI SOC Assistant navigation placeholders.

## Findings in the supplied design files

### 1. Static data presented as live telemetry — high product/security risk
**Observed:** The mockups hardcode alert IDs, usernames, IP addresses, event counts, risk scores, API connectivity, backend health, pool usage, model versions, and detection explanations.

**Risk:** Analysts may make operational decisions from fabricated data; screenshots or copied UI may be mistaken for a live security console.

**Required fix:** Replace every hardcoded operational value with authenticated API responses. Render `Unknown`, `Unavailable`, or an explicit demo-data banner when no response exists. Never default API/database status to Connected/Healthy. Keep seeded demo data in a separate development-only fixture.

### 2. External runtime dependencies — supply-chain / CSP concern
**Observed:** HTML loads Tailwind from `https://cdn.tailwindcss.com` and fonts/icons from Google Fonts.

**Risk:** Runtime CDN dependency, third-party request disclosure, availability dependency, and weaker Content Security Policy. A compromised third-party asset or unexpected CDN change could affect the UI.

**Required fix:** For production, compile Tailwind locally into the Vite build; self-host or remove external fonts/icons; pin dependencies and lockfile; use dependency scanning. Apply a restrictive CSP, for example `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self' <trusted-api-origin>; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'`. Adjust only for explicitly required origins. Avoid `unsafe-eval`; avoid `unsafe-inline` by using hashes/nonces if inline code is genuinely required.

### 3. Navigation and actions are non-functional
**Observed:** Many links use `href="#"`; buttons are visual-only; no API calls or authorization flow are present.

**Risk:** This is not an exploitable backend vulnerability by itself, but it creates false affordances and can conceal missing access controls.

**Required fix:** Implement real React Router routes and API-backed actions. Hide/disable actions based on server-provided authorization, but always enforce authorization on the backend. Add explicit confirmation for destructive/high-impact actions. Do not implement bulk baseline rebuild or alert changes as unprotected UI-only actions.

### 4. Misleading vendor/protocol label
**Observed:** The design contained “Splunk ES Protocol v8.4.1” despite being a UEBA prototype.

**Risk:** Incorrectly implies Splunk compatibility or a real protocol integration.

**Fix applied:** Replaced it with “UEBA interface prototype”.

### 5. Accessibility and interaction hardening
**Observed:** Static prototype uses dense tables, small text, and non-semantic clickable-looking elements.

**Required fix:** Use semantic buttons/links, visible focus states, keyboard navigation, accessible labels, sufficient contrast, and table captions/headers. Do not use `cursor-pointer` as a substitute for actual behavior.

## Backend and application security controls — mandatory audit checklist

These cannot be verified or fixed from the supplied design ZIP. Audit the actual source before deployment.

### Authentication and authorization
- Require authentication for every non-public API.
- Enforce role-based access control (RBAC) server-side: analyst, senior analyst, administrator, read-only.
- Enforce object-level authorization for event, alert, user, baseline, and feedback IDs to prevent IDOR/BOLA.
- Protect admin, baseline rebuild, model training, model deployment, export, and feedback actions with explicit permissions.
- Use secure session cookies (`HttpOnly`, `Secure`, appropriate `SameSite`) or a well-designed token flow; never store long-lived secrets in browser localStorage.
- Add MFA for privileged accounts in production.

### API and data access
- Validate request bodies, query parameters, sort keys, filters, and pagination with Pydantic.
- Use SQLAlchemy parameterized expressions; never concatenate user input into SQL.
- Do not expose arbitrary SQL or unrestricted database tools to the future AI chatbot.
- Add pagination and maximum page sizes; apply request size limits, timeouts, and rate limits.
- Use CORS allowlists for exact frontend origins; never use wildcard origins with credentials.
- Return generic client errors; do not expose stack traces, SQL, secrets, internal hostnames, or filesystem paths.
- Add CSRF protection when cookie-based authentication is used.
- Restrict file uploads/exports by type, size, authorization, and storage location.

### Secrets and deployment
- Keep database passwords, API keys, JWT/session secrets, and LLM keys in environment variables or a secrets manager; never commit `.env`.
- Ensure `.env`, database dumps, private keys, model artifacts containing sensitive data, and logs are excluded from Git.
- Rotate any secret that has ever been committed or shared.
- Use TLS in deployed environments; restrict PostgreSQL to private network access.
- Run containers and application processes as non-root; use minimal pinned images and scan dependencies/images.
- Disable debug mode and interactive docs in production or protect them with authentication/network controls.
- Configure backups, restore tests, audit logs, and security monitoring.

### UEBA and ML-specific security
- Treat event payloads, usernames, hostnames, IPs, and metadata as untrusted input.
- Protect against event/log injection; sanitize control characters and encode all values on output.
- Detect poisoning attempts, duplicate/replayed events, abnormal ingestion bursts, and baseline manipulation.
- Keep training data provenance, model version, feature schema, training window, and evaluation metrics.
- Separate training from inference; do not automatically retrain on analyst-unreviewed suspicious events.
- Apply access controls to model artifacts and baseline rebuild operations.
- Explain anomaly results with the evidence/features actually used; do not invent reasons.

### Future AI chatbot security
- Treat retrieved event content as untrusted data, not instructions (prompt-injection defense).
- The LLM must not directly execute SQL, shell commands, or arbitrary tools.
- Expose narrow, read-only backend tools with authorization, parameter validation, row limits, and audit logging.
- Apply tenant/user authorization before retrieval, not only after LLM generation.
- Prevent cross-user and cross-tenant data leakage.
- Redact credentials, tokens, personal data, and secrets before sending context to a cloud model.
- Do not allow chatbot responses to perform response actions (disable account, isolate host, close alert) without a separate permission check and explicit human confirmation.
- Cite event IDs/alert IDs and clearly distinguish observed facts from hypotheses.
- Log model/provider/version, retrieval IDs, user, and action metadata without storing unnecessary sensitive prompt contents.

## Required verification before calling the system secure

1. Run unit/integration tests and dependency vulnerability scanning.
2. Test unauthenticated access to every API route.
3. Test role boundaries and object-level access using two separate users.
4. Test SQL injection and stored/reflected XSS paths using safe test fixtures.
5. Test CORS, CSRF (if cookie sessions), rate limits, request-size limits, and error leakage.
6. Verify secrets are absent from Git history and frontend bundles.
7. Verify database is not publicly exposed and production TLS is enforced.
8. Test audit-log coverage for sensitive reads and all state-changing actions.
9. For ML, test poisoning, replay, drift, and model artifact integrity.
10. Before chatbot release, test prompt injection, data exfiltration, unauthorized retrieval, and tool misuse.

## Next required input for an actual code-level security fix

Provide the **actual UEBA application source ZIP** (frontend + backend + Docker/Compose + migrations + tests), excluding `.env`, API keys, passwords, private keys, database dumps, and real customer/security logs. Include a sanitized `.env.example`. With that source, the review can map each route and data model, run static checks, patch confirmed issues, and return a corrected project archive. Do not upload live secrets.
