import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getAlerts, updateAlertStatus, type Alert, type AlertStatus } from "../../api";
import { AlertTable } from "../../components/AlertTable";
import { MetricCard } from "../../components/MetricCard";
import { AlertDetailsDialog } from "./AlertDetailsDialog";
import { errorMessage } from "../../lib/format";

interface AlertsFeatureProps {
  mode: "overview" | "alerts";
  refreshToken: number;
}

const STATUSES: AlertStatus[] = ["open", "investigating", "resolved", "dismissed"];
const PAGE_SIZE = 50;

export function AlertsFeature({ mode, refreshToken }: AlertsFeatureProps) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [serverTotal, setServerTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const offsetRef = useRef(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);

  const loadAlerts = useCallback(async (nextOffset = offsetRef.current) => {
    setError("");
    try {
      const response = await getAlerts(PAGE_SIZE, nextOffset);
      setAlerts(response.items);
      setServerTotal(response.total);
      offsetRef.current = response.offset;
      setOffset(response.offset);
      setSelectedAlert((current) => current ? response.items.find((alert) => alert.id === current.id) ?? null : null);
    } catch (error) {
      setError(errorMessage(error, "Unable to load security alerts."));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadAlerts();
    const timer = window.setInterval(() => void loadAlerts(), 15_000);
    return () => window.clearInterval(timer);
  }, [loadAlerts, refreshToken]);

  const filteredAlerts = useMemo(() => {
    const query = search.trim().toLowerCase();
    return alerts.filter((alert) => {
      const matchesStatus = statusFilter === "all" || alert.status === statusFilter;
      const matchesSeverity = severityFilter === "all" || alert.severity === severityFilter;
      const matchesSearch = !query || [alert.title, alert.user_id ?? "", alert.explanation, alert.id].some((value) => value.toLowerCase().includes(query));
      return matchesStatus && matchesSeverity && matchesSearch;
    });
  }, [alerts, search, severityFilter, statusFilter]);

  const counts = useMemo(() => ({
    active: alerts.filter((alert) => alert.status === "open" || alert.status === "investigating").length,
    critical: alerts.filter((alert) => alert.severity === "critical").length,
    high: alerts.filter((alert) => alert.severity === "high").length,
  }), [alerts]);

  async function handleStatusChange(alert: Alert, status: AlertStatus) {
    try {
      setError("");
      const updated = await updateAlertStatus(alert.id, status);
      setAlerts((current) => current.map((item) => item.id === updated.id ? updated : item));
      setSelectedAlert(updated);
    } catch (error) {
      setError(errorMessage(error, "Unable to update alert status."));
    }
  }

  return (
    <div className="page-stack">
      {mode === "overview" && <section className="metric-grid" aria-label="Alert metrics">
        <MetricCard label="Total alerts" value={serverTotal} helper="Records reported by API" tone="accent" symbol="◈" />
        <MetricCard label="Active alerts" value={counts.active} helper="Open or under investigation" tone="warning" symbol="◷" />
        <MetricCard label="Critical alerts" value={counts.critical} helper="Critical on current page" tone="danger" symbol="!" />
        <MetricCard label="High severity" value={counts.high} helper="High severity on current page" tone="warning" symbol="↑" />
      </section>}

      <section className="surface-card">
        <header className="surface-card__header">
          <div><div className="eyebrow">DETECTION OUTPUT</div><h2>{mode === "overview" ? "Recent security alerts" : "All security alerts"}</h2><p>{filteredAlerts.length} matching on this page · {serverTotal.toLocaleString()} total records</p></div>
          <div className="refresh-state"><span className="status-dot status-dot--connected" /> Auto-refresh every 15 seconds</div>
        </header>
        {error && <div className="inline-message inline-message--error" role="alert"><span>{error}</span><button type="button" className="text-button" onClick={() => void loadAlerts()}>Retry</button></div>}
        <div className="table-toolbar">
          <label className="search-field"><span aria-hidden="true">⌕</span><input aria-label="Search alerts" placeholder="Search by alert, user, explanation, or ID" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
          <div className="filter-controls">
            <label className="visually-label">Severity<select aria-label="Filter by severity" value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)}><option value="all">All severities</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></select></label>
            <label className="visually-label">Status<select aria-label="Filter by status" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="all">All statuses</option>{STATUSES.map((status) => <option key={status} value={status}>{status.replaceAll("_", " ")}</option>)}</select></label>
          </div>
        </div>
        <AlertTable alerts={filteredAlerts} loading={loading} onSelect={setSelectedAlert} />
        <footer className="pagination-bar"><span>Showing {alerts.length ? offset + 1 : 0}–{offset + alerts.length} of {serverTotal.toLocaleString()} · {filteredAlerts.length} match current filters</span><div><button type="button" className="button button--secondary" disabled={offset === 0 || loading} onClick={() => void loadAlerts(Math.max(0, offset - PAGE_SIZE))}>Previous</button><button type="button" className="button button--secondary" disabled={offset + alerts.length >= serverTotal || loading} onClick={() => void loadAlerts(offset + PAGE_SIZE)}>Next</button></div></footer>
      </section>

      {selectedAlert && <AlertDetailsDialog alert={selectedAlert} onClose={() => setSelectedAlert(null)} onStatusChange={handleStatusChange} />}
    </div>
  );
}
