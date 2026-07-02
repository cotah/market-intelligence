"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { JsonView } from "@/components/JsonView";
import { ScoreBadge } from "@/components/ScoreBadge";
import { ScoreBar } from "@/components/ScoreBar";
import { StatusBadge } from "@/components/StatusBadge";
import { api } from "@/lib/api";
import { AGENT_SECTIONS, SCORE_DIMENSIONS, formatDate } from "@/lib/format";
import type { Opportunity } from "@/lib/types";

export default function OpportunityDetailPage() {
  const params = useParams<{ id: string }>();
  const [opp, setOpp] = useState<Opportunity | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!params.id) return;
    api
      .getOpportunity(params.id)
      .then((data) => {
        setOpp(data);
        setError(null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  }, [params.id]);

  if (loading) {
    return <p className="py-12 text-center text-sm text-zinc-500">Carregando...</p>;
  }
  if (error || !opp) {
    return (
      <div className="space-y-4">
        <BackLink />
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
          {error ?? "Oportunidade nao encontrada"}
        </div>
      </div>
    );
  }

  const score = opp.score_data;

  return (
    <div className="space-y-6">
      <BackLink />

      {/* Cabecalho */}
      <header className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold text-zinc-100">{opp.title}</h1>
            <div className="flex flex-wrap items-center gap-3">
              <StatusBadge status={opp.status} />
              {opp.status === "completed" && opp.score_data?.risk_flag === "high" && (
                <span
                  className="inline-flex items-center rounded-full border border-amber-500/30 bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-400"
                  title="O Devil's Advocate encontrou riscos relevantes (fatal flaws / severidade alta)"
                >
                  Com ressalvas
                </span>
              )}
              <span className="text-xs text-zinc-500">
                Origem: {opp.topic_origin} · {formatDate(opp.created_at)}
              </span>
            </div>
          </div>
          <ScoreBadge score={opp.score_total} />
        </div>

        {opp.status === "discarded" && opp.discard_reason && (
          <div className="mt-4 rounded-lg border border-rose-500/20 bg-rose-500/5 px-3 py-2 text-sm text-rose-300">
            <span className="font-medium">Descartado por {opp.discarded_by}:</span>{" "}
            {opp.discard_reason}
          </div>
        )}
      </header>

      {/* Score por dimensao */}
      {score && (
        <section className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-zinc-400">
            Score por dimensao
          </h2>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            {SCORE_DIMENSIONS.map((dim) => (
              <ScoreBar
                key={dim.key}
                label={dim.label}
                value={typeof score[dim.key] === "number" ? (score[dim.key] as number) : null}
              />
            ))}
          </div>
          {typeof score.reasoning === "string" && score.reasoning && (
            <p className="mt-4 border-t border-zinc-800 pt-3 text-sm text-zinc-400">
              {score.reasoning}
            </p>
          )}
        </section>
      )}

      {/* Dados de cada agente */}
      <section className="space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-zinc-400">
          Dados dos agentes
        </h2>
        {AGENT_SECTIONS.map((sec) => {
          const data = opp[sec.key as keyof Opportunity] as Record<string, unknown> | null;
          return <AgentSection key={sec.key} title={sec.label} subtitle={sec.agent} data={data} />;
        })}
      </section>
    </div>
  );
}

function AgentSection({
  title,
  subtitle,
  data,
}: {
  title: string;
  subtitle: string;
  data: Record<string, unknown> | null;
}) {
  const hasData = data && Object.keys(data).length > 0;
  return (
    <details
      open={!!hasData}
      className="overflow-hidden rounded-xl border border-zinc-800 bg-zinc-900/50"
    >
      <summary className="flex cursor-pointer items-center justify-between px-5 py-3 hover:bg-zinc-900">
        <span className="font-medium text-zinc-100">{title}</span>
        <span className="text-xs text-zinc-500">
          {hasData ? subtitle : "sem dados"}
        </span>
      </summary>
      {hasData && (
        <div className="border-t border-zinc-800 px-5 py-4 text-sm">
          <JsonView value={data} />
        </div>
      )}
    </details>
  );
}

function BackLink() {
  return (
    <Link href="/" className="text-sm text-zinc-400 transition-colors hover:text-zinc-100">
      &larr; Voltar ao dashboard
    </Link>
  );
}
