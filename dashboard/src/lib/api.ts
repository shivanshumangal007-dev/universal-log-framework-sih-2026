const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

function getToken(): string | null {
  return localStorage.getItem("token");
}

async function request<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const token = getToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options?.headers as Record<string, string>) || {}),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    localStorage.removeItem("token");
    window.location.reload();
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `HTTP ${res.status}`);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return res.json() as Promise<T>;
}

export interface ParsedLog {
  event_id: string;
  source: string;
  raw_line: string;
  event_timestamp: string;
  format: string;
  fields_json: string;
  metadata_json: string;
  ingested_at: string;
}

export interface ReviewItem {
  event_id: string;
  source: string;
  raw_line: string;
  event_timestamp: string;
  format: string;
  fields_json: string;
  metadata_json: string;
  ingested_at: string;
  confidence: number;
  status: string;
}

export interface StatsThroughput {
  events_last_10s: number;
}

export const api = {
  login: (username: string, password: string) =>
    request<{ access_token: string; token_type: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  getRecentLogs: (limit = 50) =>
    request<ParsedLog[]>(`/api/logs/recent?limit=${limit}`),

  getReviewQueue: (status = "pending") =>
    request<ReviewItem[]>(`/api/review-queue?status=${status}`),

  approveReview: (eventId: string) =>
    request<{ status: string }>(`/api/review-queue/${eventId}/approve`, {
      method: "POST",
    }),

  rejectReview: (eventId: string) =>
    request<{ status: string }>(`/api/review-queue/${eventId}/reject`, {
      method: "POST",
    }),

  getThroughput: () => request<StatsThroughput>("/api/stats/throughput"),

  getInferenceStats: () => request<Record<string, unknown>>("/inference/stats"),
};
