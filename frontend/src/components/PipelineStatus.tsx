"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { PipelineStatus as PipelineStatusType } from "@/lib/types";

const POLL_MS = 5000;

interface Props {
  onAction?: () => void; // chamado apos run-once para a lista recarregar
}

export function PipelineStatus({ onAction }: Props) {
  const [status, setStatus] = useState<PipelineStatusType | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const s = await api.pipelineStatus();
      setStatus(s);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao buscar status");
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  async function act(
    name: string,
    fn: () => Promise<{ ok: boolean; message: string }>,
  ) {
    setBusy(name);
    setFlash(null);
    try {
      const res = await fn();
      setFlash(res.message);
      await refresh();
      if (name === "run" && onAction) onAction();
    } catch (e) {
      setFlash(e instanceof Error ? e.message : "Erro");
    } finally {
      setBusy(null);
    }
  }

  const enabled = status?.enabled ?? false;
  const lastRun = status?.last_run ?? null;

  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <span className="relative flex h-3 w-3">
            {enabled && (
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            )}
            <span
              className={`relative inline-flex h-3 w-3 rounded-full ${
                enabled ? "bg-emerald-500" : "bg-zinc-600"
              }`}
            />
          </span>
          <div>
            <p className="text-sm font-medium text-zinc-100">
              Pipeline {enabled ? "rodando" : "parado"}
            </p>
            <p className="text-xs text-zinc-500">
              Redis:{" "}
              <span className={status?.redis_available ? "text-emerald-400" : "text-rose-400"}>
                {status?.redis_available ? "ok" : "indisponivel"}
              </span>
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            label="Start"
            color="emerald"
            loading={busy === "start"}
            disabled={enabled}
            onClick={() => act("start", api.startPipeline)}
          />
          <Button
            label="Stop"
            color="rose"
            loading={busy === "stop"}
            disabled={!enabled}
            onClick={() => act("stop", api.stopPipeline)}
          />
          <Button
            label="Run Once"
            color="sky"
            loading={busy === "run"}
            onClick={() => act("run", api.runOnce)}
          />
        </div>
      </div>

      {lastRun && (
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t border-zinc-800 pt-3 text-xs text-zinc-400">
          {"topics" in lastRun && <span>Topicos: {String(lastRun.topics)}</span>}
          {"completed" in lastRun && (
            <span className="text-emerald-400">Aprovadas: {String(lastRun.completed)}</span>
          )}
          {"discarded" in lastRun && (
            <span className="text-rose-400">Descartadas: {String(lastRun.discarded)}</span>
          )}
        </div>
      )}

      {flash && <p className="mt-2 text-xs text-zinc-400">{flash}</p>}
      {error && <p className="mt-2 text-xs text-rose-400">{error}</p>}
    </div>
  );
}

function Button({
  label,
  color,
  onClick,
  loading,
  disabled,
}: {
  label: string;
  color: "emerald" | "rose" | "sky";
  onClick: () => void;
  loading?: boolean;
  disabled?: boolean;
}) {
  const colors: Record<string, string> = {
    emerald: "bg-emerald-600 hover:bg-emerald-500",
    rose: "bg-rose-600 hover:bg-rose-500",
    sky: "bg-sky-600 hover:bg-sky-500",
  };
  return (
    <button
      onClick={onClick}
      disabled={loading || disabled}
      className={`rounded-md px-3 py-1.5 text-sm font-medium text-white transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${colors[color]}`}
    >
      {loading ? "..." : label}
    </button>
  );
}
