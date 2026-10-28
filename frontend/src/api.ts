const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8001";

export type AlertStatus =
  | "open"
  | "investigating"
  | "resolved"
  | "dismissed";

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

interface AlertListResponse {
  items: Alert[];
}

interface HealthResponse {
  status: string;
  service?: string;
  environment?: string;
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

export function getAlerts(): Promise<AlertListResponse> {
  return request<AlertListResponse>("/alerts");
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
