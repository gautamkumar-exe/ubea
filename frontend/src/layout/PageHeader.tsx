import type { WorkspacePage } from "./Sidebar";

const PAGE_META: Record<WorkspacePage, { eyebrow: string; title: string; description: string }> = {
  overview: {
    eyebrow: "SECURITY OPERATIONS / OVERVIEW",
    title: "Threat monitoring",
    description: "Review behavioral anomalies and coordinate security alert triage.",
  },
  alerts: {
    eyebrow: "SECURITY OPERATIONS / ALERT MANAGEMENT",
    title: "Security alerts",
    description: "Search, prioritize, investigate, and resolve detected activity.",
  },
  events: {
    eyebrow: "TELEMETRY / EVENT PIPELINE",
    title: "Event activity",
    description: "Ingest and inspect security events before running rule-based analysis.",
  },
  analytics: {
    eyebrow: "DETECTION / BEHAVIORAL ANALYTICS",
    title: "Behavioral analytics",
    description: "Manage user baselines and investigate events with the rule-based engine.",
  },
};

interface PageHeaderProps {
  page: WorkspacePage;
  onRefresh: () => void;
}

export function PageHeader({ page, onRefresh }: PageHeaderProps) {
  const meta = PAGE_META[page];
  return (
    <header className="page-header">
      <div className="page-header__copy">
        <div className="eyebrow">{meta.eyebrow}</div>
        <h1>{meta.title}</h1>
        <p>{meta.description}</p>
      </div>
      <button type="button" className="button button--secondary page-header__refresh" onClick={onRefresh}>
        <span aria-hidden="true">↻</span> Refresh data
      </button>
    </header>
  );
}
