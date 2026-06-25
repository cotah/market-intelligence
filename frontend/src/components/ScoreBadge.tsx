import { scoreTextColor } from "@/lib/format";

export function ScoreBadge({ score }: { score: number | null | undefined }) {
  return (
    <div className="flex items-baseline gap-1">
      <span className={`text-2xl font-bold tabular-nums ${scoreTextColor(score)}`}>
        {score != null ? score.toFixed(1) : "—"}
      </span>
      <span className="text-xs text-zinc-500">/10</span>
    </div>
  );
}
