import Link from "next/link";
import { appealDeadlines, getStats, overdueHearings, upcomingHearings } from "@/lib/cases";
import { CATEGORIES, OUTCOMES, STATUSES, labelOf } from "@/lib/constants";
import { daysUntil, fmtDate, fmtMoney } from "@/lib/format";
import HearingTable from "@/components/HearingTable";

export const dynamic = "force-dynamic";

function Bars({ data, total }: { data: { label: string; n: number; href?: string }[]; total: number }) {
  return (
    <ul className="bars">
      {data.map((d) => (
        <li key={d.label}>
          <span className="bar-label">{d.href ? <Link href={d.href}>{d.label}</Link> : d.label}</span>
          <span className="bar-track">
            <span className="bar-fill" style={{ width: `${total ? (d.n / total) * 100 : 0}%` }} />
          </span>
          <span className="bar-n">{d.n}</span>
        </li>
      ))}
    </ul>
  );
}

export default function Dashboard() {
  const stats = getStats();
  const week = upcomingHearings(7);
  const overdue = overdueHearings();
  const appeals = appealDeadlines(10);
  const decided = OUTCOMES.filter((o) => o.value && stats.byOutcome[o.value]);

  return (
    <>
      <h1>Boshqaruv paneli</h1>

      <section className="kpis">
        <Link href="/ishlar" className="kpi"><b>{stats.total}</b><span>Jami ishlar</span></Link>
        <Link href="/ishlar?status=faol" className="kpi"><b>{stats.active}</b><span>Faol ishlar</span></Link>
        <Link href="/majlislar" className="kpi"><b>{week.length}</b><span>7 kunlik majlislar</span></Link>
        <Link href="/majlislar#natijasiz" className={`kpi${overdue.length ? " warn" : ""}`}>
          <b>{overdue.length}</b><span>Natijasi kiritilmagan</span>
        </Link>
        <div className="kpi"><b className="money">{fmtMoney(stats.claimActive)}</b><span>Faol da'volar summasi</span></div>
      </section>

      {overdue.length > 0 && (
        <section className="card warn-card">
          <h2>⚠️ Natijasi kiritilmagan majlislar</h2>
          <HearingTable rows={overdue} />
        </section>
      )}

      {appeals.length > 0 && (
        <section className="card warn-card">
          <h2>⏳ Shikoyat muddati yaqinlashmoqda (10 kun)</h2>
          <table className="table">
            <thead><tr><th>Ish</th><th>Taraflar</th><th>Qaror</th><th>Muddat</th></tr></thead>
            <tbody>
              {appeals.map((c) => {
                const d = daysUntil(c.appeal_deadline!);
                return (
                  <tr key={c.id}>
                    <td><Link href={`/ishlar/${c.id}`}>{c.case_number}</Link></td>
                    <td>{c.plaintiff} — {c.defendant}</td>
                    <td>{labelOf(OUTCOMES, c.outcome)} ({fmtDate(c.decision_date)})</td>
                    <td><b>{fmtDate(c.appeal_deadline)}</b> <span className="muted">({d === 0 ? "bugun" : `${d} kun`})</span></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </section>
      )}

      <section className="card">
        <h2>Yaqin 7 kundagi sud majlislari</h2>
        {week.length ? <HearingTable rows={week} /> : <p className="muted">Rejalashtirilgan majlislar yo'q.</p>}
      </section>

      <div className="cols">
        <section className="card">
          <h2>Holatlar bo'yicha</h2>
          <Bars
            total={stats.total}
            data={STATUSES.filter((s) => stats.byStatus[s.value]).map((s) => ({
              label: s.label, n: stats.byStatus[s.value], href: `/ishlar?status=${s.value}`,
            }))}
          />
        </section>
        <section className="card">
          <h2>Ish turlari bo'yicha</h2>
          <Bars
            total={stats.total}
            data={CATEGORIES.filter((c) => stats.byCategory[c.value]).map((c) => ({
              label: c.label, n: stats.byCategory[c.value], href: `/ishlar?category=${c.value}`,
            }))}
          />
          {decided.length > 0 && (
            <>
              <h3>Hal qilingan ishlar natijasi</h3>
              <Bars
                total={decided.reduce((s, o) => s + stats.byOutcome[o.value], 0)}
                data={decided.map((o) => ({ label: o.label, n: stats.byOutcome[o.value] }))}
              />
            </>
          )}
        </section>
        <section className="card">
          <h2>Hududlar bo'yicha</h2>
          <Bars
            total={stats.total}
            data={stats.byRegion.map((r) => ({
              label: r.region, n: r.n, href: `/ishlar?region=${encodeURIComponent(r.region)}`,
            }))}
          />
        </section>
      </div>
    </>
  );
}
