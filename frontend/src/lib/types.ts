// Tipos que espelham as respostas do backend FastAPI.

export type OpportunityStatus = "in_progress" | "completed" | "partial" | "discarded";

export interface ScoreData {
  total?: number;
  market?: number;
  competition?: number;
  ease?: number;
  scalability?: number;
  ai_potential?: number;
  profit?: number;
  reasoning?: string;
  [key: string]: unknown;
}

// Item enxuto usado na listagem.
export interface OpportunityListItem {
  id: string;
  title: string;
  topic_origin: string;
  status: OpportunityStatus;
  score_total: number | null;
  discard_reason: string | null;
  created_at: string;
}

// Oportunidade completa (pagina de detalhe).
export interface Opportunity {
  id: string;
  title: string;
  summary: string;
  topic_origin: string;
  source: string;
  status: OpportunityStatus;
  discard_reason: string | null;
  discarded_by: string | null;
  failed_agents: { agent: string; error: string }[] | null;

  trend_data: Record<string, unknown> | null;
  problem_data: Record<string, unknown> | null;
  competitor_data: Record<string, unknown> | null;
  market_data: Record<string, unknown> | null;
  ai_opportunity_data: Record<string, unknown> | null;
  compatibility_data: Record<string, unknown> | null;
  monetization_data: Record<string, unknown> | null;
  score_data: ScoreData | null;
  project_plan: Record<string, unknown> | null;
  devils_advocate_data: Record<string, unknown> | null;

  score_total: number | null;
  created_at: string;
  updated_at: string;
}

export interface DailyReport {
  id: string;
  report_date: string;
  total_analyzed: number;
  promising_count: number;
  excellent_count: number;
  summary: string;
  payload: Record<string, unknown> | null;
  created_at: string;
}

export interface PipelineStatus {
  enabled: boolean;
  redis_available: boolean;
  last_run: Record<string, unknown> | null;
}

export interface PipelineAction {
  ok: boolean;
  message: string;
  task_id: string | null;
}

// Perfil do fundador (editavel em /profile). Espelha FounderProfileSchema.
export interface FounderProfile {
  name: string;
  current_country: string;
  active_markets: string[];
  technical_skills: string[];
  business_skills: string[];
  target_business_type: string[];
  ai_tools: string[];
  software_tools: string[];
  hardware_tools: string[];
  active_projects: string;
  budget_range: string;
  avoid: string[];
  languages: string[];
}
