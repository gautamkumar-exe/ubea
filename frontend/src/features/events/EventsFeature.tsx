import { useCallback, useEffect, useState, type FormEvent } from "react";
import { getEvents, ingestEvent, type SecurityEvent, type SecurityEventCreate } from "../../api";
import { errorMessage, formatDate, localDateTimeInputValue } from "../../lib/format";

interface EventsFeatureProps {
  refreshToken: number;
  onAnalyzeEvent: (eventId: string) => void;
}

interface EventFilters {
  user_id: string;
  event_type: string;
  source: string;
}

const PAGE_SIZE = 50;

const EMPTY_FILTERS: EventFilters = { user_id: "", event_type: "", source: "" };

const initialEventForm = () => ({
  source: "manual",
  external_id: "",
  event_type: "login",
  user_id: "",
  entity_id: "",
  source_ip: "",
  event_time: localDateTimeInputValue(),
  raw_event: "{}",
});

export function EventsFeature({ refreshToken, onAnalyzeEvent }: EventsFeatureProps) {
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [filters, setFilters] = useState<EventFilters>(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState<EventFilters>(EMPTY_FILTERS);
  const [form, setForm] = useState(initialEventForm);

  const loadEvents = useCallback(async (nextOffset = 0) => {
    setLoading(true);
    setError("");
    try {
      const response = await getEvents({
        limit: PAGE_SIZE,
        offset: nextOffset,
        user_id: appliedFilters.user_id,
        event_type: appliedFilters.event_type,
        source: appliedFilters.source,
      });
      setEvents(response.items);
      setTotal(response.total);
      setOffset(response.offset);
    } catch (error) {
      setError(errorMessage(error, "Unable to load security events."));
    } finally {
      setLoading(false);
    }
  }, [appliedFilters]);

  useEffect(() => {
    void loadEvents(0);
  }, [loadEvents, refreshToken]);

  function updateForm<K extends keyof ReturnType<typeof initialEventForm>>(key: K, value: ReturnType<typeof initialEventForm>[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setSuccess("");

    try {
      const parsed: unknown = JSON.parse(form.raw_event);
      if (!parsed || Array.isArray(parsed) || typeof parsed !== "object") {
        throw new Error("Raw event JSON must be an object, such as {\"action\": \"login\"}.");
      }
      const payload: SecurityEventCreate = {
        source: form.source.trim(),
        external_id: form.external_id.trim(),
        event_type: form.event_type.trim(),
        user_id: form.user_id.trim() || null,
        entity_id: form.entity_id.trim() || null,
        source_ip: form.source_ip.trim() || null,
        event_time: new Date(form.event_time).toISOString(),
        raw_event: parsed as Record<string, unknown>,
      };
      const result = await ingestEvent(payload);
      setSuccess(result.duplicate ? "This event already exists. The duplicate was not stored." : "Event ingested successfully.");
      setForm((current) => ({ ...current, external_id: "" }));
      await loadEvents(0);
    } catch (error) {
      setError(errorMessage(error, "Unable to ingest the event."));
    } finally {
      setSubmitting(false);
    }
  }

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setAppliedFilters({ user_id: filters.user_id.trim(), event_type: filters.event_type.trim(), source: filters.source.trim() });
  }

  return (
    <div className="page-stack">
      <section className="surface-card">
        <header className="surface-card__header">
          <div><div className="eyebrow">EVENT PIPELINE</div><h2>Ingest a security event</h2><p>Validate and store telemetry before running rule-based analysis.</p></div>
        </header>
        <form className="form-grid" onSubmit={handleSubmit}>
          <label className="field"><span>Source <em>Required</em></span><input required maxLength={100} value={form.source} onChange={(event) => updateForm("source", event.target.value)} placeholder="manual, endpoint, identity" /></label>
          <label className="field"><span>External event ID <em>Required</em></span><input required maxLength={255} value={form.external_id} onChange={(event) => updateForm("external_id", event.target.value)} placeholder="demo-login-001" /></label>
          <label className="field"><span>Event type <em>Required</em></span><input required maxLength={100} value={form.event_type} onChange={(event) => updateForm("event_type", event.target.value)} placeholder="login" /></label>
          <label className="field"><span>User ID</span><input value={form.user_id} onChange={(event) => updateForm("user_id", event.target.value)} placeholder="user-001" /></label>
          <label className="field"><span>Entity ID</span><input value={form.entity_id} onChange={(event) => updateForm("entity_id", event.target.value)} placeholder="device or asset ID" /></label>
          <label className="field"><span>Source IP</span><input value={form.source_ip} onChange={(event) => updateForm("source_ip", event.target.value)} placeholder="192.0.2.10" inputMode="decimal" /></label>
          <label className="field"><span>Event time <em>Required</em></span><input required type="datetime-local" value={form.event_time} onChange={(event) => updateForm("event_time", event.target.value)} /></label>
          <label className="field field--span-2"><span>Raw event JSON</span><textarea rows={4} spellCheck={false} value={form.raw_event} onChange={(event) => updateForm("raw_event", event.target.value)} placeholder={'{\n  "action": "login",\n  "result": "success"\n}'} /></label>
          <div className="form-actions"><button className="button button--primary" type="submit" disabled={submitting}>{submitting ? "Ingesting event…" : "Ingest event"}</button><span className="form-hint">Events are stored; analysis is a separate operation.</span></div>
        </form>
        {error && <div className="inline-message inline-message--error" role="alert">{error}</div>}
        {success && <div className="inline-message inline-message--success" role="status">{success}</div>}
      </section>

      <section className="surface-card">
        <header className="surface-card__header surface-card__header--compact">
          <div><div className="eyebrow">STORED TELEMETRY</div><h2>Recent events</h2><p>{total.toLocaleString()} events match the applied filters.</p></div>
          <button type="button" className="button button--secondary" onClick={() => void loadEvents(0)} disabled={loading}>Refresh events</button>
        </header>
        <form className="event-filter-form" onSubmit={applyFilters}>
          <label className="field"><span>User ID</span><input value={filters.user_id} onChange={(event) => setFilters((current) => ({ ...current, user_id: event.target.value }))} placeholder="Filter by user" /></label>
          <label className="field"><span>Event type</span><input value={filters.event_type} onChange={(event) => setFilters((current) => ({ ...current, event_type: event.target.value }))} placeholder="Filter by event type" /></label>
          <label className="field"><span>Source</span><input value={filters.source} onChange={(event) => setFilters((current) => ({ ...current, source: event.target.value }))} placeholder="Filter by source" /></label>
          <div className="filter-actions"><button type="submit" className="button button--primary" disabled={loading}>Apply filters</button><button type="button" className="button button--ghost" onClick={() => { setFilters(EMPTY_FILTERS); setAppliedFilters(EMPTY_FILTERS); }} disabled={loading}>Clear</button></div>
        </form>
        <div className="table-scroll-region" role="region" aria-label="Stored security events" tabIndex={0}>
          <table className="data-table">
            <thead><tr><th scope="col">Event</th><th scope="col">User</th><th scope="col">Source IP</th><th scope="col">Event time</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
            <tbody>
              {loading ? <tr><td colSpan={5} className="table-empty">Loading events…</td></tr> : events.length === 0 ? <tr><td colSpan={5} className="table-empty"><strong>No events found</strong><span>Ingest a security event or clear the applied filters.</span></td></tr> : events.map((item) => (
                <tr key={item.id}><td><span className="table-primary">{item.event_type}</span><span className="cell-secondary mono">{item.id}</span><span className="cell-secondary">Source: {item.source}</span></td><td>{item.user_id ?? "—"}</td><td className="mono">{item.source_ip ?? "—"}</td><td className="date-cell">{formatDate(item.event_time)}</td><td><button type="button" className="button button--table" onClick={() => onAnalyzeEvent(item.id)}>Analyze <span aria-hidden="true">→</span></button></td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <footer className="pagination-bar"><span>Showing {events.length ? offset + 1 : 0}–{offset + events.length} of {total.toLocaleString()}</span><div><button type="button" className="button button--secondary" disabled={offset === 0 || loading} onClick={() => void loadEvents(Math.max(0, offset - PAGE_SIZE))}>Previous</button><button type="button" className="button button--secondary" disabled={offset + events.length >= total || loading} onClick={() => void loadEvents(offset + PAGE_SIZE)}>Next</button></div></footer>
      </section>
    </div>
  );
}
