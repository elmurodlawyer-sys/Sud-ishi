"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";
import {
  addHearing, createCase, deleteCase, deleteHearing, getCase, setHearingResult, updateCase,
  type CaseInput,
} from "@/lib/cases";
import { CATEGORIES, OUTCOMES, REGIONS, ROLES, STATUSES, labelOf } from "@/lib/constants";

export type FormState = { errors?: Record<string, string>; message?: string };

const str = (fd: FormData, key: string) => String(fd.get(key) ?? "").trim();
const dateOrNull = (fd: FormData, key: string) => {
  const v = str(fd, key);
  return /^\d{4}-\d{2}-\d{2}$/.test(v) ? v : null;
};

function parseCase(fd: FormData): { input: CaseInput; errors: Record<string, string> } {
  const errors: Record<string, string> = {};
  const amountRaw = str(fd, "claim_amount").replace(/[\s,]/g, "");
  const claim_amount = amountRaw ? Number(amountRaw) : null;
  if (claim_amount != null && (!Number.isFinite(claim_amount) || claim_amount < 0)) {
    errors.claim_amount = "Summa noto'g'ri kiritilgan";
  }
  const input: CaseInput = {
    case_number: str(fd, "case_number"),
    court: str(fd, "court"),
    category: str(fd, "category"),
    role: str(fd, "role"),
    region: str(fd, "region"),
    plaintiff: str(fd, "plaintiff"),
    defendant: str(fd, "defendant"),
    subject: str(fd, "subject"),
    claim_amount: errors.claim_amount ? null : claim_amount,
    judge: str(fd, "judge"),
    responsible: str(fd, "responsible"),
    status: str(fd, "status") || "yangi",
    outcome: str(fd, "outcome"),
    filed_at: dateOrNull(fd, "filed_at"),
    decision_date: dateOrNull(fd, "decision_date"),
    appeal_deadline: dateOrNull(fd, "appeal_deadline"),
    notes: str(fd, "notes"),
  };
  if (!input.case_number) errors.case_number = "Ish raqamini kiriting";
  if (!input.court) errors.court = "Sud nomini kiriting";
  if (!CATEGORIES.some((o) => o.value === input.category)) errors.category = "Ish turini tanlang";
  if (!ROLES.some((o) => o.value === input.role)) errors.role = "Ishtirok rolini tanlang";
  if (!REGIONS.includes(input.region)) errors.region = "Hududni tanlang";
  if (!STATUSES.some((o) => o.value === input.status)) errors.status = "Holat noto'g'ri";
  if (!OUTCOMES.some((o) => o.value === input.outcome)) errors.outcome = "Natija noto'g'ri";
  if (input.decision_date && input.filed_at && input.decision_date < input.filed_at) {
    errors.decision_date = "Qaror sanasi ariza sanasidan oldin bo'lishi mumkin emas";
  }
  return { input, errors };
}

export async function saveCase(_prev: FormState, fd: FormData): Promise<FormState> {
  const { input, errors } = parseCase(fd);
  if (Object.keys(errors).length) return { errors, message: "Formadagi xatolarni tuzating" };

  const id = Number(fd.get("id")) || null;
  let caseId: number;
  if (id) {
    const old = getCase(id);
    if (!old) return { message: "Ish topilmadi" };
    const changes: string[] = [];
    if (old.status !== input.status) {
      changes.push(`Holat: ${labelOf(STATUSES, old.status)} → ${labelOf(STATUSES, input.status)}`);
    }
    if (old.outcome !== input.outcome) {
      changes.push(`Natija: ${labelOf(OUTCOMES, old.outcome)} → ${labelOf(OUTCOMES, input.outcome)}`);
    }
    if ((old.appeal_deadline ?? "") !== (input.appeal_deadline ?? "")) {
      changes.push(`Shikoyat muddati: ${input.appeal_deadline ?? "olib tashlandi"}`);
    }
    if (!changes.length) changes.push("Ish ma'lumotlari tahrirlandi");
    updateCase(id, input, changes);
    caseId = id;
  } else {
    caseId = createCase(input);
  }
  revalidatePath("/", "layout");
  redirect(`/ishlar/${caseId}`);
}

export async function deleteCaseAction(fd: FormData) {
  deleteCase(Number(fd.get("id")));
  revalidatePath("/", "layout");
  redirect("/ishlar");
}

export async function addHearingAction(fd: FormData) {
  const caseId = Number(fd.get("case_id"));
  const scheduled_at = str(fd, "scheduled_at");
  if (!caseId || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(scheduled_at)) return;
  addHearing(caseId, { scheduled_at, location: str(fd, "location"), notes: str(fd, "notes") });
  revalidatePath("/", "layout");
}

export async function setHearingResultAction(fd: FormData) {
  const result = str(fd, "result");
  if (!result) return;
  setHearingResult(Number(fd.get("id")), result);
  revalidatePath("/", "layout");
}

export async function deleteHearingAction(fd: FormData) {
  deleteHearing(Number(fd.get("id")));
  revalidatePath("/", "layout");
}
