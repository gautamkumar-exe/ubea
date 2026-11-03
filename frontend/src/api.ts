
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001";

export type AlertStatus =
  | "open"
  | "investigating"
  | "resolved"
  | "dismissed";

export type AlertSeverity = "critical" | "high" | "medium" | "low";

export interface AlertListFilters {
  status?: AlertStatus;
  severity?: AlertSeverity;
  user_id?: string;
}

export type FeedbackVerdict =
  | "true_positive"
  | "false_positive"
  | "benign"
  | "inconclusive";

export interface Alert {
  id: string;
  event_id: string | null;
  user_id: string | null;
  title: string;
  severity: "critical" | "high" | "medium" | "low" | string;
  risk_score: number;
  status: AlertStatus;
  explanation: string;
  evidence: Record<string, unknown>;
  created_at: string;
}

export interface AlertListResponse {
  items: Alert[];
  total: number;
  limit: number;
  offset: number;
}

export interface SecurityEvent {
  id: string;
  source: string;
  external_id: string;
  event_type: string;
  user_id: string | null;
  entity_id: string | null;
  source_ip: string | null;
  event_time: string;
  raw_event: Record<string, unknown>;
}

export interface SecurityEventListResponse {
  items: SecurityEvent[];
  total: number;
  limit: number;
  offset: number;
}

export interface SecurityEventCreate {
  source: string;
  external_id: string;
  event_type: string;
  user_id: string | null;
  entity_id: string | null;
  source_ip: string | null;
  event_time: string;
  raw_event: Record<string, unknown>;
}

export interface BaselineResponse {
  user_id: string;
  baseline: Record<string, unknown>;
  status: string;
}

export interface AnomalyAnalysis {
  event_id: string;
  user_id: string;
  risk_score: number;
  severity: string;
  is_anomalous: boolean;
  reasons: Array<Record<string, unknown>>;
  baseline_event_count: number;
  note: string;
  alert_id: string | null;
}

interface HealthResponse {
  status: string;
  service?: string;
  environment?: string;
}

export interface AnalystFeedback {
  id: string;
  alert_id: string;
  analyst_id: string;
  verdict: FeedbackVerdict;
  comment: string | null;
  created_at: string;
}

export interface FeedbackListResponse {
  items: AnalystFeedback[];
  total: number;
}

export interface MLAnalyticsDemo {
  demonstration_type: string;
  feature_specification_version: string;
  fixture_sha256: string;
  model: {
    name: string;
    implementation: string;
    feature_specification_version: string;
    features: string[];
    configuration: {
      contamination: number;
      random_state: number;
      n_estimators: number;
    };
    training: {
      records: number;
      partition: string;
      scenario_labels_used_for_fit: false;
    };
    decision_rule: {
      score_name: string;
      operator: string;
      threshold: number;
      note: string;
    };
  };
  training: Record<string, unknown>;
  features: string[];
  threshold: string;
  results: Array<{
    scenario: string;
    input_event: {
      user_id: string;
      event_time_utc: string;
      event_type: string;
      source_ip: string;
    };
    features: Record<string, number>;
    decision_score: number;
    prediction: "ANOMALY" | "NOT FLAGGED";
    threshold_rule: string;
    context: string;
    interpretation: string;
  }>;
  benchmark_evaluation: {
    dataset_kind: string;
    evaluation_status: string;
    label_source: string;
    fixture_sha256: string;
    feature_specification_version: string;
    evaluation_split: string;
    test_records: number;
    threshold: string;
    metrics: {
      precision: number;
      recall: number;
      f1: number;
      false_positive_rate: number | null;
      confusion_matrix: { labels: string[]; values: number[][] };
    };
    scenario_results: Record<string, {
      support: number;
      predicted_anomalies: number;
      predicted_anomaly_rate: number | null;
    }>;
    warning: string;
  };
  warning: string;
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(
      `API request failed (${response.status}): ${message || response.statusText}`,
    );
  }

  return response.json() as Promise<T>;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export function runMLAnalyticsDemo(signal?: AbortSignal): Promise<MLAnalyticsDemo> {
  return request<MLAnalyticsDemo>("/ml-analytics/demo", { signal, cache: "no-store" });
}

export function getAlerts(
  limit = 100,
  offset = 0,
  filters: AlertListFilters = {},
  signal?: AbortSignal,
): Promise<AlertListResponse> {
  const query = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (filters.status) query.set("status", filters.status);
  if (filters.severity) query.set("severity", filters.severity);
  if (filters.user_id?.trim()) query.set("user_id", filters.user_id.trim());
  return request<AlertListResponse>(`/alerts?${query.toString()}`, { signal });
}

export function getEvents(params: {
  limit?: number;
  offset?: number;
  user_id?: string;
  event_type?: string;
  source?: string;
} = {}, signal?: AbortSignal): Promise<SecurityEventListResponse> {
  const query = new URLSearchParams();
  query.set("limit", String(params.limit ?? 50));
  query.set("offset", String(params.offset ?? 0));
  if (params.user_id?.trim()) query.set("user_id", params.user_id.trim());
  if (params.event_type?.trim()) query.set("event_type", params.event_type.trim());
  if (params.source?.trim()) query.set("source", params.source.trim());
  return request<SecurityEventListResponse>(`/events?${query.toString()}`, { signal });
}

export function ingestEvent(payload: SecurityEventCreate): Promise<{
  id: string;
  source: string;
  external_id: string;
  event_type: string;
  user_id: string | null;
  entity_id: string | null;
  source_ip: string | null;
  event_time: string;
  status: string;
  duplicate: boolean;
}> {
  return request("/events", { method: "POST", body: JSON.stringify(payload) });
}

export function getBaseline(userId: string): Promise<BaselineResponse> {
  return request<BaselineResponse>(`/baselines/${encodeURIComponent(userId)}`);
}

export function rebuildBaseline(userId: string): Promise<BaselineResponse> {
  return request<BaselineResponse>(`/baselines/${encodeURIComponent(userId)}/rebuild`, { method: "POST" });
}

export function analyzeEvent(eventId: string): Promise<AnomalyAnalysis> {
  return request<AnomalyAnalysis>(`/anomalies/analyze/${encodeURIComponent(eventId)}`, { method: "POST" });
}

export function updateAlertStatus(
  alertId: string,
  status: AlertStatus,
): Promise<Alert> {
  return request<Alert>(
    `/alerts/${encodeURIComponent(alertId)}/status`,
    {
      method: "PATCH",
      body: JSON.stringify({ status }),
    },
  );
}

export function getAlertFeedback(
  alertId: string,
  signal?: AbortSignal,
): Promise<FeedbackListResponse> {
  return request<FeedbackListResponse>(
    `/alerts/${encodeURIComponent(alertId)}/feedback`,
    { signal },
  );
}

export function submitAlertFeedback(
  alertId: string,
  payload: {
    analyst_id: string;
    verdict: FeedbackVerdict;
    comment: string | null;
  },
): Promise<AnalystFeedback> {
  return request<AnalystFeedback>(
    `/alerts/${encodeURIComponent(alertId)}/feedback`,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
  );
}
