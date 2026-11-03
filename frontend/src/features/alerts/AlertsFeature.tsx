import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getAlerts,
  updateAlertStatus,
  type Alert,
  type AlertListFilters,
  type AlertSeverity,
  type AlertStatus,
} from "../../api";
import { AlertTable } from "../../components/AlertTable";
import { MetricCard } from "../../components/MetricCard";
import { AlertDetailsDialog } from "./AlertDetailsDialog";
import { errorMessage } from "../../lib/format";

interface AlertsFeatureProps {
  mode: "overview" | "alerts";
  refreshToken: number;
  onAskAi?: (alertId: string) => void;
}

const STATUSES: AlertStatus[] = ["open", "investigating", "resolved", "dismissed"];
const SEVERITIES: AlertSeverity[] = ["critical", "high", "medium", "low"];
const PAGE_SIZE = 50;
const REFRESH_INTERVAL_MS = 15_000;

export function AlertsFeature({ mode, refreshToken, onAskAi }: AlertsFeatureProps) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loadedKey, setLoadedKey] = useState("");
  const [serverTotal, setServerTotal] = useState(0);
  const [serverLimit, setServerLimit] = useState(PAGE_SIZE);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState<AlertSeverity | "all">("all");
  const [statusFilter, setStatusFilter] = useState<AlertStatus | "all">("all");
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const activeRequest = useRef<{ key: string; controller: AbortController } | null>(null);

  const serverFilters = useMemo<AlertListFilters>(() => ({
    ...(severityFilter !== "all" ? { severity: severityFilter } : {}),
    ...(statusFilter !== "all" ? { status: statusFilter } : {}),
  }), [severityFilter, statusFilter]);
  const requestKey = `${offset}:${serverFilters.severity ?? "all"}:${serverFilters.status ?? "all"}`;

  const loadAlerts = useCallback(async (
    nextOffset: number,
    filters: AlertListFilters,
    backgroundRefresh = false,
    forceRefresh = false,
  ) => {
    const key = `${nextOffset}:${filters.severity ?? "all"}:${filters.status ?? "all"}`;
    const current = activeRequest.current;
    if (current?.key === key && !current.controller.signal.aborted && !forceRefresh) return;

    current?.controller.abort();
    const controller = new AbortController();
    activeRequest.current = { key, controller };
    if (!backgroundRefresh) setLoading(true);
    setError("");

    try {
      const response = await getAlerts(PAGE_SIZE, nextOffset, filters, controller.signal);
      if (activeRequest.current?.controller !== controller) return;
      setAlerts(response.items);
      setLoadedKey(key);
      setServerTotal(response.total);
      setServerLimit(response.limit);
      setOffset(response.offset);
      setSelectedAlert((currentAlert) => currentAlert
        ? response.items.find((alert) => alert.id === currentAlert.id) ?? null
        : null);
    } catch (requestError) {
      if (!controller.signal.aborted && activeRequest.current?.controller === controller) {
        setError(errorMessage(requestError, "Unable to load security alerts."));
      }
    } finally {
      if (activeRequest.current?.controller === controller) {
        activeRequest.current = null;
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    void loadAlerts(offset, serverFilters);
    const timer = window.setInterval(
      () => void loadAlerts(offset, serverFilters, true),
      REFRESH_INTERVAL_MS,
    );
    return () => {
      window.clearInterval(timer);
      if (activeRequest.current?.key === requestKey) {
        activeRequest.current.controller.abort();
      }
    };
  }, [loadAlerts, offset, refreshToken, requestKey, serverFilters]);

  const pageAlerts = loadedKey === requestKey ? alerts : [];
  const pageTotal = loadedKey === requestKey ? serverTotal : 0;

  const filteredAlerts = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return pageAlerts;
    return pageAlerts.filter((alert) => [
      alert.title,
      alert.user_id ?? "",
      alert.explanation,
      alert.id,
    ].some((value) => value.toLowerCase().includes(query)));
  }, [pageAlerts, search]);

  const counts = useMemo(() => ({
    active: pageAlerts.filter((alert) => alert.status === "open" || alert.status === "investigating").length,
    critical: pageAlerts.filter((alert) => alert.severity === "critical").length,
    high: pageAlerts.filter((alert) => alert.severity === "high").length,
  }), [pageAlerts]);

  async function handleStatusChange(alert: Alert, status: AlertStatus) {
    const updated = await updateAlertStatus(alert.id, status);
    setAlerts((current) => current.map((item) => item.id === updated.id ? updated : item));
    setSelectedAlert(updated);

    if (serverFilters.status && serverFilters.status !== updated.status) {
      setLoadedKey("");
      setSelectedAlert(null);
      void loadAlerts(offset, serverFilters, false, true);
    }
  }

  function updateSeverityFilter(value: AlertSeverity | "all") {
    setSelectedAlert(null);
    setSeverityFilter(value);
    setOffset(0);
  }

  function updateStatusFilter(value: AlertStatus | "all") {
    setSelectedAlert(null);
    setStatusFilter(value);
    setOffset(0);
  }

  const emptyState = search.trim() && filteredAlerts.length === 0 && pageAlerts.length > 0
    ? "No loaded alert on this page matches your search. Try another page or clear the search."
    : pageTotal === 0
      ? "No alerts match the selected severity and status filters."
      : "No alert records were returned for this page.";

  return (
    <div className="page-stack">
      {mode === "overview" && <section className="metric-grid" aria-label="Alert metrics">
        <MetricCard label="Total alerts" value={pageTotal} helper="Records matching server filters" tone="accent" symbol="◈" />
        <MetricCard label="Active alerts" value={counts.active} helper="Open or investigating on this page" tone="warning" symbol="◷" />
        <MetricCard label="Critical alerts" value={counts.critical} helper="Critical on this page" tone="danger" symbol="!" />
        <MetricCard label="High severity" value={counts.high} helper="High severity on this page" tone="warning" symbol="↑" />
      </section>}

      <section className="surface-card alert-queue">
        <header className="surface-card__header">
          <div>
            <div className="eyebrow">DETECTION OUTPUT</div>
            <h2>{mode === "overview" ? "Recent security alerts" : "Security alerts"}</h2>
            <p>{pageTotal.toLocaleString()} records match server filters · {filteredAlerts.length} shown after page search</p>
          </div>
          <div className="refresh-state" role="status">
            <span className={`status-dot ${error ? "status-dot--unavailable" : loading ? "status-dot--checking" : "status-dot--connected"}`} aria-hidden="true" />
            {loading ? "Loading alerts" : error ? "Refresh issue" : "Auto-refresh every 15 seconds"}
          </div>
        </header>

        {error && pageAlerts.length > 0 && <div className="inline-message inline-message--error alert-queue__error" role="alert">
          <span>{error}</span>
          <button type="button" className="text-button" onClick={() => void loadAlerts(offset, serverFilters)}>Retry</button>
        </div>}

        <div className="table-toolbar">
          <label className="search-field">
            <span aria-hidden="true">⌕</span>
            <input
              aria-label="Search loaded alerts"
              placeholder="Search this page by alert, user, explanation, or ID"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>
          <div className="filter-controls">
            <label className="visually-label">Severity
              <select aria-label="Filter alerts by severity" value={severityFilter} onChange={(event) => updateSeverityFilter(event.target.value as AlertSeverity | "all")}>
                <option value="all">All severities</option>
                {SEVERITIES.map((severity) => <option key={severity} value={severity}>{severity[0].toUpperCase() + severity.slice(1)}</option>)}
              </select>
            </label>
            <label className="visually-label">Status
              <select aria-label="Filter alerts by status" value={statusFilter} onChange={(event) => updateStatusFilter(event.target.value as AlertStatus | "all")}>
                <option value="all">All statuses</option>
                {STATUSES.map((status) => <option key={status} value={status}>{status.replaceAll("_", " ")}</option>)}
              </select>
            </label>
          </div>
        </div>
        <p className="alert-search-scope">Severity and status apply across server results. Text search applies only to the currently loaded page.</p>

        <AlertTable
          alerts={filteredAlerts}
          loading={loading}
          error={error}
          emptyMessage={emptyState}
          onRetry={() => void loadAlerts(offset, serverFilters)}
          onSelect={setSelectedAlert}
        />
        <footer className="pagination-bar">
          <span>
            Showing {pageAlerts.length ? offset + 1 : 0}–{offset + pageAlerts.length} of {pageTotal.toLocaleString()} server-matched alerts
            {search.trim() ? ` · ${filteredAlerts.length} match this page search` : ""}
          </span>
          <div>
            <button type="button" className="button button--secondary" disabled={offset === 0 || loading} onClick={() => { setSelectedAlert(null); setOffset((current) => Math.max(0, current - serverLimit)); }}>Previous</button>
            <button type="button" className="button button--secondary" disabled={offset + pageAlerts.length >= pageTotal || loading} onClick={() => { setSelectedAlert(null); setOffset((current) => current + serverLimit); }}>Next</button>
          </div>
        </footer>
      </section>

      {selectedAlert && <AlertDetailsDialog alert={selectedAlert} onClose={() => setSelectedAlert(null)} onStatusChange={handleStatusChange} onAskAi={onAskAi} />}
    </div>
  );
}
