import mimetypes
import os
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.audit import log_action
from notifications.models import NotificationKind
from notifications.services import notify_case
from reports.exports import export_response

from . import services
from .filters import filtered_cases
from .forms import CaseForm, DeadlineForm, DocumentForm, HearingForm, ReasonForm, StageCloseForm, StageForm
from .models import Case, CaseDocument, CaseStage, Deadline, EventType, Hearing, HearingStatus, ReviewStatus
from .permissions import can_edit, get_case, require

CASE_EXPORT_HEADERS = [
    "Tizim raqami", "Ish raqami", "Tashkilot", "Hudud", "Maqomi", "Da’vogar", "Javobgar", "Sud", "Instansiya",
    "Ish turi", "Holati", "Navbatdagi majlis", "Mas’ul xodim", "Da’vo summasi", "Natija", "Ro‘yxatga olingan",
]


def _case_rows(qs):
    rows = []
    for c in qs.select_related(
        "organization", "organization__region", "court", "instance", "category", "status", "outcome", "responsible"
    ):
        rows.append([
            c.reg_number, c.case_number, c.organization.full_name, c.organization.region or "", c.get_role_display(),
            c.plaintiffs, c.defendants, c.court or "", c.instance or "", c.category or "", c.status,
            c.next_hearing_at, c.responsible or "", c.claim_amount, c.outcome or "", c.created_at,
        ])
    return rows


@login_required
def case_list(request):
    form, qs = filtered_cases(request)
    fmt = request.GET.get("export")
    if fmt in ("xlsx", "pdf", "print"):
        rows = _case_rows(qs)
        return export_response(
            request, fmt, "Sud ishlari ro‘yxati", CASE_EXPORT_HEADERS, rows, form.active_filters(), filename="sud-ishlari"
        )
    qs = qs.select_related("organization", "court", "instance", "status", "responsible", "category")
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    advanced_keys = set(form.fields) - {"q", "state", "role", "status", "sort"}
    return render(request, "cases/list.html", {
        "form": form,
        "page": page,
        "total": page.paginator.count,
        "querystring": params.urlencode(),
        "show_advanced": any(request.GET.get(k) for k in advanced_keys),
        "active_filters": form.active_filters(),
    })


@login_required
def case_create(request):
    require(request.user.can_edit_cases)
    if request.method == "POST":
        form = CaseForm(request.POST, user=request.user)
        if form.is_valid():
            case = form.save(commit=False)
            services.register_case(case, request.user)
            log_action(request, "ish_yaratildi", case, f"{case.reg_number} {case.case_number}")
            request._audit_logged = True
            messages.success(request, f"Sud ishi ro‘yxatga olindi: {case.reg_number}")
            return redirect(case)
    else:
        initial = {}
        if request.user.organization_id and not request.user.is_central:
            initial["organization"] = request.user.organization_id
            initial["responsible"] = request.user.pk
        form = CaseForm(initial=initial, user=request.user)
    return render(request, "cases/form.html", {"form": form, "title": "Yangi sud ishini ro‘yxatga olish"})


@login_required
def case_detail(request, pk):
    case = get_case(request, pk)
    editable = can_edit(request.user, case)
    return render(request, "cases/detail.html", {
        "case": case,
        "editable": editable,
        "stages": case.stages.select_related("instance", "court", "result"),
        "hearings": case.hearings.select_related("responsible", "result").order_by("-scheduled_at"),
        "deadlines": case.deadlines.select_related("responsible", "deadline_type").order_by("is_done", "due_date"),
        "documents": case.documents.select_related("doc_type", "uploaded_by"),
        "events": case.events.select_related("user")[:200],
        "warnings": case.control_warnings(),
        "external_records": case.external_records.select_related("source"),
        "tab": request.GET.get("tab", "umumiy"),
        "reason_form": ReasonForm(),
        "today": timezone.localdate(),
    })


@login_required
def case_edit(request, pk):
    case = get_case(request, pk, edit=True)
    old = services.snapshot(case)
    if request.method == "POST":
        form = CaseForm(request.POST, instance=case, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                case = form.save(commit=False)
                if not case.status_id:
                    case.status = services.status_by_code("yangi")
                case.save()
                changes = services.apply_changes(case, request.user, old, form.cleaned_data.get("change_comment", ""))
                if changes and case.review_status == ReviewStatus.APPROVED and not request.user.is_legal:
                    case.review_status = ReviewStatus.DRAFT
                    case.save(update_fields=["review_status"])
            messages.success(request, "O‘zgarishlar saqlandi." if changes else "O‘zgarish kiritilmadi.")
            return redirect(case)
    else:
        form = CaseForm(instance=case, user=request.user)
    return render(request, "cases/form.html", {"form": form, "case": case, "title": f"Tahrirlash: {case.case_number}"})


# --- Bosqichlar -----------------------------------------------------------------

@login_required
def stage_add(request, pk):
    case = get_case(request, pk, edit=True)
    if request.method == "POST":
        form = StageForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                stage = form.save(commit=False)
                stage.case = case
                stage.created_by = request.user
                prev = case.stages.filter(ended_on__isnull=True).order_by("-started_on", "-id").first()
                if prev:
                    prev.ended_on = stage.started_on
                    prev.save(update_fields=["ended_on"])
                stage.save()
                old = services.snapshot(case)
                case.instance = stage.instance
                code = services.INSTANCE_TO_STATUS.get(stage.instance.code)
                if code:
                    case.status = services.status_by_code(code)
                case.save()
                services.apply_changes(case, request.user, old, stage.note)
            messages.success(request, "Yangi sud bosqichi qo‘shildi.")
            return redirect(f"{case.get_absolute_url()}?tab=bosqichlar")
    else:
        form = StageForm(initial={"started_on": timezone.localdate(), "court": case.court_id})
    return render(request, "cases/subform.html", {"form": form, "case": case, "title": "Yangi sud bosqichi (instansiya)"})


@login_required
def stage_close(request, pk, stage_id):
    case = get_case(request, pk, edit=True)
    stage = get_object_or_404(CaseStage, pk=stage_id, case=case)
    if request.method == "POST":
        form = StageCloseForm(request.POST, instance=stage)
        if form.is_valid():
            form.save()
            services.record_event(
                case, request.user, EventType.STAGE, f"Bosqich yakunlandi: {stage.instance}, natija: {stage.result or '—'}",
                comment=stage.note,
            )
            messages.success(request, "Bosqich yakunlandi.")
            return redirect(f"{case.get_absolute_url()}?tab=bosqichlar")
    else:
        form = StageCloseForm(instance=stage, initial={"ended_on": timezone.localdate()})
    return render(request, "cases/subform.html", {"form": form, "case": case, "title": f"Bosqichni yakunlash: {stage.instance}"})


# --- Sud majlislari -------------------------------------------------------------

@login_required
def hearing_edit(request, pk, hearing_id=None):
    case = get_case(request, pk, edit=True)
    hearing = get_object_or_404(Hearing, pk=hearing_id, case=case) if hearing_id else None
    old_at = hearing.scheduled_at if hearing else None
    if request.method == "POST":
        form = HearingForm(request.POST, instance=hearing, user=request.user)
        if form.is_valid():
            with transaction.atomic():
                h = form.save(commit=False)
                h.case = case
                if hearing is None:
                    h.created_by = request.user
                    h.stage = case.stages.filter(ended_on__isnull=True).last()
                h.save()
                services.after_hearing_change(case, h, request.user, created=hearing is None, old_scheduled_at=old_at)
                nxt = form.cleaned_data.get("next_hearing_at")
                if nxt:
                    new = Hearing.objects.create(
                        case=case, stage=h.stage, scheduled_at=nxt, location=h.location, responsible=h.responsible,
                        created_by=request.user,
                    )
                    services.after_hearing_change(case, new, request.user, created=True)
            messages.success(request, "Sud majlisi ma’lumotlari saqlandi.")
            return redirect(f"{case.get_absolute_url()}?tab=majlislar")
    else:
        initial = {} if hearing else {"responsible": case.responsible_id}
        form = HearingForm(instance=hearing, initial=initial, user=request.user)
    title = "Sud majlisi natijasini / ma’lumotlarini kiritish" if hearing else "Sud majlisini belgilash"
    return render(request, "cases/subform.html", {"form": form, "case": case, "title": title})


# --- Muddatlar ------------------------------------------------------------------

@login_required
def deadline_edit(request, pk, deadline_id=None):
    case = get_case(request, pk, edit=True)
    deadline = get_object_or_404(Deadline, pk=deadline_id, case=case) if deadline_id else None
    if request.method == "POST":
        form = DeadlineForm(request.POST, instance=deadline, user=request.user)
        if form.is_valid():
            d = form.save(commit=False)
            d.case = case
            if deadline is None:
                d.created_by = request.user
            d.save()
            services.record_event(
                case, request.user, EventType.DEADLINE,
                f"{'Nazorat muddati belgilandi' if deadline is None else 'Nazorat muddati o‘zgartirildi'}: {d.title} — {d.due_date:%d.%m.%Y}",
            )
            messages.success(request, "Muddat saqlandi.")
            return redirect(f"{case.get_absolute_url()}?tab=muddatlar")
    else:
        form = DeadlineForm(instance=deadline, initial={} if deadline else {"responsible": case.responsible_id}, user=request.user)
    return render(request, "cases/subform.html", {"form": form, "case": case, "title": "Nazorat muddati"})


@login_required
@require_POST
def deadline_done(request, pk, deadline_id):
    case = get_case(request, pk, edit=True)
    d = get_object_or_404(Deadline, pk=deadline_id, case=case)
    d.is_done = not d.is_done
    d.done_at = timezone.now() if d.is_done else None
    d.done_by = request.user if d.is_done else None
    d.save()
    services.record_event(
        case, request.user, EventType.DEADLINE,
        f"Muddat {'bajarildi' if d.is_done else 'qayta ochildi'}: {d.title}",
    )
    return redirect(f"{case.get_absolute_url()}?tab=muddatlar")


# --- Hujjatlar ------------------------------------------------------------------

@login_required
def document_upload(request, pk):
    case = get_case(request, pk, edit=True)
    if request.method == "POST":
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.case = case
            doc.uploaded_by = request.user
            doc.original_name = os.path.basename(request.FILES["file"].name)[:255]
            doc.size = request.FILES["file"].size
            doc.save()
            services.record_event(
                case, request.user, EventType.DOCUMENT, f"Hujjat biriktirildi: {doc.doc_type} — {doc.title or doc.original_name}"
            )
            notify_case(
                case, NotificationKind.NEW_INFO, f"Yangi hujjat: {case.case_number}",
                f"{doc.doc_type}: {doc.title or doc.original_name}", include_legal=True, exclude=request.user,
            )
            messages.success(request, "Hujjat yuklandi.")
            return redirect(f"{case.get_absolute_url()}?tab=hujjatlar")
    else:
        form = DocumentForm()
    return render(request, "cases/subform.html", {"form": form, "case": case, "title": "Hujjat biriktirish", "multipart": True})


@login_required
def document_download(request, pk, doc_id):
    case = get_case(request, pk)
    doc = get_object_or_404(CaseDocument, pk=doc_id, case=case)
    path = os.path.join(settings.MEDIA_ROOT, doc.file.name)
    if not os.path.exists(path):
        raise Http404("Fayl topilmadi.")
    log_action(request, "hujjat_yuklab_olindi", doc, f"{case.reg_number}: {doc.original_name}")
    content_type = mimetypes.guess_type(doc.original_name or path)[0] or "application/octet-stream"
    inline = request.GET.get("inline") == "1" and content_type in ("application/pdf", "image/png", "image/jpeg")
    return FileResponse(open(path, "rb"), content_type=content_type, as_attachment=not inline, filename=doc.original_name or os.path.basename(path))


# --- Tasdiqlash, bekor qilish, arxiv ------------------------------------------

@login_required
@require_POST
def review_action(request, pk, action):
    case = get_case(request, pk)
    form = ReasonForm(request.POST, required=action in ("return", "cancel", "archive", "restore"))
    if not form.is_valid():
        messages.error(request, "Sabab (izoh) kiritilishi shart.")
        return redirect(case)
    reason = form.cleaned_data["reason"]
    if action == "submit":
        require(can_edit(request.user, case))
        services.submit_for_review(case, request.user)
        messages.success(request, "Ma’lumotlar Yuridik bo‘lim tasdig‘iga yuborildi.")
    elif action == "approve":
        require(request.user.is_legal)
        services.approve(case, request.user, reason)
        messages.success(request, "Ma’lumotlar tasdiqlandi.")
    elif action == "return":
        require(request.user.is_legal)
        services.return_for_clarification(case, request.user, reason)
        messages.success(request, "Aniqlashtirish uchun qaytarildi.")
    elif action == "cancel":
        require(request.user.is_legal and not case.is_cancelled)
        services.cancel(case, request.user, reason)
        messages.warning(request, "Kartochka bekor qilindi. U statistikaga kirmaydi, lekin tizimda saqlanadi.")
    elif action == "restore":
        require(request.user.is_legal and case.is_cancelled)
        try:
            services.restore(case, request.user, reason)
            messages.success(request, "Kartochka qayta tiklandi.")
        except ValueError as exc:
            messages.error(request, str(exc))
    elif action == "archive":
        require(request.user.is_legal and not case.is_cancelled)
        services.archive(case, request.user, reason)
        messages.success(request, "Ish arxivga olindi.")
    else:
        raise Http404
    log_action(request, f"ish_{action}", case, reason)
    request._audit_logged = True
    return redirect(case)


# --- Sud majlislari kalendari va nazorat ro'yxati ----------------------------

@login_required
def hearing_list(request):
    today = timezone.localdate()
    try:
        date_from = datetime.strptime(request.GET.get("from", ""), "%Y-%m-%d").date()
    except ValueError:
        date_from = today
    try:
        date_to = datetime.strptime(request.GET.get("to", ""), "%Y-%m-%d").date()
    except ValueError:
        date_to = today + timedelta(days=14)
    qs = Hearing.objects.filter(
        case__is_cancelled=False, scheduled_at__date__gte=date_from, scheduled_at__date__lte=date_to
    ).select_related("case", "case__organization", "case__court", "responsible", "result")
    scope = request.user.scope_organization_ids()
    if scope is not None:
        qs = qs.filter(case__organization_id__in=scope)
    if request.GET.get("mine"):
        qs = qs.filter(Q(responsible=request.user) | Q(case__responsible=request.user))
    qs = qs.order_by("scheduled_at")
    fmt = request.GET.get("export")
    if fmt in ("xlsx", "pdf", "print"):
        rows = [[timezone.localtime(h.scheduled_at), h.case.case_number, h.case.organization, h.case.get_role_display(),
                 h.case.court or "", h.location, h.get_status_display(), h.responsible or h.case.responsible or ""] for h in qs]
        return export_response(
            request, fmt, f"Sud majlislari: {date_from:%d.%m.%Y} — {date_to:%d.%m.%Y}",
            ["Sana va vaqt", "Ish raqami", "Tashkilot", "Maqomi", "Sud", "Zal", "Holati", "Mas’ul"], rows, filename="sud-majlislari",
        )
    days = {}
    for h in qs:
        days.setdefault(timezone.localtime(h.scheduled_at).date(), []).append(h)
    return render(request, "cases/hearings.html", {
        "days": sorted(days.items()), "date_from": date_from, "date_to": date_to, "today": today, "count": qs.count(),
        "HearingStatus": HearingStatus,
    })


@login_required
def control_list(request):
    scope = request.user.scope_organization_ids()
    deadlines = Deadline.objects.pending().select_related("case", "case__organization", "responsible", "deadline_type")
    cases = Case.objects.valid().visible_to(request.user)
    if scope is not None:
        deadlines = deadlines.filter(case__organization_id__in=scope)
    return render(request, "cases/control.html", {
        "overdue": deadlines.overdue().order_by("due_date"),
        "upcoming": deadlines.upcoming().order_by("due_date"),
        "stale": cases.stale().select_related("organization", "status").order_by("last_activity_at")[:100],
        "no_outcome": cases.filter(status__code="yakunlangan", outcome__isnull=True).select_related("organization")[:100],
        "pending_review": cases.filter(review_status=ReviewStatus.PENDING).select_related("organization")[:100],
        "returned": cases.filter(review_status=ReviewStatus.RETURNED).select_related("organization")[:100],
        "today": timezone.localdate(),
        "stale_days": settings.STALE_CASE_DAYS,
    })
