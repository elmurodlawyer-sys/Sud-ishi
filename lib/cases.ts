import "server-only";
import { getDb } from "./db";
import { ACTIVE_STATUSES } from "./constants";
import { addDays, nowLocal, today } from "./format";

export type Case = {
  id: number;
  case_number: string;
  court: string;
  category: string;
  role: string;
  region: string;
  plaintiff: string;
  defendant: string;
  subject: string;
  claim_amount: number | null;
  judge: string;
  responsible: string;
  status: string;
  outcome: string;
  filed_at: string | null;
  decision_date: string | null;
  appeal_deadline: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
};

export type CaseRow = Case & { next_hearing: string | null };

export type Hearing = {
  id: number;
  case_id: number;
  scheduled_at: string;
  location: string;
  result: string | null;
  notes: string;
};

export type HearingRow = Hearing & {
  case_number: string;
  court: string;
  plaintiff: string;
  defendant: string;
  responsible: string;
};

export type CaseEvent = { id: number; case_id: number; created_at: string; text: string };

export type CaseInput = Omit<Case, "id" | "created_at" | "updated_at">;

export type CaseFilters = {
  q?: string;
  status?: string;
  category?: string;
  region?: string;
  role?: string;
  sort?: string;
};

const NEXT_HEARING_SQL = `(SELECT MIN(h.scheduled_at) FROM hearings h
  WHERE h.case_id = c.id AND h.result IS NULL AND h.scheduled_at >= @now)`;

const SORTS: Record<string, string> = {
  yangilangan: "c.updated_at DESC",
  majlis: "next_hearing IS NULL, next_hearing ASC",
  raqam: "c.case_number COLLATE NOCASE ASC",
  summa: "c.claim_amount IS NULL, c.claim_amount DESC",
};

export function listCases(f: CaseFilters = {}): CaseRow[] {
  const where: string[] = [];
  const params: Record<string, unknown> = { now: nowLocal() };
  if (f.q) {
    where.push(`(c.case_number LIKE @q OR c.plaintiff LIKE @q OR c.defendant LIKE @q
      OR c.subject LIKE @q OR c.court LIKE @q OR c.responsible LIKE @q)`);
    params.q = `%${f.q}%`;
  }
  if (f.status === "faol") {
    where.push(`c.status IN (${ACTIVE_STATUSES.map((s) => `'${s}'`).join(",")})`);
  } else if (f.status) {
    where.push("c.status = @status");
    params.status = f.status;
  }
  for (const key of ["category", "region", "role"] as const) {
    if (f[key]) {
      where.push(`c.${key} = @${key}`);
      params[key] = f[key];
    }
  }
  const order = SORTS[f.sort ?? ""] ?? SORTS.yangilangan;
  const sql = `SELECT c.*, ${NEXT_HEARING_SQL} AS next_hearing FROM cases c
    ${where.length ? "WHERE " + where.join(" AND ") : ""} ORDER BY ${order}`;
  return getDb().prepare(sql).all(params) as CaseRow[];
}

export function getCase(id: number): Case | undefined {
  return getDb().prepare("SELECT * FROM cases WHERE id = ?").get(id) as Case | undefined;
}

export function getHearings(caseId: number): Hearing[] {
  return getDb()
    .prepare("SELECT * FROM hearings WHERE case_id = ? ORDER BY scheduled_at DESC")
    .all(caseId) as Hearing[];
}

export function getEvents(caseId: number): CaseEvent[] {
  return getDb()
    .prepare("SELECT * FROM case_events WHERE case_id = ? ORDER BY id DESC")
    .all(caseId) as CaseEvent[];
}

const CASE_FIELDS: (keyof CaseInput)[] = [
  "case_number", "court", "category", "role", "region", "plaintiff", "defendant", "subject",
  "claim_amount", "judge", "responsible", "status", "outcome", "filed_at", "decision_date",
  "appeal_deadline", "notes",
];

export function addEvent(caseId: number, text: string) {
  getDb().prepare("INSERT INTO case_events (case_id, text) VALUES (?, ?)").run(caseId, text);
}

export function createCase(input: CaseInput): number {
  const db = getDb();
  const cols = CASE_FIELDS.join(", ");
  const vals = CASE_FIELDS.map((k) => "@" + k).join(", ");
  return db.transaction(() => {
    const id = Number(db.prepare(`INSERT INTO cases (${cols}) VALUES (${vals})`).run(input).lastInsertRowid);
    addEvent(id, "Ish ro'yxatga olindi");
    return id;
  })();
}

export function updateCase(id: number, input: CaseInput, changes: string[]) {
  const db = getDb();
  const set = CASE_FIELDS.map((k) => `${k} = @${k}`).join(", ");
  db.transaction(() => {
    db.prepare(`UPDATE cases SET ${set}, updated_at = datetime('now', 'localtime') WHERE id = @id`).run({ ...input, id });
    for (const c of changes) addEvent(id, c);
  })();
}

export function deleteCase(id: number) {
  getDb().prepare("DELETE FROM cases WHERE id = ?").run(id);
}

function touch(caseId: number) {
  getDb().prepare("UPDATE cases SET updated_at = datetime('now', 'localtime') WHERE id = ?").run(caseId);
}

export function addHearing(caseId: number, h: { scheduled_at: string; location: string; notes: string }) {
  const db = getDb();
  db.transaction(() => {
    db.prepare("INSERT INTO hearings (case_id, scheduled_at, location, notes) VALUES (?, ?, ?, ?)")
      .run(caseId, h.scheduled_at, h.location, h.notes);
    // Birinchi majlis tayinlanganda "Yangi" ish avtomatik "Ko'rib chiqilmoqda"ga o'tadi.
    const moved = db.prepare("UPDATE cases SET status = 'korilmoqda' WHERE id = ? AND status = 'yangi'").run(caseId);
    addEvent(caseId, `Sud majlisi tayinlandi: ${h.scheduled_at.replace("T", " ")}`);
    if (moved.changes) addEvent(caseId, "Holat: Yangi → Ko'rib chiqilmoqda");
    touch(caseId);
  })();
}

export function setHearingResult(hearingId: number, result: string) {
  const db = getDb();
  const h = db.prepare("SELECT * FROM hearings WHERE id = ?").get(hearingId) as Hearing | undefined;
  if (!h) return;
  db.transaction(() => {
    db.prepare("UPDATE hearings SET result = ? WHERE id = ?").run(result, hearingId);
    addEvent(h.case_id, `Majlis natijasi (${h.scheduled_at.replace("T", " ")}): ${result}`);
    touch(h.case_id);
  })();
  return h.case_id;
}

export function deleteHearing(hearingId: number) {
  const db = getDb();
  const h = db.prepare("SELECT * FROM hearings WHERE id = ?").get(hearingId) as Hearing | undefined;
  if (!h) return;
  db.transaction(() => {
    db.prepare("DELETE FROM hearings WHERE id = ?").run(hearingId);
    addEvent(h.case_id, `Majlis o'chirildi: ${h.scheduled_at.replace("T", " ")}`);
    touch(h.case_id);
  })();
  return h.case_id;
}

const HEARING_JOIN = `SELECT h.*, c.case_number, c.court, c.plaintiff, c.defendant, c.responsible
  FROM hearings h JOIN cases c ON c.id = h.case_id`;

export function upcomingHearings(days: number | null): HearingRow[] {
  const params: Record<string, unknown> = { now: nowLocal(), until: days == null ? null : addDays(today(), days + 1) };
  return getDb()
    .prepare(`${HEARING_JOIN} WHERE h.result IS NULL AND h.scheduled_at >= @now
      AND (@until IS NULL OR h.scheduled_at < @until) ORDER BY h.scheduled_at`)
    .all(params) as HearingRow[];
}

/** O'tib ketgan, lekin natijasi kiritilmagan majlislar. */
export function overdueHearings(): HearingRow[] {
  return getDb()
    .prepare(`${HEARING_JOIN} WHERE h.result IS NULL AND h.scheduled_at < @now ORDER BY h.scheduled_at`)
    .all({ now: nowLocal() }) as HearingRow[];
}

export function pastHearings(limit = 50): HearingRow[] {
  return getDb()
    .prepare(`${HEARING_JOIN} WHERE h.result IS NOT NULL ORDER BY h.scheduled_at DESC LIMIT ?`)
    .all(limit) as HearingRow[];
}

/** Shikoyat muddati yaqinlashayotgan (yoki bugun tugaydigan) ishlar. */
export function appealDeadlines(days: number): Case[] {
  return getDb()
    .prepare(`SELECT * FROM cases WHERE appeal_deadline IS NOT NULL
      AND appeal_deadline >= @from AND appeal_deadline <= @to
      AND status IN ('hal_qilingan') ORDER BY appeal_deadline`)
    .all({ from: today(), to: addDays(today(), days) }) as Case[];
}

export type Stats = {
  total: number;
  active: number;
  claimActive: number;
  byStatus: Record<string, number>;
  byCategory: Record<string, number>;
  byOutcome: Record<string, number>;
  byRegion: { region: string; n: number }[];
};

export function getStats(): Stats {
  const db = getDb();
  const group = (col: string) =>
    Object.fromEntries(
      (db.prepare(`SELECT ${col} AS k, COUNT(*) AS n FROM cases GROUP BY ${col}`).all() as { k: string; n: number }[])
        .map((r) => [r.k, r.n]),
    );
  const active = ACTIVE_STATUSES.map((s) => `'${s}'`).join(",");
  const totals = db
    .prepare(`SELECT COUNT(*) AS total,
      SUM(status IN (${active})) AS active,
      COALESCE(SUM(CASE WHEN status IN (${active}) THEN claim_amount END), 0) AS claimActive
      FROM cases`)
    .get() as { total: number; active: number | null; claimActive: number };
  return {
    total: totals.total,
    active: totals.active ?? 0,
    claimActive: totals.claimActive,
    byStatus: group("status"),
    byCategory: group("category"),
    byOutcome: group("outcome"),
    byRegion: db
      .prepare("SELECT region, COUNT(*) AS n FROM cases GROUP BY region ORDER BY n DESC")
      .all() as { region: string; n: number }[],
  };
}
