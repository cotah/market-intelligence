import { statusBadgeClasses, statusLabel } from "@/lib/format";
import type { OpportunityStatus } from "@/lib/types";

export function StatusBadge({ status }: { status: OpportunityStatus }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${statusBadgeClasses(status)}`}
    >
      {statusLabel(status)}
    </span>
  );
}
