"use client";

import { useCallback, useEffect, useState } from "react";
import { DailyReportCard } from "@/components/DailyReportCard";
import { api } from "@/lib/api";
import type { DailyReport } from "@/lib/types";

export default function ReportsPage() {
  const [reports, setReports] = useState<DailyReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listDailyReports();
      setReports(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar relatorios");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function generate() {
    setBusy(true);
    setFlash(null);
    try {
      const res = await api.generateDailyReport();
      setFlash(res.message + " (atualize em alguns segundos)");
    } catch (e) {
      setFlash(e instanceof Error ? e.message : "Erro");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold text-zinc-100">Relatorios diarios</h1>
          <p className="text-sm text-zinc-500">Consolidacao das oportunidades por dia.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={generate}
            disabled={busy}
            className="rounded-md bg-sky-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-sky-500 disabled:opacity-40"
          >
            {busy ? "..." : "Gerar agora"}
          </button>
          <button
            onClick={load}
            className="rounded-md border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-sm text-zinc-200 transition-colors hover:bg-zinc-700"
          >
            Atualizar
          </button>
        </div>
      </div>

      {flash && <p className="text-xs text-zinc-400">{flash}</p>}
      {error && (
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
          {error}
        </div>
      )}

      {loading ? (
        <p className="py-12 text-center text-sm text-zinc-500">Carregando...</p>
      ) : reports.length === 0 && !error ? (
        <p className="py-12 text-center text-sm text-zinc-500">
          Nenhum relatorio ainda. Clique em &quot;Gerar agora&quot;.
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {reports.map((r) => (
            <DailyReportCard key={r.id} report={r} />
          ))}
        </div>
      )}
    </div>
  );
}
