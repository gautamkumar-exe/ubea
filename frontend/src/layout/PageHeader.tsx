import type { WorkspacePage } from "./Sidebar";

const PAGE_META: Record<WorkspacePage, { eyebrow: string; title: string; description: string }> = {
  overview: {
    eyebrow: "SECURITY OPERATIONS / OVERVIEW",
    title: "Threat monitoring",
    description: "Review behavioral anomalies and coordinate security alert triage.",
  },
  alerts: {
    eyebrow: "SECURITY OPERATIONS / ALERT MANAGEMENT",
    title: "Security Alerts",
    description: "Search, prioritize, investigate, and resolve detected activity.",
  },
  events: {
    eyebrow: "TELEMETRY / EVENT PIPELINE",
    title: "Events",
    description: "Ingest and inspect security events before running rule-based analysis.",
  },
  analytics: {
    eyebrow: "DETECTION / BEHAVIORAL ANALYTICS",
    title: "User Analytics",
    description: "Inspect observed user activity, saved behavioral baselines, and rule-based event analysis.",
  },
  ml: {
    eyebrow: "EXPERIMENTAL / OFFLINE MODEL ANALYTICS",
    title: "ML Analytics",
    description: "Run the synthetic Isolation Forest demonstration and inspect its experimental evaluation.",
  },
  "ai-assistant": {
    eyebrow: "INVESTIGATION / AI SOC ASSISTANT",
    title: "AI SOC Assistant",
    description: "Ask evidence-grounded questions about security alerts and events. All recommendations require analyst review.",
  },
};

interface PageHeaderProps {
  page: WorkspacePage;
  onRefresh: () => void;
  onOpenNavigation: () => void;
}

export function PageHeader({ page, onRefresh, onOpenNavigation }: PageHeaderProps) {
  const meta = PAGE_META[page];
  return (
    <header className="page-header">
      <button type="button" className="page-header__menu" onClick={onOpenNavigation} aria-label="Open navigation" aria-controls="main-navigation">
        <span aria-hidden="true">☰</span>
        <span>Menu</span>
      </button>
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
