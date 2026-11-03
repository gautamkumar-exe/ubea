import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  getAssistantStatus,
  sendAssistantMessage,
  type AssistantChatResponse,
  type AssistantContextType,
  type AssistantHistoryMessage,
  type AssistantMode,
  type AssistantStatus,
} from "../../api";
import { errorMessage } from "../../lib/format";

export interface AssistantContextSelection {
  type: AssistantContextType;
  id: string;
}

interface AISocAssistantFeatureProps {
  initialContext: AssistantContextSelection | null;
}

interface ChatMessage extends AssistantHistoryMessage { id: number; createdAt: number; }

const SUGGESTIONS: Array<{ label: string; prompt: string; mode: AssistantMode }> = [
  { label: "Explain selected alert", prompt: "Explain the selected security alert using only the supplied evidence. Separate observations from inferences and suggest next checks.", mode: "explain_alert" },
  { label: "Summarize this incident", prompt: "Summarize the selected incident context, including the related activity and evidence gaps.", mode: "incident_summary" },
  { label: "Identify suspicious behavior", prompt: "Identify behavior that appears unusual in the supplied context, and explain what evidence supports that assessment.", mode: "general" },
  { label: "Recommend next steps", prompt: "Recommend prioritized, non-destructive investigation steps based on the available evidence.", mode: "general" },
  { label: "Why may this be anomalous?", prompt: "Explain why this activity may be anomalous, distinguishing observed facts from possible explanations.", mode: "general" },
];

export function AISocAssistantFeature({ initialContext }: AISocAssistantFeatureProps) {
  const [status, setStatus] = useState<AssistantStatus | null>(null);
  const [statusError, setStatusError] = useState("");
  const [context, setContext] = useState<AssistantContextSelection | null>(initialContext);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [lastResponse, setLastResponse] = useState<AssistantChatResponse | null>(null);
  const [mode, setMode] = useState<AssistantMode>(initialContext?.type === "alert" ? "explain_alert" : "general");
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const scrollArea = useRef<HTMLDivElement>(null);
  const nextId = useRef(1);

  useEffect(() => {
    const controller = new AbortController();
    getAssistantStatus(controller.signal)
      .then(setStatus)
      .catch((reason: unknown) => setStatusError(errorMessage(reason, "Unable to check AI assistant availability.")));
    return () => controller.abort();
  }, []);

  useEffect(() => {
    scrollArea.current?.scrollTo({ top: scrollArea.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  async function submit(message: string, nextMode: AssistantMode = mode, retry = false) {
    const content = message.trim();
    if (!content || loading || !status?.configured) return;
    setError("");
    setDraft("");
    setMode(nextMode);
    const userMessage: ChatMessage = { id: nextId.current++, role: "user", content, createdAt: Date.now() };
    const previous = retry ? messages.slice(0, -1) : messages;
    if (!retry) setMessages((current) => [...current, userMessage]);
    setLoading(true);
    try {
      const history = previous.slice(-12).map(({ role, content: text }) => ({ role, content: text }));
      const response = await sendAssistantMessage({
        message: content,
        mode: nextMode,
        history,
        ...(context?.type === "alert" ? { alert_id: context.id } : {}),
        ...(context?.type === "event" ? { event_id: context.id } : {}),
      });
      setLastResponse(response);
      setMessages((current) => [...current, {
        id: nextId.current++, role: "assistant", content: response.response, createdAt: Date.now(),
      }]);
    } catch (reason) {
      setError(errorMessage(reason, "Unable to get a response from the AI assistant."));
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submit(draft);
  }

  function clearConversation() {
    setMessages([]);
    setLastResponse(null);
    setError("");
    nextId.current = 1;
  }

  return (
    <div className="page-stack ai-assistant-layout">
      <section className="surface-card ai-assistant-chat">
        <header className="surface-card__header ai-assistant-header">
          <div><div className="eyebrow">ADVISORY INVESTIGATION</div><h2>UEBA AI SOC Assistant</h2><p>Interpretation is AI-generated; referenced records below are backend evidence.</p></div>
          <div className="ai-assistant-header__actions">
            <span className={`assistant-status ${status?.configured ? "assistant-status--ready" : "assistant-status--offline"}`}><i />{status === null ? "Checking provider" : status.configured ? `Ready · ${status.model}` : "Not configured"}</span>
            <button type="button" className="button button--secondary" onClick={clearConversation} disabled={loading || (!messages.length && !error)}>Clear conversation</button>
          </div>
        </header>

        {statusError && <div className="inline-message inline-message--error ai-assistant-status-error" role="alert"><span>{statusError}</span><button type="button" className="text-button" onClick={() => { setStatusError(""); getAssistantStatus().then(setStatus).catch((reason: unknown) => setStatusError(errorMessage(reason, "Unable to check assistant status."))); }}>Retry</button></div>}
        {status && !status.configured && <div className="inline-message inline-message--info ai-assistant-status-error" role="status">AI assistance is unavailable until the backend is configured with <code>OPENAI_API_KEY</code>. The rest of the UEBA platform continues to work.</div>}
        <div className="ai-assistant-messages" ref={scrollArea} aria-live="polite" aria-label="Conversation">
          {messages.length === 0 ? <div className="ai-assistant-welcome">
            <span className="ai-assistant-welcome__icon" aria-hidden="true">✳</span>
            <h3>Investigate with evidence in view</h3>
            <p>Ask a general security question, or select an alert or event to ground the investigation in available UEBA records.</p>
            <div className="ai-assistant-suggestions">{SUGGESTIONS.map((item) => <button key={item.label} type="button" className="assistant-prompt-chip" disabled={!status?.configured || loading} onClick={() => void submit(item.prompt, item.mode)}>{item.label}<span aria-hidden="true">↗</span></button>)}</div>
          </div> : <div className="ai-assistant-message-list">
            {messages.map((message) => <article key={message.id} className={`assistant-message assistant-message--${message.role}`}>
              <div className="assistant-message__label">{message.role === "assistant" ? "AI SOC ASSISTANT · AI INTERPRETATION" : "ANALYST"}</div>
              <div className="assistant-message__content">{message.content}</div>
            </article>)}
          </div>}
          {loading && <div className="assistant-loading" role="status"><span className="assistant-loading__pulse" /> Reviewing the supplied context…</div>}
        </div>
      {error && <div className="inline-message inline-message--error ai-assistant-error" role="alert"><span>{error}</span><button type="button" className="text-button" onClick={() => { const lastMessage = messages[messages.length - 1]; if (lastMessage?.role === "user") void submit(lastMessage.content, mode, true); }}>Retry</button></div>}
        <div className="ai-assistant-composer-wrap">
          <div className="ai-assistant-mode-row" aria-label="Assistant mode">
            <button type="button" className={mode === "general" ? "is-selected" : ""} onClick={() => setMode("general")}>General</button>
            <button type="button" className={mode === "explain_alert" ? "is-selected" : ""} disabled={context?.type !== "alert"} onClick={() => setMode("explain_alert")}>Explain alert</button>
            <button type="button" className={mode === "incident_summary" ? "is-selected" : ""} disabled={!context} onClick={() => setMode("incident_summary")}>Incident summary</button>
          </div>
          <form className="ai-assistant-composer" onSubmit={handleSubmit}>
            <label className="sr-only" htmlFor="assistant-message">Message the AI SOC Assistant</label>
            <textarea id="assistant-message" rows={2} maxLength={4000} value={draft} disabled={!status?.configured || loading} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); void submit(draft); } }} placeholder={status?.configured ? "Ask about security activity… (Enter to send, Shift+Enter for a new line)" : "Configure the backend provider to start a conversation."} />
            <button type="submit" className="button button--primary" disabled={!draft.trim() || loading || !status?.configured}>{loading ? "Reviewing…" : "Send"}</button>
          </form>
          <p className="ai-assistant-disclaimer">Advisory only. Verify recommendations against source evidence. No alerts, events, or baselines are changed.</p>
        </div>
      </section>

      <aside className="surface-card ai-assistant-context">
        <header className="surface-card__header"><div><div className="eyebrow">INVESTIGATION CONTEXT</div><h2>Selected evidence</h2><p>Context is retrieved from the backend when you send a message.</p></div></header>
        <div className="ai-assistant-context__body">
          <div className="assistant-context-record"><span className="detail-field__label">Selected record</span><strong>{context?.type === "alert" ? "Security alert" : context?.type === "event" ? "Security event" : "General question"}</strong><code>{context?.id ?? "No record selected"}</code></div>
          {context && <button className="text-button" type="button" onClick={() => { setContext(null); setLastResponse(null); setMode("general"); }}>Clear selected context</button>}
          {lastResponse && <>
            <div className="assistant-context-divider" />
            <div className="detail-field__label">Last request context</div>
            {!lastResponse.security_context_available && <p className="empty-note">No security context was available. The response is a general assistant answer.</p>}
            {lastResponse.context_types_used.length > 0 && <div className="assistant-context-tags">{lastResponse.context_types_used.map((item) => <span className="badge" key={item}>{item.replaceAll("_", " ")}</span>)}</div>}
            {lastResponse.context_references.length === 0 ? <p className="empty-note">No records referenced.</p> : <ul className="assistant-reference-list">{lastResponse.context_references.map((ref, index) => <li key={`${ref.type}-${ref.id}-${index}`}><span>{ref.type.replaceAll("_", " ")}</span><code>{ref.id}</code><small className={ref.status === "available" ? "" : "is-missing"}>{ref.status}</small></li>)}</ul>}
          </>}
          <div className="assistant-safety-note"><strong>Evidence and interpretation are separate.</strong><p>Backend records appear as referenced evidence. Assistant responses are generated interpretations and may be incomplete.</p></div>
        </div>
      </aside>
    </div>
  );
}
