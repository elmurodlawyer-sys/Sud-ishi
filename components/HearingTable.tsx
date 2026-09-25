import Link from "next/link";
import type { HearingRow } from "@/lib/cases";
import { daysUntil, fmtDate } from "@/lib/format";

export default function HearingTable({ rows, showResult = false }: { rows: HearingRow[]; showResult?: boolean }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Sana</th><th>Ish</th><th>Taraflar</th><th>Sud / joy</th><th>Mas'ul</th>
            {showResult && <th>Natija</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((h) => {
            const d = daysUntil(h.scheduled_at);
            return (
              <tr key={h.id}>
                <td className="nowrap">
                  {fmtDate(h.scheduled_at)}
                  {!showResult && (
                    <div className="muted small">
                      {d === 0 ? "bugun" : d > 0 ? `${d} kundan so'ng` : `${-d} kun oldin`}
                    </div>
                  )}
                </td>
                <td><Link href={`/ishlar/${h.case_id}`}>{h.case_number}</Link></td>
                <td>{h.plaintiff} — {h.defendant}</td>
                <td>{h.court}{h.location && <div className="muted small">{h.location}</div>}</td>
                <td>{h.responsible || "—"}</td>
                {showResult && <td>{h.result}</td>}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
