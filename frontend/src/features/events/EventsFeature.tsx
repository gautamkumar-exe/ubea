import { useCallback, useEffect, useState, type FormEvent, type ReactNode } from "react";
import {
  getEvents,
  ingestEvent,
  type SecurityEvent,
  type SecurityEventCreate,
  type SecurityEventListResponse,
} from "../../api";
import { errorMessage, formatDate, localDateTimeInputValue } from "../../lib/format";
import { EventDetailsDialog } from "./EventDetailsDialog";

interface EventsFeatureProps {
  refreshToken: number;
  onAnalyzeEvent: (eventId: string) => void;
  onAskAi?: (eventId: string) => void;
}

interface EventFilters {
  user_id: string;
  event_type: string;
  source: string;
}

interface EventsResourceState {
  response: SecurityEventListResponse | null;
  responseKey: string;
  error: string;
  errorKey: string;
  loadingKey: string;
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

function EventsSection({ children, eyebrow, title, description, action, className = "" }: {
  children: ReactNode;
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <section className={`surface-card events-section ${className}`}>
      <header className="surface-card__header">
        <div>
          <div className="eyebrow">{eyebrow}</div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        {action}
      </header>
      {children}
    </section>
  );
}

export function EventsFeature({ refreshToken, onAnalyzeEvent, onAskAi }: EventsFeatureProps) {
  const [eventsState, setEventsState] = useState<EventsResourceState>({
    response: null,
    responseKey: "",
    error: "",
    errorKey: "",
    loadingKey: "",
  });
  const [offset, setOffset] = useState(0);
  const [retryToken, setRetryToken] = useState(0);
  const [pollToken, setPollToken] = useState(0);
  const [ingestReloadToken, setIngestReloadToken] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [ingestError, setIngestError] = useState("");
  const [success, setSuccess] = useState("");
  const [filters, setFilters] = useState<EventFilters>(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState<EventFilters>(EMPTY_FILTERS);
  const [form, setForm] = useState(initialEventForm);
  const [selectedEvent, setSelectedEvent] = useState<SecurityEvent | null>(null);

  const requestKey = JSON.stringify([appliedFilters, offset]);
  const currentResponse = eventsState.responseKey === requestKey ? eventsState.response : null;
  const currentError = eventsState.errorKey === requestKey ? eventsState.error : "";
  const loading = !currentResponse && !currentError;
  const refreshing = Boolean(currentResponse && eventsState.loadingKey === requestKey);
  const events = currentResponse?.items ?? [];

  useEffect(() => {
    const controller = new AbortController();
    let pollTimer: number | undefined;
    const key = JSON.stringify([appliedFilters, offset]);
    const schedulePoll = () => {
      pollTimer = window.setTimeout(() => setPollToken((current) => current + 1), 15_000);
    };
    setEventsState((current) => ({
      ...current,
      loadingKey: key,
      error: current.errorKey === key ? "" : current.error,
      errorKey: current.errorKey === key ? "" : current.errorKey,
    }));

    getEvents({
      limit: PAGE_SIZE,
      offset,
      user_id: appliedFilters.user_id,
      event_type: appliedFilters.event_type,
      source: appliedFilters.source,
    }, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return;
        setEventsState((current) => ({
          ...current,
          response,
          responseKey: key,
          error: "",
          errorKey: "",
          loadingKey: "",
        }));
        setOffset(response.offset);
        schedulePoll();
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) {
          setEventsState((current) => ({
            ...current,
            error: errorMessage(error, "Unable to load security events."),
            errorKey: key,
            loadingKey: "",
          }));
          schedulePoll();
        }
      });

    return () => {
      controller.abort();
      if (pollTimer !== undefined) window.clearTimeout(pollTimer);
    };
  }, [appliedFilters, offset, refreshToken, retryToken, pollToken, ingestReloadToken]);

  function updateForm<K extends keyof ReturnType<typeof initialEventForm>>(
    key: K,
    value: ReturnType<typeof initialEventForm>[K],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setIngestError("");
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
      setOffset(0);
      setIngestReloadToken((current) => current + 1);
    } catch (error) {
      setIngestError(errorMessage(error, "Unable to ingest the event."));
    } finally {
      setSubmitting(false);
    }
  }

  function applyFilters(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextFilters = {
      user_id: filters.user_id.trim(),
      event_type: filters.event_type.trim(),
      source: filters.source.trim(),
    };
    setOffset(0);
    setAppliedFilters((current) => current.user_id === nextFilters.user_id
      && current.event_type === nextFilters.event_type
      && current.source === nextFilters.source ? current : nextFilters);
  }

  function clearFilters() {
    setFilters(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
    setOffset(0);
  }

  const retry = useCallback(() => setRetryToken((current) => current + 1), []);

  return (
    <div className="page-stack events-feature">
      <EventsSection
        eyebrow="STORED TELEMETRY"
        title="Security events"
        description={currentResponse
          ? `${currentResponse.total.toLocaleString()} events match the applied filters · newest event time first`
          : "Investigate stored event records returned by the backend."}
        className="events-investigation"
        action={<span className="events-refresh-label" role="status">{refreshing ? "Refreshing…" : "Live refresh · 15 sec"}</span>}
      >
        <form className="event-filter-form events-filter-form" onSubmit={applyFilters}>
          <label className="field"><span>User ID</span><input value={filters.user_id} onChange={(event) => setFilters((current) => ({ ...current, user_id: event.target.value }))} placeholder="Filter by user ID" /></label>
          <label className="field"><span>Event type</span><input value={filters.event_type} onChange={(event) => setFilters((current) => ({ ...current, event_type: event.target.value }))} placeholder="Filter by exact event type" /></label>
          <label className="field"><span>Source</span><input value={filters.source} onChange={(event) => setFilters((current) => ({ ...current, source: event.target.value }))} placeholder="Filter by exact source" /></label>
          <div className="filter-actions">
            <button type="submit" className="button button--primary" disabled={loading}>Apply filters</button>
            <button type="button" className="button button--ghost" onClick={clearFilters} disabled={loading}>Clear</button>
          </div>
        </form>
        <p className="events-filter-note">Filters match exact user ID, event type, and source values supported by the events API. Time range and severity filters are unavailable.</p>

        {currentError && currentResponse && <div className="inline-message inline-message--error overview-message overview-message--stale" role="alert">
          <span>Refresh failed; showing the last successful event page. {currentError}</span>
          <button type="button" className="text-button" onClick={retry}>Retry</button>
        </div>}
        {refreshing && <p className="overview-refresh-note" role="status">Refreshing this event page…</p>}
        <div className="table-scroll-region events-table-region" role="region" aria-label="Security events" aria-busy={loading || refreshing} tabIndex={0}>
          <table className="data-table events-table">
            <caption className="sr-only">Security events returned by the backend</caption>
            <thead>
              <tr><th scope="col">Event type / ID</th><th scope="col">User / entity</th><th scope="col">Source IP</th><th scope="col">Event time</th><th scope="col"><span className="sr-only">Actions</span></th></tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={5} className="table-empty" role="status">Loading security events…</td></tr>
              ) : currentError && !currentResponse ? (
                <tr><td colSpan={5} className="table-empty events-error-state" role="alert"><strong>Events are unavailable</strong><span>{currentError}</span><button type="button" className="button button--secondary" onClick={retry}>Retry</button></td></tr>
              ) : events.length === 0 ? (
                <tr><td colSpan={5} className="table-empty"><strong>No events found</strong><span>{currentResponse?.total ? "The backend returned no events for this page." : "No security events match these filters."}</span></td></tr>
              ) : events.map((item) => (
                <tr key={item.id}>
                  <td className="events-primary-cell">
                    <button type="button" className="table-link" onClick={() => setSelectedEvent(item)}>{item.event_type}</button>
                    <span className="cell-secondary mono">Event ID: {item.id}</span>
                    <span className="cell-secondary mono">External ID: {item.external_id}</span>
                    <span className="cell-secondary">Source: {item.source}</span>
                  </td>
                  <td><span className="table-primary mono">{item.user_id ?? "—"}</span><span className="cell-secondary mono">Entity: {item.entity_id ?? "—"}</span></td>
                  <td className="mono">{item.source_ip ?? "—"}</td>
                  <td className="date-cell"><time dateTime={item.event_time}>{formatDate(item.event_time)}</time></td>
                  <td><div className="events-row-actions">
                    <button type="button" className="button button--table" onClick={() => setSelectedEvent(item)}>Details</button>
                    <button type="button" className="button button--table" onClick={() => onAnalyzeEvent(item.id)}>Analyze <span aria-hidden="true">→</span></button>
                  </div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <footer className="pagination-bar">
          <span>{currentResponse
            ? `Showing ${events.length ? currentResponse.offset + 1 : 0}–${currentResponse.offset + events.length} of ${currentResponse.total.toLocaleString()}`
            : "Showing —"}</span>
          <div>
            <button type="button" className="button button--secondary" disabled={!currentResponse || currentResponse.offset === 0 || loading} onClick={() => setOffset(Math.max(0, (currentResponse?.offset ?? 0) - (currentResponse?.limit ?? PAGE_SIZE)))}>Previous</button>
            <button type="button" className="button button--secondary" disabled={!currentResponse || currentResponse.offset + events.length >= currentResponse.total || loading} onClick={() => setOffset((currentResponse?.offset ?? 0) + (currentResponse?.limit ?? PAGE_SIZE))}>Next</button>
          </div>
        </footer>
      </EventsSection>

      <EventsSection eyebrow="EVENT PIPELINE" title="Ingest a security event" description="Validate and store telemetry before running event analysis." className="events-ingestion">
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
        {ingestError && <div className="inline-message inline-message--error" role="alert">{ingestError}</div>}
        {success && <div className="inline-message inline-message--success" role="status">{success}</div>}
      </EventsSection>

      {selectedEvent && <EventDetailsDialog event={selectedEvent} onClose={() => setSelectedEvent(null)} onAnalyze={() => onAnalyzeEvent(selectedEvent.id)} onAskAi={onAskAi} />}
    </div>
  );
}
