import Link from "next/link";
import { notFound } from "next/navigation";
import { getCase, getEvents, getHearings } from "@/lib/cases";
import { CATEGORIES, OUTCOMES, ROLES, labelOf } from "@/lib/constants";
import { daysUntil, fmtDate, fmtMoney, nowLocal } from "@/lib/format";
import {
  addHearingAction, deleteCaseAction, deleteHearingAction, setHearingResultAction,
} from "@/app/actions";
import StatusBadge from "@/components/StatusBadge";
import ConfirmButton from "@/components/ConfirmButton";

export const dynamic = "force-dynamic";

export default async function CasePage({ params }: { params: Promise<{ id: string }> }) {
  const c = getCase(Number((await params).id));
  if (!c) notFound();
  const hearings = getHearings(c.id);
  const events = getEvents(c.id);
  const now = nowLocal();
  const appealDays = c.appeal_deadline ? daysUntil(c.appeal_deadline) : null;

  const info: [string, React.ReactNode][] = [
    ["Sud", c.court],
    ["Hudud", c.region],
    ["Ish turi", labelOf(CATEGORIES, c.category)],
    ["Ishtirok roli", labelOf(ROLES, c.role)],
    ["Da'vogar / arizachi", c.plaintiff || "—"],
    ["Javobgar", c.defendant || "—"],
    ["Da'vo summasi", fmtMoney(c.claim_amount)],
    ["Sudya", c.judge || "—"],
    ["Mas'ul xodim", c.responsible || "—"],
    ["Ariza sanasi", fmtDate(c.filed_at)],
    ["Natija", labelOf(OUTCOMES, c.outcome)],
    ["Qaror sanasi", fmtDate(c.decision_date)],
    ["Shikoyat muddati", c.appeal_deadline ? (
      <>
        {fmtDate(c.appeal_deadline)}{" "}
        {appealDays != null && appealDays >= 0 && appealDays <= 10 && (
          <span className="badge s-toxtatilgan">{appealDays === 0 ? "bugun" : `${appealDays} kun qoldi`}</span>
        )}
        {appealDays != null && appealDays < 0 && <span className="muted">(o'tgan)</span>}
      </>
    ) : "—"],
  ];

  return (
    <>
      <div className="page-head">
        <div>
          <Link href="/ishlar" className="muted small">← Ishlar</Link>
          <h1>{c.case_number} <StatusBadge status={c.status} /></h1>
        </div>
        <div className="actions">
          <Link href={`/ishlar/${c.id}/tahrirlash`} className="btn">Tahrirlash</Link>
          <form action={deleteCaseAction}>
            <input type="hidden" name="id" value={c.id} />
            <ConfirmButton message="Ish va unga tegishli barcha majlislar o'chirilsinmi?">O'chirish</ConfirmButton>
          </form>
        </div>
      </div>

      <div className="cols two">
        <section className="card">
          <h2>Ma'lumotlar</h2>
          <dl className="info">
            {info.map(([k, val]) => (
              <div key={k}><dt>{k}</dt><dd>{val}</dd></div>
            ))}
          </dl>
          {c.subject && (<><h3>Nizo predmeti</h3><p className="pre">{c.subject}</p></>)}
          {c.notes && (<><h3>Izoh</h3><p className="pre">{c.notes}</p></>)}
        </section>

        <div>
          <section className="card">
            <h2>Sud majlislari</h2>
            <form action={addHearingAction} className="inline-form">
              <input type="hidden" name="case_id" value={c.id} />
              <input type="datetime-local" name="scheduled_at" required />
              <input name="location" placeholder="Zal / manzil" />
              <input name="notes" placeholder="Izoh" />
              <button className="btn primary" type="submit">Majlis qo'shish</button>
            </form>

            {hearings.length === 0 ? (
              <p className="muted">Majlislar hali tayinlanmagan.</p>
            ) : (
              <ul className="hearings">
                {hearings.map((h) => {
                  const past = h.scheduled_at < now;
                  return (
                    <li key={h.id} className={!h.result && past ? "overdue" : undefined}>
                      <div className="hearing-head">
                        <b>{fmtDate(h.scheduled_at)}</b>
                        {h.location && <span className="muted"> · {h.location}</span>}
                        <form action={deleteHearingAction} className="right">
                          <input type="hidden" name="id" value={h.id} />
                          <ConfirmButton message="Majlis o'chirilsinmi?" className="link-btn">o'chirish</ConfirmButton>
                        </form>
                      </div>
                      {h.notes && <div className="muted small">{h.notes}</div>}
                      {h.result ? (
                        <div className="result">Natija: {h.result}</div>
                      ) : past ? (
                        <form action={setHearingResultAction} className="inline-form">
                          <input type="hidden" name="id" value={h.id} />
                          <input name="result" placeholder="Majlis natijasini kiriting" required />
                          <button className="btn small" type="submit">Saqlash</button>
                        </form>
                      ) : (
                        <div className="muted small">Kutilmoqda</div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          <section className="card">
            <h2>Tarix</h2>
            <ul className="timeline">
              {events.map((e) => (
                <li key={e.id}><span className="muted small">{fmtDate(e.created_at)}</span> {e.text}</li>
              ))}
            </ul>
          </section>
        </div>
      </div>
    </>
  );
}
