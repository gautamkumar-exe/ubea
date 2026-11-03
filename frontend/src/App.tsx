import { useCallback, useEffect, useState } from "react";
import { getHealth } from "./api";
import { Sidebar, type WorkspacePage } from "./layout/Sidebar";
import { PageHeader } from "./layout/PageHeader";
import { OverviewFeature } from "./features/overview/OverviewFeature";
import { AlertsFeature } from "./features/alerts/AlertsFeature";
import { EventsFeature } from "./features/events/EventsFeature";
import { UserAnalyticsFeature } from "./features/analytics/UserAnalyticsFeature";
import { errorMessage } from "./lib/format";
import "./App.css";

 type ApiStatus = "connected" | "unavailable" | "checking";

function App() {
  const [activePage, setActivePage] = useState<WorkspacePage>("overview");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");
  const [healthError, setHealthError] = useState("");
  const [refreshToken, setRefreshToken] = useState(0);
  const [initialEventId, setInitialEventId] = useState("");

  const checkHealth = useCallback(async () => {
    try {
      const result = await getHealth();
      setApiStatus(result.status === "ok" ? "connected" : "unavailable");
      setHealthError("");
    } catch (error) {
      setApiStatus("unavailable");
      setHealthError(errorMessage(error, "Unable to reach the backend API."));
    }
  }, []);

  useEffect(() => {
    void checkHealth();
    const timer = window.setInterval(() => void checkHealth(), 15_000);
    return () => window.clearInterval(timer);
  }, [checkHealth, refreshToken]);

  useEffect(() => {
    if (!mobileSidebarOpen) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setMobileSidebarOpen(false);
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [mobileSidebarOpen]);

  function refreshWorkspace() {
    setRefreshToken((current) => current + 1);
  }

  function navigateToAnalysis(eventId: string) {
    setInitialEventId(eventId);
    setActivePage("analytics");
  }

  return (
    <div className={`app-shell${sidebarCollapsed ? " app-shell--sidebar-collapsed" : ""}`}>
      <Sidebar
        activePage={activePage}
        onNavigate={setActivePage}
        apiStatus={apiStatus}
        collapsed={sidebarCollapsed}
        mobileOpen={mobileSidebarOpen}
        onToggleCollapsed={() => setSidebarCollapsed((current) => !current)}
        onCloseMobile={() => setMobileSidebarOpen(false)}
      />
      {mobileSidebarOpen && <button type="button" className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setMobileSidebarOpen(false)} />}
      <main className="main-panel">
        <PageHeader page={activePage} onRefresh={refreshWorkspace} onOpenNavigation={() => setMobileSidebarOpen(true)} />
        {healthError && <div className="inline-message inline-message--error app-health-message" role="alert"><span><strong>Backend health check failed.</strong> {healthError}</span><button type="button" className="text-button" onClick={() => void checkHealth()}>Retry</button></div>}

        {activePage === "overview" && <OverviewFeature refreshToken={refreshToken} onDataChanged={refreshWorkspace} onNavigateToAlerts={() => setActivePage("alerts")} onNavigateToEvents={() => setActivePage("events")} />}
        {activePage === "alerts" && <AlertsFeature mode="alerts" refreshToken={refreshToken} />}
        {activePage === "events" && <EventsFeature refreshToken={refreshToken} onAnalyzeEvent={navigateToAnalysis} />}
        {activePage === "analytics" && <UserAnalyticsFeature initialEventId={initialEventId} onAnalysisComplete={refreshWorkspace} />}

        <footer className="app-footer"><span>UEBA SECURITY PLATFORM</span><span className="footer-separator">/</span><span>RULE-BASED DETECTION</span><span className="footer-separator">/</span><span>Refresh interval: 15 seconds</span></footer>
      </main>
    </div>
  );
}

export default App;
