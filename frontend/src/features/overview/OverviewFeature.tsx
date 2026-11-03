import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
  getAlerts,
  getEvents,
  updateAlertStatus,
  type Alert,
  type AlertSeverity,
  type AlertStatus,
  type SecurityEventListResponse,
} from "../../api";
import { AlertTable } from "../../components/AlertTable";
import { MetricCard } from "../../components/MetricCard";
import { AlertDetailsDialog } from "../alerts/AlertDetailsDialog";
import { errorMessage, formatDate } from "../../lib/format";
import { SeverityDistribution } from "./SeverityDistribution";

interface OverviewFeatureProps {
  refreshToken: number;
  onDataChanged: () => void;
  onNavigateToAlerts: () => void;
  onNavigateToEvents: () => void;
}

interface GlobalAlertMetrics {
  total: number;
  open: number;
  investigating: number;
  resolved: number;
  severity: Record<AlertSeverity, number>;
}

interface ResourceState<T> {
  data: T | null;
  dataKey: string;
  error: string;
  errorKey: string;
  refreshingKey: string;
}

interface ResourceResult<T> {
  data: T | null;
  loading: boolean;
  refreshing: boolean;
  error: string;
  retry: () => void;
}

const PAGE_SIZE = 10;
const REFRESH_INTERVAL_MS = 15_000;
const SEVERITIES: AlertSeverity[] = ["critical", "high", "medium", "low"];

async function getGlobalAlertMetrics(signal: AbortSignal): Promise<GlobalAlertMetrics> {
  const [all, open, investigating, resolved, critical, high, medium, low] = await Promise.all([
    getAlerts(1, 0, {}, signal),
    getAlerts(1, 0, { status: "open" }, signal),
    getAlerts(1, 0, { status: "investigating" }, signal),
    getAlerts(1, 0, { status: "resolved" }, signal),
    getAlerts(1, 0, { severity: "critical" }, signal),
    getAlerts(1, 0, { severity: "high" }, signal),
    getAlerts(1, 0, { severity: "medium" }, signal),
    getAlerts(1, 0, { severity: "low" }, signal),
  ]);

  return {
    total: all.total,
    open: open.total,
    investigating: investigating.total,
    resolved: resolved.total,
    severity: {
      critical: critical.total,
      high: high.total,
      medium: medium.total,
      low: low.total,
    },
  };
}

function usePollingResource<T>(
  key: string,
  refreshToken: number,
  load: (signal: AbortSignal) => Promise<T>,
): ResourceResult<T> {
  const [state, setState] = useState<ResourceState<T>>({
    data: null,
    dataKey: "",
    error: "",
    errorKey: "",
    refreshingKey: "",
  });
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    let inFlight = false;
    let activeController: AbortController | null = null;

    async function run() {
      if (inFlight) return;
      inFlight = true;
      const controller = new AbortController();
      activeController = controller;
      setState((current) => ({
        ...current,
        error: current.errorKey === key ? "" : current.error,
        errorKey: current.errorKey === key ? "" : current.errorKey,
        refreshingKey: current.dataKey === key ? key : "",
      }));

      try {
        const data = await load(controller.signal);
        if (controller.signal.aborted) return;
        setState((current) => ({
          ...current,
          data,
          dataKey: key,
          error: "",
          errorKey: "",
          refreshingKey: "",
        }));
      } catch (error) {
        if (!controller.signal.aborted) {
          setState((current) => ({
            ...current,
            error: errorMessage(error, "Unable to load dashboard data."),
            errorKey: key,
            refreshingKey: "",
          }));
          controller.abort();
        }
      } finally {
        inFlight = false;
        if (activeController === controller) activeController = null;
      }
    }

    void run();
    const timer = window.setInterval(() => void run(), REFRESH_INTERVAL_MS);
    return () => {
      window.clearInterval(timer);
      activeController?.abort();
    };
  }, [key, load, refreshToken, retryToken]);

  const data = state.dataKey === key ? state.data : null;
  const error = state.errorKey === key ? state.error : "";
  return {
    data,
    loading: data === null && error === "",
    refreshing: data !== null && state.refreshingKey === key,
    error,
    retry: () => setRetryToken((current) => current + 1),
  };
}

interface OverviewSectionProps {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}

function OverviewSection({ eyebrow, title, description, action, children, className = "" }: OverviewSectionProps) {
  return (
    <section className={`surface-card overview-section ${className}`}>
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

interface RecentEventsProps {
  data: SecurityEventListResponse | null;
  loading: boolean;
  refreshing: boolean;
  error: string;
  onRetry: () => void;
  onNavigate: () => void;
}

function RecentEvents({ data, loading, refreshing, error, onRetry, onNavigate }: RecentEventsProps) {
  const events = data?.items ?? [];

  return (
    <OverviewSection
      eyebrow="EVENT PIPELINE"
      title="Recent security events"
      description={data ? `Latest ${events.length} of ${data.total.toLocaleString()} stored events · newest first` : "Latest stored events returned by the backend."}
      className="overview-events"
      action={<button type="button" className="button button--secondary" onClick={onNavigate}>Open Events</button>}
    >
      {error && data && <div className="inline-message inline-message--error overview-message overview-message--stale" role="alert">
        <span>{data ? `Refresh failed; showing the last successful event list. ${error}` : `Recent events are unavailable. ${error}`}</span>
        <button type="button" className="text-button" onClick={onRetry}>Retry</button>
      </div>}
      {refreshing && <p className="overview-refresh-note" role="status">Refreshing recent events…</p>}
      <div className="table-scroll-region overview-event-table" role="region" aria-label="Recent security events" aria-busy={loading} tabIndex={0}>
        <table className="data-table">
          <caption className="sr-only">Most recent security events returned by the backend</caption>
          <thead><tr><th scope="col">Event / ID</th><th scope="col">User / Entity</th><th scope="col">Source IP</th><th scope="col">Event time</th></tr></thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={4} className="table-empty" role="status">Loading recent events…</td></tr>
            ) : error && !data ? (
              <tr><td colSpan={4} className="table-empty"><strong>Recent events unavailable</strong><span>{error}</span><button type="button" className="button button--secondary" onClick={onRetry}>Retry</button></td></tr>
            ) : events.length === 0 ? (
              <tr><td colSpan={4} className="table-empty"><strong>No recent events</strong><span>{data?.total ? "The backend returned no events for this page." : "No security events have been returned by the backend."}</span></td></tr>
            ) : events.map((event) => (
              <tr key={event.id}>
                <td><span className="table-primary">{event.event_type}</span><span className="cell-secondary mono">{event.id}</span><span className="cell-secondary">Source: {event.source}</span></td>
                <td className="mono">{event.user_id ?? event.entity_id ?? "—"}</td>
                <td className="mono">{event.source_ip ?? "—"}</td>
                <td className="date-cell"><time dateTime={event.event_time}>{formatDate(event.event_time)}</time></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </OverviewSection>
  );
}

export function OverviewFeature({ refreshToken, onDataChanged, onNavigateToAlerts, onNavigateToEvents }: OverviewFeatureProps) {
  const [severityFilter, setSeverityFilter] = useState<AlertSeverity | "all">("all");
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);

  const loadMetrics = useCallback((signal: AbortSignal) => getGlobalAlertMetrics(signal), []);
  const loadRecentAlerts = useCallback((signal: AbortSignal) => getAlerts(
    PAGE_SIZE,
    0,
    severityFilter === "all" ? {} : { severity: severityFilter },
    signal,
  ), [severityFilter]);
  const loadRecentEvents = useCallback((signal: AbortSignal) => getEvents({ limit: PAGE_SIZE, offset: 0 }, signal), []);

  const metrics = usePollingResource("global-alert-metrics", refreshToken, loadMetrics);
  const alerts = usePollingResource(`recent-alerts:${severityFilter}`, refreshToken, loadRecentAlerts);
  const events = usePollingResource("recent-events", refreshToken, loadRecentEvents);

  async function handleStatusChange(alert: Alert, status: AlertStatus) {
    const updated = await updateAlertStatus(alert.id, status);
    setSelectedAlert(updated);
    onDataChanged();
  }

  const alertItems = alerts.data?.items ?? [];
  const alertEmptyMessage = severityFilter === "all"
    ? "No security alerts have been returned by the backend."
    : `No ${severityFilter} severity alerts have been returned by the backend.`;

  return (
    <div className="page-stack overview-feature">
      <section className="overview-metrics" aria-label="Global alert metrics" aria-busy={metrics.loading}>
        {metrics.loading && !metrics.data ? (
          <div className="overview-state-card" role="status">Loading global alert metrics…</div>
        ) : metrics.error && !metrics.data ? (
          <div className="overview-state-card overview-state-card--error" role="alert">
            <span><strong>Global alert metrics unavailable.</strong> {metrics.error}</span>
            <button type="button" className="text-button" onClick={metrics.retry}>Retry</button>
          </div>
        ) : metrics.data ? (
          <>
            <div className="metric-grid overview-metric-grid">
              <MetricCard label="Total alerts" value={metrics.data.total} helper="Global total returned by the backend" tone="accent" symbol="◈" />
              <MetricCard label="Open alerts" value={metrics.data.open} helper="Global total · open status" tone="danger" symbol="!" />
              <MetricCard label="Investigating" value={metrics.data.investigating} helper="Global total · investigating status" tone="warning" symbol="◷" />
              <MetricCard label="Resolved alerts" value={metrics.data.resolved} helper="Global total · resolved status" tone="success" symbol="✓" />
            </div>
            {metrics.error && <div className="inline-message inline-message--error overview-message" role="alert">
              <span>Metric refresh failed; showing the last successful totals. {metrics.error}</span>
              <button type="button" className="text-button" onClick={metrics.retry}>Retry</button>
            </div>}
          </>
        ) : null}
      </section>

      <div className="overview-upper-grid">
        <OverviewSection
          eyebrow="ALERT POSTURE"
          title="Severity distribution"
          description="Global alert counts returned by severity filters."
          className="overview-severity"
        >
          {metrics.loading && !metrics.data ? (
            <p className="overview-section-state" role="status">Loading severity totals…</p>
          ) : metrics.error && !metrics.data ? (
            <div className="overview-section-state overview-section-state--error" role="alert">
              <span>Severity distribution unavailable. {metrics.error}</span>
              <button type="button" className="text-button" onClick={metrics.retry}>Retry</button>
            </div>
          ) : metrics.data ? (
            <>
              {metrics.error && <p className="overview-refresh-note" role="status">Last successful severity totals are shown while the refresh is unavailable.</p>}
              <SeverityDistribution counts={metrics.data.severity} total={metrics.data.total} />
              <p className="overview-data-note">Counts cover all alert records returned by the backend; percentages use the global total.</p>
            </>
          ) : null}
        </OverviewSection>

        <OverviewSection
          eyebrow="DETECTION OUTPUT"
          title="Recent security alerts"
          description={alerts.data ? `Latest ${alertItems.length} of ${alerts.data.total.toLocaleString()} ${severityFilter === "all" ? "alerts" : `${severityFilter} alerts`} · newest first` : "Latest alerts returned by the backend."}
          className="overview-alerts"
          action={<div className="overview-section__actions">
            <label className="visually-label">Severity
              <select aria-label="Filter recent alerts by severity" value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value as AlertSeverity | "all")}>
                <option value="all">All severities</option>
                {SEVERITIES.map((severity) => <option key={severity} value={severity}>{severity[0].toUpperCase() + severity.slice(1)}</option>)}
              </select>
            </label>
            <button type="button" className="button button--secondary" onClick={onNavigateToAlerts}>All Alerts</button>
          </div>}
        >
          {alerts.error && alerts.data && <div className="inline-message inline-message--error overview-message overview-message--stale" role="alert">
            <span>{alerts.data ? `Refresh failed; showing the last successful alert list. ${alerts.error}` : `Recent alerts are unavailable. ${alerts.error}`}</span>
            <button type="button" className="text-button" onClick={alerts.retry}>Retry</button>
          </div>}
          {alerts.refreshing && <p className="overview-refresh-note" role="status">Refreshing recent alerts…</p>}
          <AlertTable
            alerts={alertItems}
            loading={alerts.loading}
            error={alerts.error}
            emptyMessage={alertEmptyMessage}
            onRetry={alerts.retry}
            onSelect={setSelectedAlert}
          />
          <p className="overview-data-note">Severity filters apply to this list. Dashboard metrics remain global. Date-range filtering is not supported by the current alerts API.</p>
        </OverviewSection>
      </div>

      <RecentEvents
        data={events.data}
        loading={events.loading}
        refreshing={events.refreshing}
        error={events.error}
        onRetry={events.retry}
        onNavigate={onNavigateToEvents}
      />

      {selectedAlert && <AlertDetailsDialog alert={selectedAlert} onClose={() => setSelectedAlert(null)} onStatusChange={handleStatusChange} />}
    </div>
  );
}
