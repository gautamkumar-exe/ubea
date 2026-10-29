interface MetricCardProps {
  label: string;
  value: number | string;
  helper: string;
  tone?: "neutral" | "danger" | "warning" | "success" | "accent";
  symbol?: string;
}

export function MetricCard({ label, value, helper, tone = "neutral", symbol }: MetricCardProps) {
  return (
    <article className={`metric-card metric-card--${tone}`}>
      <div className="metric-card__topline">
        <span className="metric-card__label">{label}</span>
        {symbol && <span className="metric-card__symbol" aria-hidden="true">{symbol}</span>}
      </div>
      <strong className="metric-card__value">{typeof value === "number" ? value.toLocaleString() : value}</strong>
      <span className="metric-card__helper">{helper}</span>
    </article>
  );
}
