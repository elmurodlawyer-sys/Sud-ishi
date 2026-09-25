from datetime import timedelta
from urllib.parse import urlencode

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Value
from django.db.models.functions import Coalesce, NullIf, TruncMonth
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.audit import log_action
from cases.filters import CaseFilterForm
from cases.models import AgencyResult, Case, Deadline, Hearing, HearingStatus, ProceduralRole, ReviewStatus

from .analytics import DEFAULT_METRICS, DIMENSIONS, GRANULARITY, METRICS, PERIOD_FIELDS, drilldown_params
from .exports import export_response
from .generation import generate_files, querydict_to_params, run_report
from .models import GeneratedReport, Periodicity, ReportTemplate

MONTHS = ["yan", "fev", "mar", "apr", "may", "iyun", "iyul", "avg", "sen", "okt", "noy", "dek"]


def _cases_url(**params):
    params = {k: v for k, v in params.items() if v not in (None, "")}
    return reverse("cases:list") + ("?" + urlencode(params) if params else "")


def _distribution(qs, id_field, label_field, param, limit=None, choices=None, show_rest=True):
    rows = list(qs.order_by().values(id_field, label_field).annotate(n=Count("id")).order_by("-n"))
    items = []
    for r in rows:
        value = r[id_field]
        label = r[label_field]
        if choices is not None:
            label = choices.get(value, value)
        items.append({
            "label": label or "Ko‘rsatilmagan",
            "value": r["n"],
            "url": _cases_url(**{param: value}) if value not in (None, "") else _cases_url(),
        })
    if limit and len(items) > limit:
        rest = sum(i["value"] for i in items[limit:])
        items = items[:limit] + ([{"label": "Boshqalar", "value": rest, "url": _cases_url()}] if show_rest else [])
    return items


@login_required
def dashboard(request):
    """Rahbariyat va Yuridik bo'lim uchun monitoring paneli (3.9-band)."""
    user = request.user
    base = Case.objects.valid().visible_to(user)
    scope = user.scope_organization_ids()
    today = timezone.localdate()
    now = timezone.now()

    hearings = Hearing.objects.filter(case__is_cancelled=False, status=HearingStatus.SCHEDULED)
    deadlines = Deadline.objects.pending()
    if scope is not None:
        hearings = hearings.filter(case__organization_id__in=scope)
        deadlines = deadlines.filter(case__organization_id__in=scope)

    counts = base.aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status__is_final=False)),
        closed=Count("id", filter=Q(status__is_final=True)),
        plaintiff=Count("id", filter=Q(role=ProceduralRole.PLAINTIFF)),
        defendant=Count("id", filter=Q(role=ProceduralRole.DEFENDANT)),
        third=Count("id", filter=Q(role=ProceduralRole.THIRD_PARTY)),
        pending_review=Count("id", filter=Q(review_status=ReviewStatus.PENDING)),
        new=Count("id", filter=Q(status__code="yangi")),
    )
    counts["hearings_today"] = hearings.filter(scheduled_at__date=today).count()
    counts["hearings_week"] = hearings.filter(scheduled_at__date__gte=today, scheduled_at__date__lte=today + timedelta(days=7)).count()
    counts["deadlines_soon"] = deadlines.upcoming().values("case").distinct().count()
    counts["deadlines_overdue"] = deadlines.overdue().values("case").distinct().count()
    counts["stale"] = base.stale().count()

    kpis = [
        {"label": "Jami sud ishlari", "value": counts["total"], "url": _cases_url(), "icon": "folder2-open", "tone": "primary"},
        {"label": "Jarayondagi ishlar", "value": counts["open"], "url": _cases_url(state="open"), "icon": "hourglass-split", "tone": "info"},
        {"label": "Yakunlangan ishlar", "value": counts["closed"], "url": _cases_url(state="closed"), "icon": "check2-circle", "tone": "success"},
        {"label": "Agentlik tizimi — da’vogar", "value": counts["plaintiff"], "url": _cases_url(role=ProceduralRole.PLAINTIFF), "icon": "person-up", "tone": "secondary"},
        {"label": "Agentlik tizimi — javobgar", "value": counts["defendant"], "url": _cases_url(role=ProceduralRole.DEFENDANT), "icon": "shield-exclamation", "tone": "secondary"},
        {"label": "Agentlik tizimi — uchinchi shaxs", "value": counts["third"], "url": _cases_url(role=ProceduralRole.THIRD_PARTY), "icon": "people", "tone": "secondary"},
        {"label": "Bugungi sud majlislari", "value": counts["hearings_today"], "url": _cases_url(majlis="bugun"), "icon": "calendar-event", "tone": "warning"},
        {"label": "Kelgusi 7 kundagi majlislar", "value": counts["hearings_week"], "url": _cases_url(majlis="hafta"), "icon": "calendar-week", "tone": "warning"},
        {"label": "Muddati yaqinlashayotgan nazoratlar", "value": counts["deadlines_soon"], "url": _cases_url(nazorat="yaqin"), "icon": "alarm", "tone": "warning"},
        {"label": "Muddati o‘tib ketgan nazoratlar", "value": counts["deadlines_overdue"], "url": _cases_url(nazorat="otgan"), "icon": "exclamation-octagon", "tone": "danger"},
        {"label": f"{settings.STALE_CASE_DAYS} kundan ortiq yangilanmagan", "value": counts["stale"], "url": _cases_url(nazorat="yangilanmagan"), "icon": "clock-history", "tone": "danger"},
        {"label": "Yuridik bo‘lim tasdig‘ida", "value": counts["pending_review"], "url": _cases_url(review_status=ReviewStatus.PENDING), "icon": "patch-question", "tone": "info"},
    ]

    start = (today.replace(day=1) - timedelta(days=330)).replace(day=1)
    monthly_raw = {
        (r["m"].year, r["m"].month): r["n"]
        for r in base.filter(created_at__date__gte=start).annotate(m=TruncMonth("created_at")).values("m").annotate(n=Count("id"))
        if r["m"]
    }
    monthly, cursor = [], start
    while cursor <= today:
        nxt = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        monthly.append({
            "label": f"{MONTHS[cursor.month - 1]} {cursor:%y}",
            "value": monthly_raw.get((cursor.year, cursor.month), 0),
            "url": _cases_url(created_from=cursor.isoformat(), created_to=(nxt - timedelta(days=1)).isoformat()),
        })
        cursor = nxt

    charts = {
        "court_type": _distribution(base, "court__court_type_id", "court__court_type__name", "court_type"),
        "category": _distribution(base, "category_id", "category__name", "category", limit=8),
        "region": _distribution(base, "organization__region_id", "organization__region__name", "region"),
        "organization": _distribution(
            base.annotate(org_label=Coalesce(NullIf("organization__short_name", Value("")), "organization__full_name")),
            "organization_id", "org_label", "organization", limit=10, show_rest=False,
        ),
        "status": _distribution(base, "status_id", "status__name", "status"),
        "result": _distribution(base.exclude(agency_result=""), "agency_result", "agency_result", "agency_result", choices=dict(AgencyResult.choices)),
        "monthly": monthly,
    }
    upcoming = hearings.filter(scheduled_at__gte=now - timedelta(hours=2)).select_related(
        "case", "case__organization", "case__court", "responsible"
    ).order_by("scheduled_at")[:10]
    overdue = deadlines.overdue().select_related("case", "case__organization", "responsible").order_by("due_date")[:10]
    return render(request, "reports/dashboard.html", {
        "kpis": kpis, "charts": charts, "upcoming": upcoming, "overdue": overdue, "counts": counts, "today": today,
    })


class ReportOptionsForm(forms.Form):
    dims = forms.MultipleChoiceField(
        label="Kesimlar (1–3 tagacha, tartib bo‘yicha)", choices=[(k, v[0]) for k, v in DIMENSIONS.items()], required=False,
        widget=forms.SelectMultiple(attrs={"class": "form-select", "size": 8}),
    )
    metrics = forms.MultipleChoiceField(
        label="Ko‘rsatkichlar", choices=list(METRICS.items()), required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    granularity = forms.ChoiceField(
        label="Davr birligi", choices=[(k, v[0]) for k, v in GRANULARITY.items()], initial="month", required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    period_field = forms.ChoiceField(
        label="Davr qaysi sana bo‘yicha", choices=list(PERIOD_FIELDS.items()), required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )


PRESETS = [
    ("Tashkilotlar kesimida", ["organization"]),
    ("Tashkilot turlari kesimida", ["org_type"]),
    ("Hududlar kesimida", ["region"]),
    ("Sud turlari kesimida", ["court_type"]),
    ("Sud va instansiya kesimida", ["court", "instance"]),
    ("Ish turlari kesimida", ["category"]),
    ("Protsessual maqom kesimida", ["role"]),
    ("Ish holati kesimida", ["status"]),
    ("Sud bosqichi kesimida", ["instance"]),
    ("Ish natijasi kesimida", ["outcome"]),
    ("Oylik dinamika", ["period"]),
    ("Da’vo summalari kesimida", ["claim_bucket"]),
    ("Hudud × maqom", ["region", "role"]),
    ("Hudud × ish turi", ["region", "category"]),
]


@login_required
def report_builder(request):
    """Kombinatsiyalangan avtomatik hisobot (3.8-band)."""
    params = request.GET.copy()
    if not params.getlist("dims"):
        params.setlist("dims", ["organization"])
    if not params.getlist("metrics"):
        params.setlist("metrics", DEFAULT_METRICS)
    if not params.get("granularity"):
        params["granularity"] = "month"
    options = ReportOptionsForm(params)
    options.is_valid()
    filter_form = CaseFilterForm(params, user=request.user)
    title, headers, rows, totals, keys, filters = run_report(querydict_to_params(params), request.user)

    fmt = request.GET.get("export")
    if fmt in ("xlsx", "pdf", "print"):
        return export_response(request, fmt, title, headers, rows, filters, totals, filename="hisobot")

    dims = [d for d in params.getlist("dims") if d in DIMENSIONS][:3]
    base_filters = {k: v for k, v in querydict_to_params(params).items() if k not in ("dims", "metrics", "granularity", "period_field")}
    table = []
    for row, key in zip(rows, keys):
        drill = {**base_filters, **drilldown_params(dims, key, params.get("granularity", "month"), params.get("period_field", "created_at"))}
        table.append({"cells": row, "dims": row[: len(dims)], "values": row[len(dims):], "url": _cases_url(**drill)})
    query = params.copy()
    query.pop("export", None)
    presets = []
    for label, preset_dims in PRESETS:
        q = request.GET.copy()
        q.setlist("dims", preset_dims)
        q.pop("export", None)
        presets.append({"label": label, "url": "?" + q.urlencode(), "active": preset_dims == dims})
    return render(request, "reports/builder.html", {
        "options": options, "filter_form": filter_form, "title": title, "headers": headers, "table": table, "totals": totals,
        "dim_count": len(dims), "filters": filters, "querystring": query.urlencode(), "presets": presets,
        "periodicity_choices": Periodicity.choices,
        "templates": ReportTemplate.objects.filter(Q(created_by=request.user) | Q(created_by__isnull=True))[:50]
        if not request.user.is_central else ReportTemplate.objects.all()[:50],
    })


@login_required
@require_POST
def report_save(request):
    params = querydict_to_params(request.POST)
    params.pop("name", None)
    params.pop("periodicity", None)
    name = request.POST.get("name", "").strip() or "Hisobot"
    action = request.POST.get("action", "generate")
    if action == "template":
        periodicity = request.POST.get("periodicity", "")
        if periodicity and periodicity not in dict(Periodicity.choices):
            periodicity = ""
        template = ReportTemplate.objects.create(name=name, params=params, periodicity=periodicity, created_by=request.user)
        template.recipients.add(request.user)
        messages.success(request, f"Hisobot shabloni saqlandi: {name}")
    else:
        report = generate_files(name, params, request.user)
        log_action(request, "hisobot_saqlandi", report, name)
        messages.success(request, f"Hisobot shakllantirildi va saqlandi: {report.title}")
    return redirect("reports:generated")


def _can_see_generated(user, report):
    return user.is_central or report.created_by_id == user.pk


@login_required
def generated_list(request):
    qs = GeneratedReport.objects.select_related("created_by", "template")
    if not request.user.is_central:
        qs = qs.filter(created_by=request.user)
    templates = ReportTemplate.objects.all() if request.user.is_central else ReportTemplate.objects.filter(created_by=request.user)
    return render(request, "reports/generated.html", {"reports": qs[:200], "templates": templates})


@login_required
def generated_download(request, pk, kind):
    report = get_object_or_404(GeneratedReport, pk=pk)
    if not _can_see_generated(request.user, report):
        raise PermissionDenied
    rel = report.file_xlsx if kind == "xlsx" else report.file_pdf
    path = (settings.REPORTS_ROOT / rel).resolve()
    if not rel or not str(path).startswith(str(settings.REPORTS_ROOT.resolve())) or not path.exists():
        raise Http404
    log_action(request, "hisobot_yuklab_olindi", report, report.title)
    return FileResponse(open(path, "rb"), as_attachment=True, filename=path.name)


@login_required
@require_POST
def template_action(request, pk, action):
    template = get_object_or_404(ReportTemplate, pk=pk)
    if not (request.user.is_central or template.created_by_id == request.user.pk):
        raise PermissionDenied
    if action == "run":
        scope_user = template.created_by if template.created_by and not template.created_by.is_central else None
        generate_files(template.name, template.params, scope_user or request.user, template=template)
        template.last_generated_at = timezone.now()
        template.save(update_fields=["last_generated_at"])
        messages.success(request, "Hisobot qayta shakllantirildi.")
    elif action == "delete":
        template.delete()
        messages.success(request, "Shablon o‘chirildi (shakllantirilgan hisobotlar saqlanib qoladi).")
    elif action == "open":
        from .generation import params_to_querydict

        return redirect(reverse("reports:builder") + "?" + params_to_querydict(template.params).urlencode())
    return redirect("reports:generated")
