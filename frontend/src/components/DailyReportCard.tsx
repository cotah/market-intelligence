import { formatDate } from "@/lib/format";
import type { DailyReport } from "@/lib/types";

export function DailyReportCard({ report }: { report: DailyReport }) {
  const best = (report.payload?.best_of_day ?? null) as
    | { title?: string; score?: number }
    | null;

  return (
    <article className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-5">
      <header className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-zinc-100">{report.report_date}</h2>
        <span className="text-xs text-zinc-500">{formatDate(report.created_at)}</span>
      </header>

      <div className="mb-4 grid grid-cols-3 gap-3">
        <Stat label="Analisadas" value={report.total_analyzed} />
        <Stat label="Promissoras" value={report.promising_count} color="text-amber-400" />
        <Stat label="Excelentes" value={report.excellent_count} color="text-emerald-400" />
      </div>

      {best && best.title && (
        <div className="mb-4 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2">
          <p className="text-xs uppercase tracking-wide text-emerald-500/80">Melhor do dia</p>
          <p className="mt-0.5 text-sm text-zinc-100">
            {best.title}{" "}
            {best.score != null && (
              <span className="font-semibold text-emerald-400">({best.score.toFixed(1)})</span>
            )}
          </p>
        </div>
      )}

      {report.summary && (
        <p className="whitespace-pre-line text-sm leading-relaxed text-zinc-300">
          {report.summary}
        </p>
      )}
    </article>
  );
}

function Stat({
  label,
  value,
  color = "text-zinc-100",
}: {
  label: string;
  value: number;
  color?: string;
}) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950/50 px-3 py-2 text-center">
      <p className={`text-2xl font-bold tabular-nums ${color}`}>{value}</p>
      <p className="text-xs text-zinc-500">{label}</p>
    </div>
  );
}
