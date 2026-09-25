"""Hisobotlarni fayl ko'rinishida shakllantirish va saqlash (7-bo'lim: belgilangan davrda avtomatik)."""
from datetime import timedelta

from django.conf import settings
from django.http import QueryDict
from django.utils import timezone
from django.utils.text import slugify

from cases.filters import CaseFilterForm, apply_filters
from cases.models import Case

from .analytics import DIMENSIONS, build_report
from .exports import build_pdf, build_xlsx
from .models import GeneratedReport, Periodicity


def params_to_querydict(params):
    qd = QueryDict(mutable=True)
    for key, value in (params or {}).items():
        if isinstance(value, list):
            qd.setlist(key, [str(v) for v in value])
        elif value not in (None, ""):
            qd[key] = str(value)
    return qd


def querydict_to_params(qd):
    return {k: (qd.getlist(k) if len(qd.getlist(k)) > 1 or k in ("dims", "metrics") else qd.get(k)) for k in qd.keys()
            if k not in ("export", "csrfmiddlewaretoken", "page")}


def run_report(params, user=None):
    qd = params_to_querydict(params)
    form = CaseFilterForm(qd, user=user)
    qs = Case.objects.all()
    if user is not None:
        qs = qs.visible_to(user)
    qs = apply_filters(qs, form.cleaned_data if form.is_valid() else {})
    dims = qd.getlist("dims") or ["organization"]
    headers, rows, totals, keys = build_report(
        qs, dims, qd.getlist("metrics") or None, qd.get("granularity", "month"), qd.get("period_field", "created_at")
    )
    title = "Sud ishlari hisoboti: " + ", ".join(DIMENSIONS[d][0].lower() for d in dims if d in DIMENSIONS) + " kesimida"
    return title, headers, rows, totals, keys, form.active_filters()


def generate_files(name, params, user=None, template=None, automatic=False):
    title, headers, rows, totals, _, filters = run_report(params, user)
    title = name or title
    folder = settings.REPORTS_ROOT / timezone.localtime().strftime("%Y/%m")
    folder.mkdir(parents=True, exist_ok=True)
    base = f"{slugify(title)[:60] or 'hisobot'}_{timezone.localtime():%Y%m%d_%H%M%S}"
    xlsx_path, pdf_path = folder / f"{base}.xlsx", folder / f"{base}.pdf"
    xlsx_path.write_bytes(build_xlsx(title, headers, rows, filters, totals))
    pdf_path.write_bytes(build_pdf(title, headers, rows, filters, totals))
    return GeneratedReport.objects.create(
        template=template,
        title=title,
        params=params,
        file_xlsx=str(xlsx_path.relative_to(settings.REPORTS_ROOT)),
        file_pdf=str(pdf_path.relative_to(settings.REPORTS_ROOT)),
        is_automatic=automatic,
        created_by=user,
    )


def is_due(template, now=None):
    if not template.periodicity:
        return False
    now = timezone.localtime(now or timezone.now())
    last = timezone.localtime(template.last_generated_at) if template.last_generated_at else None
    today = now.date()
    if template.periodicity == Periodicity.DAILY:
        start = today
    elif template.periodicity == Periodicity.WEEKLY:
        start = today - timedelta(days=today.weekday())
    elif template.periodicity == Periodicity.MONTHLY:
        start = today.replace(day=1)
    elif template.periodicity == Periodicity.QUARTERLY:
        start = today.replace(month=(today.month - 1) // 3 * 3 + 1, day=1)
    else:
        start = today.replace(month=1, day=1)
    return last is None or last.date() < start
