import type { AlertSeverity } from "../../api";

const SEVERITIES: { value: AlertSeverity; label: string }[] = [
  { value: "critical", label: "Critical" },
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

interface SeverityDistributionProps {
  counts: Record<AlertSeverity, number>;
  total: number;
}

export function SeverityDistribution({ counts, total }: SeverityDistributionProps) {
  if (total === 0) {
    return <p className="empty-note overview-inline-empty">No alerts are currently available for severity distribution.</p>;
  }

  return (
    <div className="severity-distribution" aria-label="Global alert severity distribution">
      {SEVERITIES.map(({ value, label }) => {
        const count = counts[value];
        const percent = (count / total) * 100;
        return (
          <div className="severity-distribution__row" key={value}>
            <span className={`severity-distribution__label severity-distribution__label--${value}`}>{label}</span>
            <span className="severity-distribution__track" role="img" aria-label={`${label}: ${count} alerts, ${percent.toFixed(1)} percent of total`}>
              <span className={`severity-distribution__fill severity-distribution__fill--${value}`} style={{ width: `${percent}%` }} />
            </span>
            <strong>{count.toLocaleString()}</strong>
            <small>{percent.toFixed(1)}%</small>
          </div>
        );
      })}
    </div>
  );
}
