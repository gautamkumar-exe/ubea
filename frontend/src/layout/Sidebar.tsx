export type WorkspacePage = "overview" | "alerts" | "events" | "analytics";

interface SidebarProps {
  activePage: WorkspacePage;
  onNavigate: (page: WorkspacePage) => void;
  apiStatus: "connected" | "unavailable" | "checking";
}

const NAV_ITEMS: { id: WorkspacePage; label: string; icon: string }[] = [
  { id: "overview", label: "Overview", icon: "▦" },
  { id: "alerts", label: "Security alerts", icon: "◈" },
  { id: "events", label: "Event activity", icon: "⌁" },
  { id: "analytics", label: "Behavioral analytics", icon: "◎" },
];

export function Sidebar({ activePage, onNavigate, apiStatus }: SidebarProps) {
  return (
    <aside className="sidebar">
      <a className="brand" href="#overview" onClick={(event) => { event.preventDefault(); onNavigate("overview"); }} aria-label="UEBA Security Platform home">
        <span className="brand__mark" aria-hidden="true">U</span>
        <span className="brand__copy">
          <strong>UEBA</strong>
          <small>SECURITY PLATFORM</small>
        </span>
      </a>

      <nav className="sidebar__nav" aria-label="Workspace">
        <span className="sidebar__label">WORKSPACE</span>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`nav-item ${activePage === item.id ? "is-active" : ""}`}
            aria-current={activePage === item.id ? "page" : undefined}
            onClick={() => onNavigate(item.id)}
          >
            <span className="nav-item__icon" aria-hidden="true">{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar__footer">
        <span className={`status-dot status-dot--${apiStatus}`} aria-hidden="true" />
        <div className="sidebar__status-copy">
          <strong>Backend API</strong>
          <span>{apiStatus === "connected" ? "Connected" : apiStatus === "checking" ? "Checking connection" : "Unavailable"}</span>
        </div>
        <span className="sidebar__environment">DEV</span>
      </div>
    </aside>
  );
}
