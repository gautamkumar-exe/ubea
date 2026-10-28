
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getAlerts,
  getHealth,
  updateAlertStatus,
  type Alert,
} from "./api";
import "./App.css";

type Status = "open" | "investigating" | "resolved" | "dismissed";

const STATUSES: Status[] = [
  "open",
  "investigating",
  "resolved",
  "dismissed",
];

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}

function App() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [apiStatus, setApiStatus] = useState("checking");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    try {
      setError("");

      const [health, response] = await Promise.all([
        getHealth(),
        getAlerts(),
      ]);

      setApiStatus(health.status === "ok" ? "connected" : "unavailable");
      setAlerts(response.items);

      setSelectedAlert((current) => {
        if (!current) return null;
        return response.items.find((item) => item.id === current.id) ?? null;
      });
    } catch (err) {
      setApiStatus("unavailable");
      setError(
        err instanceof Error ? err.message : "Unable to load dashboard data.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
    const timer = window.setInterval(() => void loadData(), 15000);
    return () => window.clearInterval(timer);
  }, [loadData]);

  const filteredAlerts = useMemo(() => {
    const query = search.trim().toLowerCase();

    return alerts.filter((alert) => {
      const matchesStatus =
        statusFilter === "all" || alert.status === statusFilter;
      const matchesSeverity =
        severityFilter === "all" || alert.severity === severityFilter;
      const matchesSearch =
        !query ||
        [
          alert.title,
          alert.user_id ?? "",
          alert.explanation,
          alert.id,
        ].some((value) => value.toLowerCase().includes(query));

      return matchesStatus && matchesSeverity && matchesSearch;
    });
  }, [alerts, statusFilter, severityFilter, search]);

  const counts = useMemo(() => {
    const active = alerts.filter(
      (alert) => alert.status === "open" || alert.status === "investigating",
    );

    return {
      total: alerts.length,
      active: active.length,
      critical: alerts.filter((alert) => alert.severity === "critical").length,
      high: alerts.filter((alert) => alert.severity === "high").length,
    };
  }, [alerts]);

  async function changeStatus(alert: Alert, status: Status) {
    try {
      setError("");
      const updated = await updateAlertStatus(alert.id, status);

      setAlerts((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setSelectedAlert(updated);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to update alert status.",
      );
    }
  }

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">U</div>
          <div>
            <strong>UEBA</strong>
            <span>SECURITY PLATFORM</span>
          </div>
        </div>

        <div className="nav-label">WORKSPACE</div>
        <div className="nav-item active">
          <span>▦</span> Overview
        </div>
        <div className="nav-item">
          <span>◈</span> Security alerts
        </div>
        <div className="nav-item">
          <span>⌁</span> Event activity
        </div>
        <div className="nav-item">
          <span>◎</span> Behavioral analytics
        </div>

        <div className="sidebar-bottom">
          <span className={`status-dot ${apiStatus}`} />
          <div>
            <strong>Backend API</strong>
            <span>{apiStatus}</span>
          </div>
        </div>
      </aside>

      <section className="main-panel">
        <header className="topbar">
          <div>
            <div className="eyebrow">SECURITY OPERATIONS / OVERVIEW</div>
            <h1>Threat monitoring</h1>
            <p>Behavioral anomalies and security alert triage.</p>
          </div>

          <button className="refresh-button" onClick={() => void loadData()}>
            ↻ Refresh data
          </button>
        </header>

        {error && (
          <div className="error-banner">
            <strong>Request failed</strong>
            <span>{error}</span>
            <button onClick={() => void loadData()}>Retry</button>
          </div>
        )}

        <section className="metric-grid">
          <Metric label="TOTAL ALERTS" value={counts.total} detail="Loaded from API" />
          <Metric label="ACTIVE ALERTS" value={counts.active} detail="Open or investigating" />
          <Metric label="CRITICAL" value={counts.critical} detail="Critical severity" />
          <Metric label="HIGH SEVERITY" value={counts.high} detail="High severity" />
        </section>

        <section className="content-card">
          <div className="section-heading">
            <div>
              <div className="eyebrow">DETECTION OUTPUT</div>
              <h2>Security alerts</h2>
              <p>{filteredAlerts.length} matching alerts</p>
            </div>
            <span className="live-indicator">
              <span className="status-dot connected" /> AUTO-REFRESH 15S
            </span>
          </div>

          <div className="filters">
            <input
              aria-label="Search alerts"
              placeholder="Search title, user, explanation or ID..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />

            <select
              aria-label="Filter by severity"
              value={severityFilter}
              onChange={(event) => setSeverityFilter(event.target.value)}
            >
              <option value="all">All severities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>

            <select
              aria-label="Filter by status"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
            >
              <option value="all">All statuses</option>
              {STATUSES.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ALERT</th>
                  <th>USER</th>
                  <th>SEVERITY</th>
                  <th>RISK</th>
                  <th>STATUS</th>
                  <th>CREATED</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={7} className="empty-state">
                      Loading alerts from the backend...
                    </td>
                  </tr>
                ) : filteredAlerts.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="empty-state">
                      No alerts match your filters. Ingest and analyze a test
                      event to generate one.
                    </td>
                  </tr>
                ) : (
                  filteredAlerts.map((alert) => (
                    <tr key={alert.id}>
                      <td>
                        <button
                          className="alert-title"
                          onClick={() => setSelectedAlert(alert)}
                        >
                          {alert.title}
                        </button>
                        <span className="subtext">
                          {alert.id.slice(0, 8)}
                        </span>
                      </td>
                      <td>{alert.user_id ?? "—"}</td>
                      <td>
                        <span className={`severity ${alert.severity}`}>
                          {alert.severity}
                        </span>
                      </td>
                      <td>
                        <div className="risk-cell">
                          <strong>{alert.risk_score}</strong>
                          <div className="risk-track">
                            <div
                              className={`risk-fill ${alert.severity}`}
                              style={{ width: `${alert.risk_score}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td>
                        <span className={`status-pill ${alert.status}`}>
                          {alert.status}
                        </span>
                      </td>
                      <td className="date-cell">
                        {formatDate(alert.created_at)}
                      </td>
                      <td>
                        <button
                          className="row-action"
                          onClick={() => setSelectedAlert(alert)}
                        >
                          Details →
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        {selectedAlert && (
          <div
            className="modal-backdrop"
            onClick={() => setSelectedAlert(null)}
          >
            <section
              className="detail-panel"
              role="dialog"
              aria-modal="true"
              aria-labelledby="detail-title"
              onClick={(event) => event.stopPropagation()}
            >
              <div className="detail-heading">
                <div>
                  <div className="eyebrow">ALERT INVESTIGATION</div>
                  <h2 id="detail-title">Alert details</h2>
                </div>
                <button
                  className="close-button"
                  aria-label="Close alert details"
                  onClick={() => setSelectedAlert(null)}
                >
                  ×
                </button>
              </div>

              <h3>{selectedAlert.title}</h3>
              <div className="detail-badges">
                <span className={`severity ${selectedAlert.severity}`}>
                  {selectedAlert.severity}
                </span>
                <span className={`status-pill ${selectedAlert.status}`}>
                  {selectedAlert.status}
                </span>
                <span className="risk-number">
                  Risk {selectedAlert.risk_score}/100
                </span>
              </div>

              <div className="detail-field">
                <label>Explanation</label>
                <p>{selectedAlert.explanation}</p>
              </div>
              <div className="detail-field">
                <label>User</label>
                <p>{selectedAlert.user_id ?? "Not specified"}</p>
              </div>
              <div className="detail-field">
                <label>Event ID</label>
                <p className="mono">{selectedAlert.event_id ?? "Not linked"}</p>
              </div>
              <div className="detail-field">
                <label>Created</label>
                <p>{formatDate(selectedAlert.created_at)}</p>
              </div>
              <div className="detail-field">
                <label>Evidence</label>
                <pre>{JSON.stringify(selectedAlert.evidence, null, 2)}</pre>
              </div>

              <div className="detail-field">
                <label>Update investigation status</label>
                <select
                  value={selectedAlert.status}
                  onChange={(event) =>
                    void changeStatus(
                      selectedAlert,
                      event.target.value as Status,
                    )
                  }
                >
                  {STATUSES.map((status) => (
                    <option key={status} value={status}>
                      {status}
                    </option>
                  ))}
                </select>
              </div>
            </section>
          </div>
        )}

        <footer>
          UEBA PLATFORM <span>•</span> RULE-BASED DETECTION <span>•</span>{" "}
          DATA REFRESHES EVERY 15 SECONDS
        </footer>
      </section>
    </main>
  );
}

function Metric({
  label,
  value,
  detail,
}: {
  label: string;
  value: number;
  detail: string;
}) {
  return (
    <article className="metric-card">
      <span className="metric-label">{label}</span>
      <strong>{value.toLocaleString()}</strong>
      <span className="metric-detail">{detail}</span>
    </article>
  );
}

export default App;
