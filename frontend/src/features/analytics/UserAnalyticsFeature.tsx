import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  getAlerts,
  getBaseline,
  getEvents,
  rebuildBaseline,
  updateAlertStatus,
  type Alert,
  type AlertStatus,
  type BaselineResponse,
  type SecurityEvent,
  type SecurityEventListResponse,
} from "../../api";
import { AlertTable } from "../../components/AlertTable";
import { StatusBadge } from "../../components/StatusBadge";
import { errorMessage, formatDate } from "../../lib/format";
import { AlertDetailsDialog } from "../alerts/AlertDetailsDialog";
import { EventDetailsDialog } from "../events/EventDetailsDialog";
import { AnalyticsFeature } from "./AnalyticsFeature";

interface UserAnalyticsFeatureProps {
  initialEventId: string;
  onAnalysisComplete: () => void;
  onAskAi?: (type: "alert" | "event", id: string) => void;
}

interface DiscoveryState {
  users: string[];
  loading: boolean;
  error: string;
  eventTotal: number;
  alertTotal: number;
}

function countMap(value: unknown): Array<[string, number]> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return [];
  return Object.entries(value).filter((entry): entry is [string, number] => typeof entry[1] === "number");
}

function CountTable({ label, values, emptyMessage }: { label: string; values: Array<[string, number]>; emptyMessage: string }) {
  return (
    <div className="baseline-count-table-wrap">
      <h4>{label}</h4>
      {values.length ? (
        <table className="data-table baseline-count-table">
          <thead><tr><th scope="col">Observed value</th><th scope="col">Count</th></tr></thead>
          <tbody>{values.map(([key, count]) => <tr key={key}><td className="mono">{key}</td><td className="mono">{count.toLocaleString()}</td></tr>)}</tbody>
        </table>
      ) : <p className="empty-note">{emptyMessage}</p>}
    </div>
  );
}

export function UserAnalyticsFeature({ initialEventId, onAnalysisComplete, onAskAi }: UserAnalyticsFeatureProps) {
  const [discovery, setDiscovery] = useState<DiscoveryState>({ users: [], loading: true, error: "", eventTotal: 0, alertTotal: 0 });
  const [userInput, setUserInput] = useState("");
  const [selectedUser, setSelectedUser] = useState("");
  const [analysisEventId, setAnalysisEventId] = useState(initialEventId);
  const [userInputError, setUserInputError] = useState("");
  const [activityOffset, setActivityOffset] = useState(0);
  const [baseline, setBaseline] = useState<BaselineResponse | null>(null);
  const [baselineLoading, setBaselineLoading] = useState(false);
  const [baselineError, setBaselineError] = useState("");
  const [baselineLookupNotFound, setBaselineLookupNotFound] = useState(false);
  const [baselineMessage, setBaselineMessage] = useState("");
  const [confirmRebuild, setConfirmRebuild] = useState(false);
  const [rebuildBusy, setRebuildBusy] = useState(false);
  const [alerts, setAlerts] = useState<Awaited<ReturnType<typeof getAlerts>> | null>(null);
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [alertsError, setAlertsError] = useState("");
  const [events, setEvents] = useState<SecurityEventListResponse | null>(null);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [eventsError, setEventsError] = useState("");
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<SecurityEvent | null>(null);
  const requestSequence = useRef(0);

  useEffect(() => {
    let active = true;
    setDiscovery((current) => ({ ...current, loading: true, error: "" }));
    Promise.allSettled([
      getEvents({ limit: 100, offset: 0 }),
      getAlerts(100, 0),
    ]).then(([eventResult, alertResult]) => {
      if (!active) return;
      const eventsData = eventResult.status === "fulfilled" ? eventResult.value : null;
      const alertsData = alertResult.status === "fulfilled" ? alertResult.value : null;
      const users = new Set<string>();
      eventsData?.items.forEach((event) => { if (event.user_id?.trim()) users.add(event.user_id); });
      alertsData?.items.forEach((alert) => { if (alert.user_id?.trim()) users.add(alert.user_id); });
      const errors = [
        eventResult.status === "rejected" ? errorMessage(eventResult.reason, "Event identifiers could not be loaded.") : "",
        alertResult.status === "rejected" ? errorMessage(alertResult.reason, "Alert identifiers could not be loaded.") : "",
      ].filter(Boolean);
      setDiscovery({
        users: [...users].sort((left, right) => left.localeCompare(right)),
        loading: false,
        error: errors.join(" "),
        eventTotal: eventsData?.total ?? 0,
        alertTotal: alertsData?.total ?? 0,
      });
    });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (initialEventId) setAnalysisEventId(initialEventId);
  }, [initialEventId]);

  async function loadUser(userId: string, offset = 0) {
    const normalized = userId.trim();
    if (!normalized) {
      setUserInputError("Enter or select a user ID first.");
      return;
    }
    const sequence = ++requestSequence.current;
    setSelectedUser(normalized);
    setUserInput(normalized);
    setUserInputError("");
    setActivityOffset(offset);
    setBaseline(null);
    setBaselineLoading(true);
    setBaselineError("");
    setBaselineLookupNotFound(false);
    setBaselineMessage("");
    setConfirmRebuild(false);
    setAlerts(null);
    setAlertsLoading(true);
    setAlertsError("");
    setEvents(null);
    setEventsLoading(true);
    setEventsError("");

    const [baselineResult, alertsResult, eventsResult] = await Promise.allSettled([
      getBaseline(normalized),
      getAlerts(10, offset, { user_id: normalized }),
      getEvents({ limit: 10, offset, user_id: normalized }),
    ]);
    if (sequence !== requestSequence.current) return;

    if (baselineResult.status === "fulfilled") setBaseline(baselineResult.value);
    else {
      const message = errorMessage(baselineResult.reason, "Unable to load this user's baseline.");
      setBaselineError(message);
      setBaselineLookupNotFound(message.includes("(404)"));
    }
    setBaselineLoading(false);

    if (alertsResult.status === "fulfilled") setAlerts(alertsResult.value);
    else setAlertsError(errorMessage(alertsResult.reason, "Unable to load alerts for this user."));
    setAlertsLoading(false);

    if (eventsResult.status === "fulfilled") setEvents(eventsResult.value);
    else setEventsError(errorMessage(eventsResult.reason, "Unable to load events for this user."));
    setEventsLoading(false);
  }

  function handleUserSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void loadUser(userInput, 0);
  }

  async function handleRebuild() {
    if (!selectedUser) return;
    setRebuildBusy(true);
    setConfirmRebuild(false);
    setBaselineError("");
    setBaselineLookupNotFound(false);
    setBaselineMessage("");
    try {
      const result = await rebuildBaseline(selectedUser);
      setBaseline(result);
      setBaselineMessage(`Baseline rebuilt from the stored security events for ${result.user_id}.`);
    } catch (error) {
      setBaselineError(errorMessage(error, "Unable to rebuild this user's baseline."));
      setBaselineLookupNotFound(false);
    } finally {
      setRebuildBusy(false);
    }
  }

  async function handleStatusChange(alert: Alert, status: AlertStatus) {
    const updated = await updateAlertStatus(alert.id, status);
    setSelectedAlert(updated);
    if (selectedUser) void loadUser(selectedUser, activityOffset);
    onAnalysisComplete();
  }

  const userAlerts = alerts?.items ?? [];
  const userEvents = events?.items ?? [];
  const canGoPrevious = activityOffset > 0;
  const canGoNext = Boolean(
    (events && events.offset + events.items.length < events.total)
    || (alerts && alerts.offset + alerts.items.length < alerts.total),
  );
  const baselineValues = baseline?.baseline ?? {};
  const eventCount = typeof baselineValues.event_count === "number" ? baselineValues.event_count : null;
  const activeDays = typeof baselineValues.active_days === "number" ? baselineValues.active_days : null;
  const firstSeen = typeof baselineValues.first_seen === "string" ? baselineValues.first_seen : null;
  const lastSeen = typeof baselineValues.last_seen === "string" ? baselineValues.last_seen : null;
  const eventTypeCounts = countMap(baselineValues.event_type_counts);
  const loginHourCounts = countMap(baselineValues.login_hour_counts_utc)
    .map(([hour, count]) => [`${hour.padStart(2, "0")}:00 UTC`, count] as [string, number]);
  const sourceIpCounts = countMap(baselineValues.source_ip_counts);
  const knownBaselineKeys = new Set(["event_count", "event_type_counts", "login_hour_counts_utc", "source_ip_counts", "active_days", "first_seen", "last_seen"]);
  const extraBaseline = Object.fromEntries(Object.entries(baselineValues).filter(([key]) => !knownBaselineKeys.has(key)));

  return (
    <div className="page-stack user-analytics-feature">
      <section className="surface-card user-discovery-card">
        <header className="surface-card__header">
          <div><div className="eyebrow">IDENTITY CONTEXT</div><h2>Inspect a user</h2><p>Load a baseline and related records using an identifier returned by stored activity.</p></div>
          {selectedUser && <button type="button" className="button button--secondary" onClick={() => void loadUser(selectedUser, activityOffset)} disabled={baselineLoading || alertsLoading || eventsLoading}>Refresh user data</button>}
        </header>
        <form className="user-lookup-form" onSubmit={handleUserSubmit}>
          <label className="field user-lookup-form__input" htmlFor="analytics-user-id"><span>User ID</span><input id="analytics-user-id" list="observed-user-ids" value={userInput} onChange={(event) => setUserInput(event.target.value)} placeholder="Select an observed ID or enter a user ID" autoComplete="off" /></label>
          <datalist id="observed-user-ids">{discovery.users.map((user) => <option key={user} value={user} />)}</datalist>
          <button type="submit" className="button button--primary" disabled={discovery.loading || !userInput.trim()}>Load user</button>
        </form>
        <p className="user-discovery-note">No user directory or global user aggregation is available. Suggestions come from the first 100 events and first 100 alerts returned by the APIs ({discovery.eventTotal.toLocaleString()} events and {discovery.alertTotal.toLocaleString()} alerts exist globally); this is a sample, not a complete user list.</p>
        {discovery.loading && <p className="overview-refresh-note" role="status">Discovering identifiers from recent events and alerts…</p>}
        {discovery.error && <div className="inline-message inline-message--error user-analytics-message" role="alert"><span>Some identifiers may be unavailable. {discovery.error}</span></div>}
        {!discovery.loading && discovery.users.length === 0 && !discovery.error && <p className="empty-note user-discovery-empty">No user IDs were returned in the sampled event and alert records. You can still enter an ID directly.</p>}
        {userInputError && <div className="inline-message inline-message--error user-analytics-message" role="alert">{userInputError}</div>}
      </section>

      {selectedUser ? <>
        <section className="surface-card baseline-card">
          <header className="surface-card__header">
            <div><div className="eyebrow">BEHAVIORAL BASELINE</div><h2>{selectedUser}</h2><p>Baseline values are computed from stored events for this user. They are distinct from live activity below.</p></div>
            {baseline && <StatusBadge value={baseline.status} kind="generic" />}
          </header>
          <div className="baseline-actions">
            <button type="button" className="button button--secondary" onClick={() => void loadUser(selectedUser, activityOffset)} disabled={baselineLoading || rebuildBusy}>Load baseline</button>
            <button type="button" className="button button--primary" onClick={() => setConfirmRebuild(true)} disabled={baselineLoading || rebuildBusy}>{rebuildBusy ? "Rebuilding…" : "Rebuild baseline"}</button>
            {baselineLoading && <span className="form-hint" role="status">Loading baseline…</span>}
          </div>
          {confirmRebuild && <div className="baseline-confirm" role="group" aria-labelledby="baseline-confirm-title">
            <div><strong id="baseline-confirm-title">Confirm baseline rebuild</strong><p>This recalculates and replaces the saved baseline using all stored security events for {selectedUser}.</p></div>
            <div><button type="button" className="button button--primary" onClick={() => void handleRebuild()} disabled={rebuildBusy}>Confirm rebuild</button><button type="button" className="button button--ghost" onClick={() => setConfirmRebuild(false)} disabled={rebuildBusy}>Cancel</button></div>
          </div>}
          {baselineError && <div className="inline-message inline-message--error user-analytics-message" role="alert">
            <span>{baselineLookupNotFound ? "No saved baseline was found for this ID. If stored events exist, rebuild to create one." : baselineError}</span>
            {!baselineLookupNotFound && <button type="button" className="text-button" onClick={() => void loadUser(selectedUser, activityOffset)}>Retry</button>}
          </div>}
          {baselineMessage && <div className="inline-message inline-message--success user-analytics-message" role="status">{baselineMessage}</div>}
          {!baselineLoading && !baseline && !baselineError && <div className="baseline-unavailable" role="status">Baseline details are not available yet.</div>}
          {baseline && <div className="baseline-content">
            <div className="baseline-observed-label"><span className="badge">SAVED BASELINE</span><span>Observed history summarized by the baseline API</span></div>
            <div className="baseline-summary-grid">
              <div><span className="result-label">Events in baseline</span><strong>{eventCount?.toLocaleString() ?? "—"}</strong></div>
              <div><span className="result-label">Active UTC days</span><strong>{activeDays?.toLocaleString() ?? "—"}</strong></div>
              <div><span className="result-label">First seen</span><strong>{firstSeen ? formatDate(firstSeen) : "—"}</strong></div>
              <div><span className="result-label">Last seen</span><strong>{lastSeen ? formatDate(lastSeen) : "—"}</strong></div>
            </div>
            <div className="baseline-counts-grid">
              <CountTable label="Event type counts" values={eventTypeCounts} emptyMessage="No event type counts were returned." />
              <CountTable label="Login hour counts · UTC" values={loginHourCounts} emptyMessage="No login hour counts were returned." />
            </div>
            <details className="raw-result baseline-source-ips">
              <summary>Source IP counts from baseline</summary>
              <CountTable label="Observed source IP counts" values={sourceIpCounts} emptyMessage="No source IP counts were returned." />
            </details>
            {Object.keys(extraBaseline).length > 0 && <details className="raw-result">
              <summary>Additional baseline fields returned by API</summary>
              <pre className="code-output">{JSON.stringify(extraBaseline, null, 2)}</pre>
            </details>}
          </div>}
        </section>

        <div className="user-activity-grid">
          <section className="surface-card user-activity-card">
            <header className="surface-card__header">
              <div><div className="eyebrow">OBSERVED ACTIVITY</div><h2>Related alerts</h2><p>{alerts ? `Latest ${userAlerts.length} of ${alerts.total.toLocaleString()} alerts returned for ${selectedUser}.` : `Alerts returned by the backend for ${selectedUser}.`}</p></div>
            </header>
            <AlertTable alerts={userAlerts} loading={alertsLoading} error={alertsError} emptyMessage={`No alerts were returned for ${selectedUser}.`} onRetry={() => void loadUser(selectedUser, activityOffset)} onSelect={setSelectedAlert} />
          </section>

          <section className="surface-card user-activity-card">
            <header className="surface-card__header">
              <div><div className="eyebrow">OBSERVED ACTIVITY</div><h2>Security events</h2><p>{events ? `Latest ${userEvents.length} of ${events.total.toLocaleString()} events returned for ${selectedUser}.` : `Events returned by the backend for ${selectedUser}.`}</p></div>
            </header>
            <div className="table-scroll-region user-event-table-region" role="region" aria-label="Events for selected user" aria-busy={eventsLoading} tabIndex={0}>
              <table className="data-table user-event-table">
                <caption className="sr-only">Security events returned for the selected user</caption>
                <thead><tr><th scope="col">Event / ID</th><th scope="col">Entity</th><th scope="col">Source IP</th><th scope="col">Event time</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
                <tbody>
                  {eventsLoading ? <tr><td colSpan={5} className="table-empty" role="status">Loading user events…</td></tr>
                    : eventsError && !events ? <tr><td colSpan={5} className="table-empty"><strong>User events unavailable</strong><span>{eventsError}</span><button type="button" className="button button--secondary" onClick={() => void loadUser(selectedUser, activityOffset)}>Retry</button></td></tr>
                      : userEvents.length === 0 ? <tr><td colSpan={5} className="table-empty"><strong>No events returned</strong><span>No event records were returned for this user.</span></td></tr>
                        : userEvents.map((event) => <tr key={event.id}>
                          <td><button type="button" className="table-link" onClick={() => setSelectedEvent(event)}>{event.event_type}</button><span className="cell-secondary mono">{event.id}</span></td>
                          <td className="mono">{event.entity_id ?? "—"}</td>
                          <td className="mono">{event.source_ip ?? "—"}</td>
                          <td className="date-cell"><time dateTime={event.event_time}>{formatDate(event.event_time)}</time></td>
                          <td><button type="button" className="button button--table" onClick={() => setSelectedEvent(event)}>Details</button></td>
                        </tr>)}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        {(events || alerts) && <footer className="pagination-bar user-activity-pagination">
          <span>Page records {events ? events.offset + 1 : "—"}–{events ? events.offset + userEvents.length : "—"} for events · {alerts ? `${alerts.offset + 1}–${alerts.offset + userAlerts.length} for alerts` : "alerts unavailable"}</span>
          <div>
            <button type="button" className="button button--secondary" disabled={!canGoPrevious || alertsLoading || eventsLoading} onClick={() => void loadUser(selectedUser, Math.max(0, activityOffset - 10))}>Previous</button>
            <button type="button" className="button button--secondary" disabled={!canGoNext || alertsLoading || eventsLoading} onClick={() => void loadUser(selectedUser, activityOffset + 10)}>Next</button>
          </div>
        </footer>}
      </> : <section className="surface-card user-selection-empty"><p className="empty-note">Select an observed user ID or enter one to load baseline and related activity.</p></section>}

      <AnalyticsFeature initialEventId={analysisEventId} onAnalysisComplete={onAnalysisComplete} />

      {selectedAlert && <AlertDetailsDialog alert={selectedAlert} onClose={() => setSelectedAlert(null)} onStatusChange={handleStatusChange} onAskAi={(alertId) => onAskAi?.("alert", alertId)} />}
      {selectedEvent && <EventDetailsDialog event={selectedEvent} onClose={() => setSelectedEvent(null)} onAnalyze={() => { setAnalysisEventId(selectedEvent.id); setSelectedEvent(null); }} onAskAi={(eventId) => onAskAi?.("event", eventId)} />}
    </div>
  );
}
