const API_BASE = import.meta.env.VITE_API_URL || "";

export interface ResearchJob {
  id: string;
  question: string;
  status: "pending" | "running" | "complete" | "failed";
  result: string;
  trace: Record<string, unknown>;
  costs: CostData;
  events: AgentEvent[];
  created_at: number;
  completed_at: number;
}

export interface AgentEvent {
  timestamp: number;
  agent: string;
  event_type: string;
  message: string;
}

export interface CostData {
  total_tokens?: number;
  total_cost_usd?: number;
  by_model?: Record<string, number>;
  by_agent?: Record<string, number>;
}

export interface SystemStats {
  total_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  total_cost_usd: number;
  avg_completion_time_s: number;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    throw new Error(`API error: ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function submitResearch(
  question: string
): Promise<{ job_id: string }> {
  return fetchJson(`${API_BASE}/research`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
}

export async function getResearch(id: string): Promise<ResearchJob> {
  return fetchJson(`${API_BASE}/research/${id}`);
}

export async function getTrace(
  id: string
): Promise<{ job_id: string; trace: Record<string, unknown> }> {
  return fetchJson(`${API_BASE}/research/${id}/trace`);
}

export async function getCosts(
  id: string
): Promise<{ job_id: string; costs: CostData }> {
  return fetchJson(`${API_BASE}/research/${id}/costs`);
}

export async function listJobs(): Promise<{ jobs: ResearchJob[] }> {
  return fetchJson(`${API_BASE}/jobs`);
}

export async function getSystemStats(): Promise<SystemStats> {
  return fetchJson(`${API_BASE}/system`);
}

export function connectWebSocket(
  jobId: string,
  onEvent: (event: AgentEvent) => void
): WebSocket {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const host = API_BASE
    ? new URL(API_BASE).host
    : window.location.host;
  const ws = new WebSocket(`${protocol}//${host}/ws/${jobId}`);

  ws.onmessage = (msg) => {
    try {
      const event = JSON.parse(msg.data) as AgentEvent;
      onEvent(event);
    } catch {
      console.warn("Failed to parse WebSocket message");
    }
  };

  ws.onerror = () => {
    console.warn("WebSocket error for job", jobId);
  };

  return ws;
}
