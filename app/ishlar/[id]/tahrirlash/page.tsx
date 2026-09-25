import { notFound } from "next/navigation";
import CaseForm from "@/components/CaseForm";
import { getCase } from "@/lib/cases";

export const dynamic = "force-dynamic";

export default async function EditCasePage({ params }: { params: Promise<{ id: string }> }) {
  const c = getCase(Number((await params).id));
  if (!c) notFound();
  return (
    <>
      <h1>Tahrirlash: {c.case_number}</h1>
      <CaseForm initial={c} />
    </>
  );
}
