import { useEffect, useState, type FormEvent } from "react";
import {
  getAlertFeedback,
  submitAlertFeedback,
  type Alert,
  type AlertStatus,
  type AnalystFeedback,
  type FeedbackVerdict,
} from "../../api";
import { errorMessage, formatDate, humanize } from "../../lib/format";
import { StatusBadge } from "../../components/StatusBadge";

const STATUSES: AlertStatus[] = ["open", "investigating", "resolved", "dismissed"];
const VERDICTS: { value: FeedbackVerdict; label: string }[] = [
  { value: "true_positive", label: "True positive" },
  { value: "false_positive", label: "False positive" },
  { value: "benign", label: "Benign activity" },
  { value: "inconclusive", label: "Inconclusive" },
];

interface AlertDetailsDialogProps {
  alert: Alert;
  onClose: () => void;
  onStatusChange: (alert: Alert, status: AlertStatus) => Promise<void>;
  onAskAi?: (alertId: string) => void;
}

export function AlertDetailsDialog({ alert, onClose, onStatusChange, onAskAi }: AlertDetailsDialogProps) {
  const [feedback, setFeedback] = useState<AnalystFeedback[]>([]);
  const [feedbackTotal, setFeedbackTotal] = useState(0);
  const [feedbackLoading, setFeedbackLoading] = useState(true);
  const [feedbackLoadError, setFeedbackLoadError] = useState("");
  const [feedbackSubmitError, setFeedbackSubmitError] = useState("");
  const [feedbackMessage, setFeedbackMessage] = useState("");
  const [feedbackReloadAttempt, setFeedbackReloadAttempt] = useState(0);
  const [analystId, setAnalystId] = useState("");
  const [verdict, setVerdict] = useState<FeedbackVerdict>("true_positive");
  const [comment, setComment] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [statusBusy, setStatusBusy] = useState(false);
  const [statusError, setStatusError] = useState("");

  useEffect(() => {
    const controller = new AbortController();
    setFeedbackLoading(true);
    setFeedbackLoadError("");
    setFeedbackMessage("");
    setFeedback([]);
    setFeedbackTotal(0);
    getAlertFeedback(alert.id, controller.signal)
      .then((response) => {
        if (controller.signal.aborted) return;
        setFeedback(response.items);
        setFeedbackTotal(response.total);
      })
      .catch((error: unknown) => {
        if (!controller.signal.aborted) setFeedbackLoadError(errorMessage(error, "Unable to load feedback history."));
      })
      .finally(() => { if (!controller.signal.aborted) setFeedbackLoading(false); });
    return () => controller.abort();
  }, [alert.id, feedbackReloadAttempt]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  async function submitFeedback(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const analyst = analystId.trim();
    if (!analyst) {
      setFeedbackSubmitError("Enter an analyst ID before submitting feedback.");
      return;
    }

    setSubmitting(true);
    setFeedbackSubmitError("");
    setFeedbackMessage("");
    try {
      const saved = await submitAlertFeedback(alert.id, {
        analyst_id: analyst,
        verdict,
        comment: comment.trim() || null,
      });
      setFeedback((items) => [saved, ...items]);
      setFeedbackTotal((total) => total + 1);
      setComment("");
      setFeedbackMessage("Feedback saved.");
    } catch (error) {
      setFeedbackSubmitError(errorMessage(error, "Unable to save analyst feedback."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleStatusChange(nextStatus: AlertStatus) {
    setStatusBusy(true);
    setStatusError("");
    try {
      await onStatusChange(alert, nextStatus);
    } catch (error) {
      setStatusError(errorMessage(error, "Unable to update alert status."));
    } finally {
      setStatusBusy(false);
    }
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="detail-dialog" role="dialog" aria-modal="true" aria-labelledby="alert-detail-title">
        <header className="detail-dialog__header">
          <div>
            <div className="eyebrow">ALERT INVESTIGATION</div>
            <h2 id="alert-detail-title">Alert details</h2>
            <p className="detail-dialog__id">ID: <code>{alert.id}</code></p>
          </div>
          <button type="button" className="icon-button" aria-label="Close alert details" onClick={onClose}>×</button>
        </header>

        <div className="detail-dialog__body">
          <section className="detail-summary">
            <h3>{alert.title}</h3>
            <div className="detail-summary__badges">
              <StatusBadge value={alert.severity} kind="severity" />
              <StatusBadge value={humanize(alert.status)} kind="status" />
              <span className="risk-score">Risk score <strong>{alert.risk_score}/100</strong></span>
            </div>
          </section>

          <div className="detail-grid">
            <div className="detail-field detail-field--wide"><span className="detail-field__label">Explanation</span><p>{alert.explanation || "No explanation was provided."}</p></div>
            <div className="detail-field"><span className="detail-field__label">User</span><p>{alert.user_id ?? "Not specified"}</p></div>
            <div className="detail-field"><span className="detail-field__label">Created</span><p>{formatDate(alert.created_at)}</p></div>
            <div className="detail-field detail-field--wide"><span className="detail-field__label">Linked event ID</span><p className="mono detail-event-id">{alert.event_id ?? "No linked event ID was returned for this alert."}</p></div>
            <div className="detail-field detail-field--wide">
              <span className="detail-field__label">Detection evidence · returned by backend</span>
              <pre className="code-output">{JSON.stringify(alert.evidence ?? {}, null, 2)}</pre>
            </div>
          </div>

          {onAskAi && <div className="event-detail-actions"><button type="button" className="button button--primary" onClick={() => onAskAi(alert.id)}>Ask AI SOC Assistant about this alert</button></div>}

          <section className="detail-section">
            <div className="detail-section__heading"><div><div className="eyebrow">CASE MANAGEMENT</div><h3>Investigation status</h3></div></div>
            <label className="field"><span>Status</span>
              <select value={alert.status} disabled={statusBusy} onChange={(event) => void handleStatusChange(event.target.value as AlertStatus)}>
                {STATUSES.map((status) => <option key={status} value={status}>{humanize(status)}</option>)}
              </select>
            </label>
            {statusBusy && <p className="muted-copy" role="status">Updating alert status…</p>}
            {statusError && <div className="inline-message inline-message--error detail-inline-message" role="alert">{statusError}</div>}
          </section>

          <section className="detail-section">
            <div className="detail-section__heading"><div><div className="eyebrow">ANALYST WORKFLOW</div><h3>Investigation feedback</h3><p>Record the assessment and evidence for this alert.</p></div></div>
            <form className="stack-form" onSubmit={submitFeedback}>
              <label className="field"><span>Analyst ID</span><input value={analystId} onChange={(event) => setAnalystId(event.target.value)} placeholder="e.g. analyst-001" maxLength={255} required /></label>
              <label className="field"><span>Verdict</span><select value={verdict} onChange={(event) => setVerdict(event.target.value as FeedbackVerdict)}>{VERDICTS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
              <label className="field"><span>Comment <small>(optional)</small></span><textarea rows={3} value={comment} onChange={(event) => setComment(event.target.value)} maxLength={5000} placeholder="Summarize the evidence behind this verdict." /></label>
              {feedbackSubmitError && <div className="inline-message inline-message--error" role="alert">{feedbackSubmitError}</div>}
              {feedbackMessage && <div className="inline-message inline-message--success" role="status">{feedbackMessage}</div>}
              <div><button className="button button--primary" type="submit" disabled={submitting}>{submitting ? "Saving feedback…" : "Submit feedback"}</button></div>
            </form>
          </section>

          <section className="detail-section">
            <div className="detail-section__heading"><div><div className="eyebrow">AUDIT TRAIL</div><h3>Previous feedback <span className="count-chip">{feedbackTotal}</span></h3></div></div>
            {feedbackLoading ? <p className="muted-copy" role="status">Loading feedback history…</p> : feedbackLoadError ? <div className="inline-message inline-message--error detail-inline-message" role="alert"><span>{feedbackLoadError}</span><button type="button" className="text-button" onClick={() => setFeedbackReloadAttempt((attempt) => attempt + 1)}>Retry</button></div> : feedback.length === 0 ? <p className="empty-note">No feedback has been recorded for this alert.</p> : (
              <div className="feedback-list">
                {feedback.map((item) => <article className="feedback-item" key={item.id}>
                  <div className="feedback-item__top"><strong>{humanize(item.verdict)}</strong><time>{formatDate(item.created_at)}</time></div>
                  <p>Analyst: {item.analyst_id}</p>
                  {item.comment && <p className="feedback-item__comment">{item.comment}</p>}
                </article>)}
              </div>
            )}
          </section>
        </div>
      </section>
    </div>
  );
}
