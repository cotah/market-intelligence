import Link from "next/link";
import { ScoreBadge } from "./ScoreBadge";
import { StatusBadge } from "./StatusBadge";
import { formatDate } from "@/lib/format";
import type { OpportunityListItem } from "@/lib/types";

export function OpportunityCard({ opp }: { opp: OpportunityListItem }) {
  return (
    <Link
      href={`/opportunities/${opp.id}`}
      className="group flex flex-col gap-3 rounded-xl border border-zinc-800 bg-zinc-900/50 p-4 transition-colors hover:border-zinc-700 hover:bg-zinc-900"
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-medium leading-snug text-zinc-100 group-hover:text-white">
          {opp.title}
        </h3>
        <ScoreBadge score={opp.score_total} />
      </div>

      <div className="flex items-center justify-between">
        <StatusBadge status={opp.status} />
        <span className="text-xs text-zinc-500">{formatDate(opp.created_at)}</span>
      </div>

      {opp.status === "discarded" && opp.discard_reason && (
        <p className="rounded-md border border-rose-500/20 bg-rose-500/5 px-2.5 py-1.5 text-xs text-rose-300">
          {opp.discard_reason}
        </p>
      )}
    </Link>
  );
}
