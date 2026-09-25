import { overdueHearings, pastHearings, upcomingHearings } from "@/lib/cases";
import HearingTable from "@/components/HearingTable";

export const dynamic = "force-dynamic";

export default function HearingsPage() {
  const upcoming = upcomingHearings(null);
  const overdue = overdueHearings();
  const past = pastHearings(30);

  return (
    <>
      <h1>Sud majlislari</h1>

      <section className="card">
        <h2>Kelgusi majlislar ({upcoming.length})</h2>
        {upcoming.length ? <HearingTable rows={upcoming} /> : <p className="muted">Rejalashtirilgan majlislar yo'q.</p>}
      </section>

      <section className="card warn-card" id="natijasiz">
        <h2>Natijasi kiritilmagan ({overdue.length})</h2>
        {overdue.length ? <HearingTable rows={overdue} /> : <p className="muted">Hammasi joyida.</p>}
      </section>

      <section className="card">
        <h2>O'tgan majlislar (oxirgi 30 ta)</h2>
        {past.length ? <HearingTable rows={past} showResult /> : <p className="muted">Hali yo'q.</p>}
      </section>
    </>
  );
}
