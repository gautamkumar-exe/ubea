import type { Alert, AlertStatus } from "../api";
import { formatDate, humanize } from "../lib/format";
import { StatusBadge } from "./StatusBadge";

interface AlertTableProps {
  alerts: Alert[];
  loading: boolean;
  error: string;
  emptyMessage: string;
  onRetry: () => void;
  onSelect: (alert: Alert) => void;
}

export function AlertTable({ alerts, loading, error, emptyMessage, onRetry, onSelect }: AlertTableProps) {
  const showErrorState = Boolean(error) && alerts.length === 0 && !loading;

  return (
    <div className="table-scroll-region alert-table-region" role="region" aria-label="Security alerts" aria-busy={loading} tabIndex={0}>
      <table className="data-table alert-table">
        <caption className="sr-only">Security alerts returned by the backend</caption>
        <thead>
          <tr>
            <th scope="col">Alert / ID</th>
            <th scope="col">User</th>
            <th scope="col">Severity</th>
            <th scope="col">Risk</th>
            <th scope="col">Status</th>
            <th scope="col">Created</th>
            <th scope="col"><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {loading && alerts.length === 0 ? (
            <tr><td colSpan={7} className="table-empty" role="status">Loading alerts from the backend…</td></tr>
          ) : showErrorState ? (
            <tr>
              <td colSpan={7} className="table-empty alert-table__error-state">
                <strong>Alerts could not be loaded</strong>
                <span>{error}</span>
                <button type="button" className="button button--secondary" onClick={onRetry}>Retry</button>
              </td>
            </tr>
          ) : alerts.length === 0 ? (
            <tr><td colSpan={7} className="table-empty"><strong>No matching alerts</strong><span>{emptyMessage}</span></td></tr>
          ) : alerts.map((alert) => (
            <tr key={alert.id}>
              <td className="alert-name-cell">
                <button type="button" className="table-link" onClick={() => onSelect(alert)}>{alert.title}</button>
                <span className="cell-secondary mono">{alert.id}</span>
              </td>
              <td><span className="table-primary mono">{alert.user_id ?? "—"}</span></td>
              <td><StatusBadge value={alert.severity} kind="severity" /></td>
              <td>
                <div className="risk-cell">
                  <strong>{alert.risk_score}</strong>
                  <span className="risk-meter" role="img" aria-label={`Risk score ${alert.risk_score} out of 100`}>
                    <span style={{ width: `${Math.max(0, Math.min(100, alert.risk_score))}%` }} />
                  </span>
                </div>
              </td>
              <td><StatusBadge value={humanize(alert.status as AlertStatus)} kind="status" /></td>
              <td className="date-cell"><time dateTime={alert.created_at}>{formatDate(alert.created_at)}</time></td>
              <td><button type="button" className="button button--table" onClick={() => onSelect(alert)}>Investigate <span aria-hidden="true">→</span></button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
