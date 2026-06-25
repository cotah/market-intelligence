// Cliente do backend. Todas as chamadas sao client-side (NEXT_PUBLIC_API_URL).

import type {
  DailyReport,
  Opportunity,
  OpportunityListItem,
  OpportunityStatus,
  PipelineAction,
  PipelineStatus,
} from "./types";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(
      `Nao foi possivel conectar ao backend (${BASE_URL}). Ele esta rodando?`,
    );
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(`Erro ${res.status}: ${detail}`, res.status);
  }
  return res.json() as Promise<T>;
}

export interface OpportunityFilters {
  scoreMin?: number;
  status?: OpportunityStatus;
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  listOpportunities: (filters: OpportunityFilters = {}) => {
    const params = new URLSearchParams();
    if (filters.scoreMin != null) params.set("score_min", String(filters.scoreMin));
    if (filters.status) params.set("status", filters.status);
    const qs = params.toString();
    return request<OpportunityListItem[]>(`/opportunities${qs ? `?${qs}` : ""}`);
  },

  getOpportunity: (id: string) => request<Opportunity>(`/opportunities/${id}`),

  listDailyReports: () => request<DailyReport[]>("/reports/daily"),
  latestDailyReport: () => request<DailyReport>("/reports/daily/latest"),
  generateDailyReport: () =>
    request<PipelineAction>("/reports/daily/generate", { method: "POST" }),

  pipelineStatus: () => request<PipelineStatus>("/pipeline/status"),
  startPipeline: () => request<PipelineAction>("/pipeline/start", { method: "POST" }),
  stopPipeline: () => request<PipelineAction>("/pipeline/stop", { method: "POST" }),
  runOnce: () => request<PipelineAction>("/pipeline/run-once", { method: "POST" }),
};

export { ApiError, BASE_URL };
