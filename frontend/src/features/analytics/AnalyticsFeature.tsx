import { useEffect, useState } from "react";
import { analyzeEvent, getBaseline, rebuildBaseline, type AnomalyAnalysis, type BaselineResponse } from "../../api";
import { errorMessage } from "../../lib/format";
import { StatusBadge } from "../../components/StatusBadge";

interface AnalyticsFeatureProps {
  initialEventId: string;
  onAnalysisComplete: () => void;
}

export function AnalyticsFeature({ initialEventId, onAnalysisComplete }: AnalyticsFeatureProps) {
  const [userId, setUserId] = useState("");
  const [baseline, setBaseline] = useState<BaselineResponse | null>(null);
  const [baselineBusy, setBaselineBusy] = useState(false);
  const [baselineMessage, setBaselineMessage] = useState("");
  const [baselineError, setBaselineError] = useState("");
  const [eventId, setEventId] = useState(initialEventId);
  const [analysis, setAnalysis] = useState<AnomalyAnalysis | null>(null);
  const [analysisBusy, setAnalysisBusy] = useState(false);
  const [analysisMessage, setAnalysisMessage] = useState("");
  const [analysisError, setAnalysisError] = useState("");

  useEffect(() => {
    if (initialEventId) setEventId(initialEventId);
  }, [initialEventId]);

  async function handleBaseline(rebuild: boolean) {
    const normalizedUserId = userId.trim();
    if (!normalizedUserId) {
      setBaselineError("Enter a user ID first.");
      setBaselineMessage("");
      return;
    }
    setBaselineBusy(true);
    setBaselineError("");
    setBaselineMessage("");
    try {
      const result = rebuild ? await rebuildBaseline(normalizedUserId) : await getBaseline(normalizedUserId);
      setBaseline(result);
      setBaselineMessage(rebuild ? "Baseline rebuilt successfully." : "Baseline loaded successfully.");
    } catch (error) {
      setBaseline(null);
      setBaselineError(errorMessage(error, "Unable to retrieve the user baseline."));
    } finally {
      setBaselineBusy(false);
    }
  }

  async function handleAnalyze() {
    const normalizedEventId = eventId.trim();
    if (!normalizedEventId) {
      setAnalysisError("Enter an event UUID, or choose Analyze from Event activity.");
      setAnalysisMessage("");
      return;
    }
    setAnalysisBusy(true);
    setAnalysisError("");
    setAnalysisMessage("");
    try {
      const result = await analyzeEvent(normalizedEventId);
      setAnalysis(result);
      setAnalysisMessage(result.alert_id ? `Analysis completed. Alert created or updated: ${result.alert_id}` : "Analysis completed. The event did not meet the alert-generation threshold.");
      onAnalysisComplete();
    } catch (error) {
      setAnalysis(null);
      setAnalysisError(errorMessage(error, "Unable to analyze the selected event."));
    } finally {
      setAnalysisBusy(false);
    }
  }

  return (
    <div className="page-stack analytics-layout">
      <section className="surface-card">
        <header className="surface-card__header">
          <div><div className="eyebrow">USER BEHAVIOR</div><h2>Baseline management</h2><p>Build a baseline from the stored history for one user.</p></div>
        </header>
        <div className="action-form-row">
          <label className="field action-form-row__input"><span>User ID</span><input value={userId} onChange={(event) => setUserId(event.target.value)} placeholder="e.g. user-001" /></label>
          <div className="action-form-row__buttons"><button type="button" className="button button--secondary" disabled={baselineBusy} onClick={() => void handleBaseline(false)}>Load baseline</button><button type="button" className="button button--primary" disabled={baselineBusy} onClick={() => void handleBaseline(true)}>{baselineBusy ? "Rebuilding…" : "Rebuild baseline"}</button></div>
        </div>
        {baselineError && <div className="inline-message inline-message--error" role="alert">{baselineError}</div>}
        {baselineMessage && <div className="inline-message inline-message--success" role="status">{baselineMessage}</div>}
        {baseline && <div className="result-panel"><div className="result-panel__header"><div><span className="eyebrow">USER PROFILE</span><h3>{baseline.user_id}</h3></div><StatusBadge value={baseline.status} kind="generic" /></div><pre className="code-output">{JSON.stringify(baseline.baseline, null, 2)}</pre></div>}
      </section>

      <section className="surface-card">
        <header className="surface-card__header">
          <div><div className="eyebrow">RULE-BASED DETECTION</div><h2>Analyze a stored event</h2><p>Analysis evaluates an existing event and may create or update a security alert.</p></div>
        </header>
        <div className="action-form-row">
          <label className="field action-form-row__input"><span>Event UUID</span><input value={eventId} onChange={(event) => setEventId(event.target.value)} placeholder="Paste an event UUID" spellCheck={false} /></label>
          <div className="action-form-row__buttons"><button type="button" className="button button--primary" onClick={() => void handleAnalyze()} disabled={analysisBusy}>{analysisBusy ? "Analyzing event…" : "Analyze event"}</button></div>
        </div>
        {analysisError && <div className="inline-message inline-message--error" role="alert">{analysisError}</div>}
        {analysisMessage && <div className={`inline-message ${analysis?.alert_id ? "inline-message--success" : "inline-message--info"}`} role="status">{analysisMessage}</div>}
        {analysis && <div className="result-panel">
          <div className="analysis-summary">
            <div><span className="result-label">Risk score</span><strong className="analysis-summary__score">{analysis.risk_score}<small>/100</small></strong></div>
            <div><span className="result-label">Severity</span><StatusBadge value={analysis.severity} kind="severity" /></div>
            <div><span className="result-label">Classification</span><strong>{analysis.is_anomalous ? "Anomalous" : "Not anomalous"}</strong></div>
            <div><span className="result-label">Baseline events</span><strong>{analysis.baseline_event_count.toLocaleString()}</strong></div>
          </div>
          {analysis.note && <p className="result-note">{analysis.note}</p>}
          {analysis.reasons.length > 0 && <div className="reason-list"><h3>Reasons</h3>{analysis.reasons.map((reason, index) => <div className="reason-item" key={`${String(reason.code ?? reason.reason ?? "reason")}-${index}`}>{String(reason.reason ?? reason.message ?? reason.code ?? JSON.stringify(reason))}</div>)}</div>}
          <details className="raw-result"><summary>Raw analysis response</summary><pre className="code-output">{JSON.stringify(analysis, null, 2)}</pre></details>
        </div>}
      </section>
    </div>
  );
}
