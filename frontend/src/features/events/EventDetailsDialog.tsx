import { useEffect } from "react";
import type { SecurityEvent } from "../../api";
import { formatDate } from "../../lib/format";

interface EventDetailsDialogProps {
  event: SecurityEvent;
  onClose: () => void;
  onAnalyze: () => void;
}

export function EventDetailsDialog({ event, onClose, onAnalyze }: EventDetailsDialogProps) {
  useEffect(() => {
    const handleKeyDown = (keyboardEvent: KeyboardEvent) => {
      if (keyboardEvent.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(mouseEvent) => { if (mouseEvent.target === mouseEvent.currentTarget) onClose(); }}>
      <section className="detail-dialog event-detail-dialog" role="dialog" aria-modal="true" aria-labelledby="event-detail-title">
        <header className="detail-dialog__header">
          <div>
            <div className="eyebrow">EVENT INVESTIGATION</div>
            <h2 id="event-detail-title">Event details</h2>
            <p className="detail-dialog__id">Event ID: <code>{event.id}</code></p>
          </div>
          <button type="button" className="icon-button" aria-label="Close event details" onClick={onClose}>×</button>
        </header>

        <div className="detail-dialog__body">
          <section className="detail-summary">
            <h3>{event.event_type}</h3>
            <div className="detail-summary__badges">
              <span className="badge">Source: {event.source}</span>
              <span className="badge">Event time: <time dateTime={event.event_time}>{formatDate(event.event_time)}</time></span>
            </div>
          </section>

          <div className="detail-grid">
            <div className="detail-field detail-field--wide"><span className="detail-field__label">Event ID</span><p className="detail-event-id">{event.id}</p></div>
            <div className="detail-field"><span className="detail-field__label">External event ID</span><p className="mono">{event.external_id}</p></div>
            <div className="detail-field"><span className="detail-field__label">Event type</span><p>{event.event_type}</p></div>
            <div className="detail-field"><span className="detail-field__label">User ID</span><p className="mono">{event.user_id ?? "Not provided"}</p></div>
            <div className="detail-field"><span className="detail-field__label">Entity ID</span><p className="mono">{event.entity_id ?? "Not provided"}</p></div>
            <div className="detail-field"><span className="detail-field__label">Source IP</span><p className="mono">{event.source_ip ?? "Not provided"}</p></div>
            <div className="detail-field"><span className="detail-field__label">Source</span><p>{event.source}</p></div>
            <div className="detail-field"><span className="detail-field__label">Event time</span><p><time dateTime={event.event_time}>{formatDate(event.event_time)}</time></p></div>
          </div>

          <section className="detail-section event-metadata">
            <div className="detail-section__heading">
              <div className="eyebrow">SOURCE METADATA</div>
              <h3>Raw event payload</h3>
              <p className="detail-field__label">Metadata supplied by the event source. Expand to inspect.</p>
            </div>
            <details className="raw-result event-raw-metadata">
              <summary>View raw event metadata</summary>
              <pre className="code-output">{JSON.stringify(event.raw_event ?? {}, null, 2)}</pre>
            </details>
          </section>

          <div className="event-detail-actions">
            <button type="button" className="button button--primary" onClick={onAnalyze}>Analyze this event</button>
          </div>
        </div>
      </section>
    </div>
  );
}
