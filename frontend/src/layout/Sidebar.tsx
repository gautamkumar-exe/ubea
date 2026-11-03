export type WorkspacePage = "overview" | "alerts" | "events" | "analytics" | "ml";

interface SidebarProps {
  activePage: WorkspacePage;
  onNavigate: (page: WorkspacePage) => void;
  apiStatus: "connected" | "unavailable" | "checking";
  collapsed: boolean;
  mobileOpen: boolean;
  onToggleCollapsed: () => void;
  onCloseMobile: () => void;
}

const NAV_ITEMS: { id: WorkspacePage; label: string; icon: string }[] = [
  { id: "overview", label: "Overview", icon: "▦" },
  { id: "alerts", label: "Security Alerts", icon: "◈" },
  { id: "analytics", label: "User Analytics", icon: "◎" },
  { id: "events", label: "Events", icon: "⌁" },
  { id: "ml", label: "ML Analytics", icon: "◌" },
];

const PLANNED_ITEMS = [
  { label: "AI SOC Assistant", icon: "✳" },
];

export function Sidebar({
  activePage,
  onNavigate,
  apiStatus,
  collapsed,
  mobileOpen,
  onToggleCollapsed,
  onCloseMobile,
}: SidebarProps) {
  function navigate(page: WorkspacePage) {
    onNavigate(page);
    onCloseMobile();
  }

  return (
    <aside id="main-navigation" className={`sidebar${collapsed ? " sidebar--collapsed" : ""}${mobileOpen ? " sidebar--mobile-open" : ""}`} aria-label="Main navigation">
      <div className="sidebar__top">
      <a className="brand" href="#overview" onClick={(event) => { event.preventDefault(); navigate("overview"); }} aria-label="UEBA Security Platform home">
        <span className="brand__mark" aria-hidden="true">U</span>
        <span className="brand__copy">
          <strong>UEBA</strong>
          <small>SECURITY PLATFORM</small>
        </span>
      </a>
      <button
        type="button"
        className="sidebar__collapse"
        onClick={onToggleCollapsed}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        aria-expanded={!collapsed}
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        <span aria-hidden="true">{collapsed ? "»" : "«"}</span>
      </button>
      </div>

      <nav className="sidebar__nav" aria-label="Workspace">
        <span className="sidebar__label">Workspace</span>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`nav-item ${activePage === item.id ? "is-active" : ""}`}
            aria-current={activePage === item.id ? "page" : undefined}
            onClick={() => navigate(item.id)}
            title={collapsed ? item.label : undefined}
          >
            <span className="nav-item__icon" aria-hidden="true">{item.icon}</span>
            <span className="nav-item__label">{item.label}</span>
          </button>
        ))}

        <div className="sidebar__planned" aria-label="Planned capabilities">
          <span className="sidebar__label">Planned</span>
          {PLANNED_ITEMS.map((item) => (
            <button
              key={item.label}
              type="button"
              className="nav-item nav-item--planned"
              disabled
              aria-label={`${item.label}, Planned / Not connected`}
              title={`${item.label} — Planned / Not connected`}
            >
              <span className="nav-item__icon" aria-hidden="true">{item.icon}</span>
              <span className="nav-item__planned-copy">
                <span className="nav-item__label">{item.label}</span>
                <small>Planned / Not connected</small>
              </span>
            </button>
          ))}
        </div>
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
