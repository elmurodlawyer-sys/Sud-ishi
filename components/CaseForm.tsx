"use client";

import { useActionState } from "react";
import Link from "next/link";
import { saveCase, type FormState } from "@/app/actions";
import { CATEGORIES, OUTCOMES, REGIONS, ROLES, STATUSES } from "@/lib/constants";
import type { Case } from "@/lib/cases";

type Props = { initial?: Case };

export default function CaseForm({ initial }: Props) {
  const [state, action, pending] = useActionState<FormState, FormData>(saveCase, {});
  const e = state.errors ?? {};
  const v = (k: keyof Case) => (initial?.[k] ?? "") as string | number;

  const field = (name: keyof Case, label: string, input: React.ReactNode, wide = false) => (
    <label className={`field${wide ? " wide" : ""}${e[name] ? " invalid" : ""}`}>
      <span>{label}</span>
      {input}
      {e[name] && <small className="error">{e[name]}</small>}
    </label>
  );

  return (
    <form action={action} className="card form">
      {initial && <input type="hidden" name="id" value={initial.id} />}
      {state.message && <p className="alert">{state.message}</p>}

      <fieldset>
        <legend>Asosiy ma'lumotlar</legend>
        <div className="grid">
          {field("case_number", "Ish raqami *", <input name="case_number" defaultValue={v("case_number")} placeholder="4-1001-2601/123" />)}
          {field("court", "Sud *", <input name="court" defaultValue={v("court")} placeholder="Toshkent shahar iqtisodiy sudi" />)}
          {field("category", "Ish turi *",
            <select name="category" defaultValue={v("category") || ""}>
              <option value="" disabled>Tanlang</option>
              {CATEGORIES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>)}
          {field("role", "Ishtirok roli *",
            <select name="role" defaultValue={v("role") || ""}>
              <option value="" disabled>Tanlang</option>
              {ROLES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>)}
          {field("region", "Hudud *",
            <select name="region" defaultValue={v("region") || ""}>
              <option value="" disabled>Tanlang</option>
              {REGIONS.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>)}
          {field("judge", "Sudya", <input name="judge" defaultValue={v("judge")} />)}
          {field("plaintiff", "Da'vogar / arizachi", <input name="plaintiff" defaultValue={v("plaintiff")} />)}
          {field("defendant", "Javobgar", <input name="defendant" defaultValue={v("defendant")} />)}
          {field("subject", "Nizo predmeti", <textarea name="subject" rows={2} defaultValue={v("subject")} />, true)}
          {field("claim_amount", "Da'vo summasi (so'm)",
            <input name="claim_amount" inputMode="decimal" defaultValue={v("claim_amount")} />)}
          {field("responsible", "Mas'ul xodim", <input name="responsible" defaultValue={v("responsible")} />)}
          {field("filed_at", "Ariza berilgan sana", <input type="date" name="filed_at" defaultValue={v("filed_at")} />)}
        </div>
      </fieldset>

      <fieldset>
        <legend>Holat va natija</legend>
        <div className="grid">
          {field("status", "Holat",
            <select name="status" defaultValue={v("status") || "yangi"}>
              {STATUSES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>)}
          {field("outcome", "Natija",
            <select name="outcome" defaultValue={v("outcome")}>
              {OUTCOMES.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>)}
          {field("decision_date", "Qaror sanasi", <input type="date" name="decision_date" defaultValue={v("decision_date")} />)}
          {field("appeal_deadline", "Shikoyat berish muddati", <input type="date" name="appeal_deadline" defaultValue={v("appeal_deadline")} />)}
          {field("notes", "Izoh", <textarea name="notes" rows={3} defaultValue={v("notes")} />, true)}
        </div>
      </fieldset>

      <div className="actions">
        <button type="submit" className="btn primary" disabled={pending}>
          {pending ? "Saqlanmoqda…" : "Saqlash"}
        </button>
        <Link href={initial ? `/ishlar/${initial.id}` : "/ishlar"} className="btn">Bekor qilish</Link>
      </div>
    </form>
  );
}
