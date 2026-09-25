import Link from "next/link";
import { listCases, type CaseFilters } from "@/lib/cases";
import { CATEGORIES, REGIONS, ROLES, STATUSES, labelOf } from "@/lib/constants";
import { fmtDate, fmtMoney } from "@/lib/format";
import StatusBadge from "@/components/StatusBadge";

export const dynamic = "force-dynamic";

type SP = Promise<Record<string, string | string[] | undefined>>;

export default async function CasesPage({ searchParams }: { searchParams: SP }) {
  const sp = await searchParams;
  const one = (k: string) => (typeof sp[k] === "string" ? (sp[k] as string) : "");
  const filters: CaseFilters = {
    q: one("q"), status: one("status"), category: one("category"),
    region: one("region"), role: one("role"), sort: one("sort"),
  };
  const cases = listCases(filters);
  const hasFilters = Object.values(filters).some(Boolean);

  return (
    <>
      <div className="page-head">
        <h1>Ishlar <span className="muted">({cases.length})</span></h1>
        <Link href="/ishlar/yangi" className="btn primary">+ Yangi ish</Link>
      </div>

      <form className="card filters" method="get">
        <input name="q" defaultValue={filters.q} placeholder="Qidirish: raqam, taraf, sud, predmet…" />
        <select name="status" defaultValue={filters.status}>
          <option value="">Barcha holatlar</option>
          <option value="faol">Faqat faol</option>
          {STATUSES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <select name="category" defaultValue={filters.category}>
          <option value="">Barcha turlar</option>
          {CATEGORIES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <select name="role" defaultValue={filters.role}>
          <option value="">Barcha rollar</option>
          {ROLES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
        <select name="region" defaultValue={filters.region}>
          <option value="">Barcha hududlar</option>
          {REGIONS.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
        <select name="sort" defaultValue={filters.sort}>
          <option value="">Oxirgi o'zgarish</option>
          <option value="majlis">Keyingi majlis</option>
          <option value="raqam">Ish raqami</option>
          <option value="summa">Da'vo summasi</option>
        </select>
        <button className="btn primary" type="submit">Qo'llash</button>
        {hasFilters && <Link href="/ishlar" className="btn">Tozalash</Link>}
      </form>

      {cases.length === 0 ? (
        <div className="card empty">
          {hasFilters ? "Filtrga mos ish topilmadi." : <>Hali ishlar yo'q. <Link href="/ishlar/yangi">Birinchi ishni qo'shing</Link>.</>}
        </div>
      ) : (
        <div className="card table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Ish raqami</th><th>Taraflar</th><th>Tur / rol</th><th>Sud</th>
                <th>Summa</th><th>Keyingi majlis</th><th>Holat</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id}>
                  <td><Link href={`/ishlar/${c.id}`}><b>{c.case_number}</b></Link></td>
                  <td>
                    {c.plaintiff || "—"} — {c.defendant || "—"}
                    {c.subject && <div className="muted small clamp">{c.subject}</div>}
                  </td>
                  <td>{labelOf(CATEGORIES, c.category)}<div className="muted small">{labelOf(ROLES, c.role)}</div></td>
                  <td>{c.court}<div className="muted small">{c.region}</div></td>
                  <td className="nowrap">{fmtMoney(c.claim_amount)}</td>
                  <td className="nowrap">{fmtDate(c.next_hearing)}</td>
                  <td><StatusBadge status={c.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
