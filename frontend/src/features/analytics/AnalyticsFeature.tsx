import { useEffect, useState } from "react";
import { analyzeEvent, type AnomalyAnalysis } from "../../api";
import { errorMessage } from "../../lib/format";
import { StatusBadge } from "../../components/StatusBadge";

interface AnalyticsFeatureProps {
  initialEventId: string;
  onAnalysisComplete: () => void;
}

export function AnalyticsFeature({ initialEventId, onAnalysisComplete }: AnalyticsFeatureProps) {
  const [eventId, setEventId] = useState(initialEventId);
  const [analysis, setAnalysis] = useState<AnomalyAnalysis | null>(null);
  const [analysisBusy, setAnalysisBusy] = useState(false);
  const [analysisMessage, setAnalysisMessage] = useState("");
  const [analysisError, setAnalysisError] = useState("");

  useEffect(() => {
    if (initialEventId) setEventId(initialEventId);
  }, [initialEventId]);

  async function handleAnalyze() {
    const normalizedEventId = eventId.trim();
    if (!normalizedEventId) {
      setAnalysisError("Enter an event UUID, or choose Analyze from event activity.");
      setAnalysisMessage("");
      return;
    }
    setAnalysisBusy(true);
    setAnalysisError("");
    setAnalysisMessage("");
    try {
      const result = await analyzeEvent(normalizedEventId);
      setAnalysis(result);
      setAnalysisMessage(result.alert_id
        ? `Analysis completed. Alert created or updated: ${result.alert_id}`
        : "Analysis completed. The event did not meet the alert-generation threshold.");
      onAnalysisComplete();
    } catch (error) {
      setAnalysis(null);
      setAnalysisError(errorMessage(error, "Unable to analyze the selected event."));
    } finally {
      setAnalysisBusy(false);
    }
  }

  return (
    <section className="surface-card analytics-analysis-section">
      <header className="surface-card__header">
        <div><div className="eyebrow">RULE-BASED DETECTION</div><h2>Analyze a stored event</h2><p>Analysis evaluates an existing event against its user baseline and may create or update an alert.</p></div>
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
        {analysis.reasons.length > 0 && <div className="reason-list"><h3>Reasons returned by the analysis API</h3>{analysis.reasons.map((reason, index) => <div className="reason-item" key={`${String(reason.code ?? reason.reason ?? reason.factor ?? "reason")}-${index}`}>{String(reason.reason ?? reason.message ?? reason.details ?? reason.code ?? JSON.stringify(reason))}</div>)}</div>}
        <details className="raw-result"><summary>Raw analysis response</summary><pre className="code-output">{JSON.stringify(analysis, null, 2)}</pre></details>
      </div>}
    </section>
  );
}
