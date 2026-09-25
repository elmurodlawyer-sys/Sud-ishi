const pad = (n: number) => String(n).padStart(2, "0");

/** "YYYY-MM-DD" yoki "YYYY-MM-DDTHH:MM" -> "DD.MM.YYYY[ HH:MM]" */
export function fmtDate(value: string | null | undefined): string {
  if (!value) return "—";
  const [d, t] = value.replace(" ", "T").split("T");
  const [y, m, day] = d.split("-");
  if (!y || !m || !day) return value;
  return `${day}.${m}.${y}${t ? " " + t.slice(0, 5) : ""}`;
}

export function fmtMoney(value: number | null | undefined): string {
  if (value == null) return "—";
  return new Intl.NumberFormat("uz-UZ", { maximumFractionDigits: 2 }).format(value) + " so'm";
}

/** Mahalliy vaqt bo'yicha "YYYY-MM-DD" */
export function today(): string {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Mahalliy vaqt bo'yicha "YYYY-MM-DDTHH:MM" */
export function nowLocal(): string {
  const d = new Date();
  return `${today()}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function addDays(date: string, days: number): string {
  const d = new Date(date + "T00:00:00");
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Bugundan sanagacha qolgan kunlar (manfiy — o'tib ketgan). */
export function daysUntil(date: string): number {
  const a = new Date(today() + "T00:00:00").getTime();
  const b = new Date(date.slice(0, 10) + "T00:00:00").getTime();
  return Math.round((b - a) / 86_400_000);
}
