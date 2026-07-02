// Helpers de formatacao e cores (tema dark).

import type { OpportunityStatus } from "./types";

export function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

/** Classe de cor (texto) para um score 0-10. */
export function scoreTextColor(score: number | null | undefined): string {
  if (score == null) return "text-zinc-500";
  if (score >= 8) return "text-emerald-400";
  if (score >= 6) return "text-amber-400";
  return "text-rose-400";
}

/** Classe de cor (fundo) para a barra de um score 0-10. */
export function scoreBarColor(score: number | null | undefined): string {
  if (score == null) return "bg-zinc-600";
  if (score >= 8) return "bg-emerald-500";
  if (score >= 6) return "bg-amber-500";
  return "bg-rose-500";
}

export function statusLabel(status: OpportunityStatus): string {
  switch (status) {
    case "completed":
      return "Aprovado";
    case "partial":
      return "Parcial";
    case "discarded":
      return "Descartado";
    case "in_progress":
      return "Em analise";
  }
}

export function statusBadgeClasses(status: OpportunityStatus): string {
  switch (status) {
    case "completed":
      return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
    case "partial":
      return "bg-amber-500/15 text-amber-400 border-amber-500/30";
    case "discarded":
      return "bg-rose-500/15 text-rose-400 border-rose-500/30";
    case "in_progress":
      return "bg-sky-500/15 text-sky-400 border-sky-500/30";
  }
}

// Nomes amigaveis das dimensoes do score.
export const SCORE_DIMENSIONS: { key: string; label: string }[] = [
  { key: "market", label: "Mercado" },
  { key: "competition", label: "Concorrencia" },
  { key: "ease", label: "Execucao" },
  { key: "scalability", label: "Escalabilidade" },
  { key: "ai_potential", label: "Potencial IA" },
  { key: "profit", label: "Lucro" },
];

// Agentes -> rotulo + campo de dados, para a pagina de detalhe.
export const AGENT_SECTIONS: { key: string; label: string; agent: string }[] = [
  { key: "trend_data", label: "1. Trend Hunter", agent: "Tendencia" },
  { key: "problem_data", label: "2. Problem Hunter", agent: "Dor real" },
  { key: "competitor_data", label: "3. Competitor Hunter", agent: "Concorrentes" },
  { key: "market_data", label: "4. Market Size", agent: "TAM/SAM/SOM" },
  { key: "ai_opportunity_data", label: "5. AI Opportunity", agent: "IA resolve?" },
  { key: "compatibility_data", label: "6. Founder Compatibility", agent: "Fit do fundador" },
  { key: "monetization_data", label: "7. Monetization", agent: "Como ganhar" },
  { key: "score_data", label: "8. Scorer", agent: "Nota 0-10" },
  { key: "project_plan", label: "9. Project Generator", agent: "Plano + MVP" },
  { key: "devils_advocate_data", label: "10. Devil's Advocate", agent: "Riscos" },
];
