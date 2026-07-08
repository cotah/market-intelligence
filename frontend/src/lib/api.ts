// Cliente do backend. Tudo passa por proxies server-side no proprio Next.js;
// o navegador nunca fala direto com o backend nem conhece nenhuma chave.
// - Leituras   -> /api/data/*    (injeta READ_API_KEY)
// - Controle   -> /api/control/* (injeta CONTROL_API_KEY)
// Ambos exigem sessao valida (ver src/middleware.ts).

import type {
  DailyReport,
  FounderProfile,
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
  // Caminho relativo (/api/control/...) = proxy no proprio Next.js.
  const url = path.startsWith("/api/") ? path : `${BASE_URL}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
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

// Prefixo das acoes de controle: passam pelo proxy server-side.
const CONTROL = "/api/control";
// Prefixo das leituras: passam pelo proxy server-side (injeta READ_API_KEY).
const DATA = "/api/data";

export interface OpportunityFilters {
  scoreMin?: number;
  status?: OpportunityStatus;
}

export const api = {
  health: () => request<{ status: string }>(`${DATA}/health`),

  listOpportunities: (filters: OpportunityFilters = {}) => {
    const params = new URLSearchParams();
    if (filters.scoreMin != null) params.set("score_min", String(filters.scoreMin));
    if (filters.status) params.set("status", filters.status);
    const qs = params.toString();
    return request<OpportunityListItem[]>(`${DATA}/opportunities${qs ? `?${qs}` : ""}`);
  },

  getOpportunity: (id: string) => request<Opportunity>(`${DATA}/opportunities/${id}`),

  listDailyReports: () => request<DailyReport[]>(`${DATA}/reports/daily`),
  latestDailyReport: () => request<DailyReport>(`${DATA}/reports/daily/latest`),
  generateDailyReport: () =>
    request<PipelineAction>(`${CONTROL}/reports/daily/generate`, { method: "POST" }),

  pipelineStatus: () => request<PipelineStatus>(`${DATA}/pipeline/status`),
  startPipeline: () =>
    request<PipelineAction>(`${CONTROL}/pipeline/start`, { method: "POST" }),
  stopPipeline: () =>
    request<PipelineAction>(`${CONTROL}/pipeline/stop`, { method: "POST" }),
  runOnce: () =>
    request<PipelineAction>(`${CONTROL}/pipeline/run-once`, { method: "POST" }),

  getFounderProfile: () => request<FounderProfile>("/founder-profile"),
  saveFounderProfile: (profile: FounderProfile) =>
    request<FounderProfile>(`${CONTROL}/founder-profile`, {
      method: "PUT",
      body: JSON.stringify(profile),
    }),
};

export { ApiError, BASE_URL };
