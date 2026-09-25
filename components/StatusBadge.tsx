import { STATUSES, labelOf } from "@/lib/constants";

export default function StatusBadge({ status }: { status: string }) {
  return <span className={`badge s-${status}`}>{labelOf(STATUSES, status)}</span>;
}
