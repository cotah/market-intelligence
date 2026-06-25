import { scoreBarColor } from "@/lib/format";

interface ScoreBarProps {
  label: string;
  value: number | null | undefined;
}

export function ScoreBar({ label, value }: ScoreBarProps) {
  const pct = value != null ? Math.max(0, Math.min(100, (value / 10) * 100)) : 0;
  return (
    <div className="flex items-center gap-2">
      <span className="w-28 shrink-0 text-xs text-zinc-400">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-zinc-800">
        <div
          className={`h-full rounded-full ${scoreBarColor(value)}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="w-8 shrink-0 text-right text-xs tabular-nums text-zinc-300">
        {value != null ? value.toFixed(0) : "—"}
      </span>
    </div>
  );
}
