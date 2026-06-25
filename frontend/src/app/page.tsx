"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { OpportunityCard } from "@/components/OpportunityCard";
import { PipelineStatus } from "@/components/PipelineStatus";
import { api } from "@/lib/api";
import type { OpportunityListItem, OpportunityStatus } from "@/lib/types";

type StatusFilter = "all" | OpportunityStatus;
type ScoreFilter = "all" | "6" | "8";

export default function DashboardPage() {
  const [opps, setOpps] = useState<OpportunityListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [scoreFilter, setScoreFilter] = useState<ScoreFilter>("all");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listOpportunities({
        status: statusFilter === "all" ? undefined : statusFilter,
        scoreMin: scoreFilter === "all" ? undefined : Number(scoreFilter),
      });
      setOpps(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar oportunidades");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, scoreFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const counts = useMemo(() => {
    return {
      total: opps.length,
      approved: opps.filter((o) => o.status === "completed").length,
      discarded: opps.filter((o) => o.status === "discarded").length,
    };
  }, [opps]);

  return (
    <div className="space-y-6">
      <PipelineStatus onAction={load} />

      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-semibold text-zinc-100">Oportunidades</h1>
            <p className="text-sm text-zinc-500">
              {counts.total} no total · {counts.approved} aprovadas · {counts.discarded} descartadas
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Select
              label="Status"
              value={statusFilter}
              onChange={(v) => setStatusFilter(v as StatusFilter)}
              options={[
                { value: "all", label: "Todos" },
                { value: "completed", label: "Aprovados" },
                { value: "discarded", label: "Descartados" },
                { value: "in_progress", label: "Em analise" },
              ]}
            />
            <Select
              label="Score min"
              value={scoreFilter}
              onChange={(v) => setScoreFilter(v as ScoreFilter)}
              options={[
                { value: "all", label: "Qualquer" },
                { value: "6", label: ">= 6" },
                { value: "8", label: ">= 8" },
              ]}
            />
            <button
              onClick={load}
              className="rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm text-zinc-200 transition-colors hover:bg-zinc-700"
            >
              Atualizar
            </button>
          </div>
        </div>

        {error && (
          <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
            {error}
          </div>
        )}

        {loading ? (
          <p className="py-12 text-center text-sm text-zinc-500">Carregando...</p>
        ) : opps.length === 0 && !error ? (
          <p className="py-12 text-center text-sm text-zinc-500">
            Nenhuma oportunidade. Rode o pipeline (Run Once) para gerar.
          </p>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {opps.map((opp) => (
              <OpportunityCard key={opp.id} opp={opp} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="flex items-center gap-2 rounded-md border border-zinc-700 bg-zinc-800 px-2.5 py-1.5 text-sm">
      <span className="text-zinc-500">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-transparent text-zinc-200 outline-none"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value} className="bg-zinc-900">
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}
