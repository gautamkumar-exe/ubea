import type { Alert, AlertStatus } from "../api";
import { formatDate, humanize } from "../lib/format";
import { StatusBadge } from "./StatusBadge";

interface AlertTableProps {
  alerts: Alert[];
  loading: boolean;
  onSelect: (alert: Alert) => void;
}

export function AlertTable({ alerts, loading, onSelect }: AlertTableProps) {
  return (
    <div className="table-scroll-region" role="region" aria-label="Security alerts" tabIndex={0}>
      <table className="data-table">
        <thead><tr><th scope="col">Alert</th><th scope="col">User</th><th scope="col">Severity</th><th scope="col">Risk</th><th scope="col">Status</th><th scope="col">Created</th><th scope="col"><span className="sr-only">Actions</span></th></tr></thead>
        <tbody>
          {loading ? <tr><td colSpan={7} className="table-empty">Loading alerts from the backend…</td></tr> : alerts.length === 0 ? <tr><td colSpan={7} className="table-empty"><strong>No matching alerts</strong><span>Try changing your filters or ingest and analyze a test event.</span></td></tr> : alerts.map((alert) => (
            <tr key={alert.id}>
              <td className="alert-name-cell"><button type="button" className="table-link" onClick={() => onSelect(alert)}>{alert.title}</button><span className="cell-secondary mono">{alert.id.slice(0, 8)}</span></td>
              <td><span className="table-primary">{alert.user_id ?? "—"}</span></td>
              <td><StatusBadge value={alert.severity} kind="severity" /></td>
              <td><div className="risk-cell"><strong>{alert.risk_score}</strong><span className="risk-meter" aria-label={`Risk score ${alert.risk_score} out of 100`}><span style={{ width: `${Math.max(0, Math.min(100, alert.risk_score))}%` }} /></span></div></td>
              <td><StatusBadge value={humanize(alert.status as AlertStatus)} kind="status" /></td>
              <td className="date-cell">{formatDate(alert.created_at)}</td>
              <td><button type="button" className="button button--table" onClick={() => onSelect(alert)}>Details <span aria-hidden="true">→</span></button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
