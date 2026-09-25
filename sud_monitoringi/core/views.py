from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.audit import log_action
from cases.models import Case
from reports.exports import export_response

from .forms import ClassifierForm, CourtForm, ImportForm, OrganizationForm
from .importers import COLUMNS, import_organizations
from .models import Classifier, ClassifierKind, Court, Organization
from .normalize import normalize_name


def _require_manager(user):
    if not user.can_manage_directory:
        raise PermissionDenied("Ma’lumotnomalarni boshqarish huquqingiz yo‘q.")


# --- Tashkilotlar ----------------------------------------------------------------

@login_required
def organization_list(request):
    qs = Organization.objects.select_related("org_type", "region", "parent").annotate(
        case_count=Count("cases", filter=Q(cases__is_cancelled=False))
    )
    q = request.GET.get("q", "").strip()
    if q:
        key = normalize_name(q)
        qs = qs.filter(Q(match_keys__icontains=key) | Q(stir__icontains=q) | Q(full_name__icontains=q))
    for param, lookup in (("org_type", "org_type_id"), ("region", "region_id"), ("parent", "parent_id")):
        if request.GET.get(param, "").isdigit():
            qs = qs.filter(**{lookup: request.GET[param]})
    if request.GET.get("active") in ("1", "0"):
        qs = qs.filter(is_active=request.GET["active"] == "1")
    qs = qs.order_by("org_type__order", "region__order", "full_name")
    fmt = request.GET.get("export")
    if fmt in ("xlsx", "pdf", "print"):
        rows = [[o.full_name, o.short_name, o.stir, o.org_type, o.region or "", o.district, o.parent or "",
                 o.previous_names.replace("\n", "; "), o.alt_names.replace("\n", "; "), "ha" if o.is_active else "yo‘q", o.case_count]
                for o in qs]
        return export_response(
            request, fmt, "Agentlik tizimidagi tashkilotlar ma’lumotnomasi",
            ["To‘liq nomi", "Qisqa nomi", "STIR", "Turi", "Hudud", "Tuman", "Yuqori tashkilot", "Oldingi nomlari",
             "Muqobil nomlari", "Faol", "Sud ishlari"], rows, filename="tashkilotlar",
        )
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "core/organization_list.html", {
        "page": page, "q": q, "querystring": params.urlencode(),
        "org_types": Classifier.objects.filter(kind=ClassifierKind.ORG_TYPE),
        "regions": Classifier.objects.filter(kind=ClassifierKind.REGION),
    })


@login_required
def organization_detail(request, pk):
    org = get_object_or_404(Organization.objects.select_related("org_type", "region", "parent"), pk=pk)
    scope = request.user.scope_organization_ids()
    cases = Case.objects.valid().filter(organization=org).select_related("status", "court")
    can_see_cases = scope is None or org.pk in scope
    return render(request, "core/organization_detail.html", {
        "org": org,
        "children": org.children.select_related("org_type").order_by("full_name"),
        "cases": cases.order_by("-created_at")[:20] if can_see_cases else [],
        "case_total": cases.count(),
        "can_see_cases": can_see_cases,
        "users": org.users.filter(is_active=True) if request.user.can_manage_directory else [],
    })


@login_required
def organization_edit(request, pk=None):
    _require_manager(request.user)
    org = get_object_or_404(Organization, pk=pk) if pk else None
    if request.method == "POST":
        form = OrganizationForm(request.POST, instance=org)
        if form.is_valid():
            org = form.save()
            log_action(request, "tashkilot_saqlandi", org, org.full_name)
            request._audit_logged = True
            messages.success(request, "Tashkilot ma’lumotlari saqlandi.")
            return redirect("core:organization_detail", pk=org.pk)
    else:
        form = OrganizationForm(instance=org, initial={"parent": request.GET.get("parent")} if not org else None)
    return render(request, "core/form.html", {
        "form": form, "title": f"Tahrirlash: {org}" if org else "Yangi tashkilot", "back": "core:organization_list",
    })


@login_required
def organization_import(request):
    _require_manager(request.user)
    result = None
    if request.method == "POST":
        form = ImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                result = import_organizations(request.FILES["file"])
                log_action(request, "tashkilotlar_import", description=f"Yangi {result['created']}, yangilangan {result['updated']}")
                request._audit_logged = True
                messages.success(request, f"Import yakunlandi: yangi {result['created']}, yangilangan {result['updated']}.")
            except Exception as exc:  # noqa: BLE001
                messages.error(request, f"Faylni o‘qib bo‘lmadi: {exc}")
    else:
        form = ImportForm()
    return render(request, "core/organization_import.html", {"form": form, "result": result, "columns": COLUMNS})


# --- Klassifikatorlar ------------------------------------------------------------

@login_required
def classifier_list(request):
    _require_manager(request.user)
    kind = request.GET.get("kind") or ClassifierKind.CASE_STATUS
    return render(request, "core/classifier_list.html", {
        "kinds": ClassifierKind.choices, "kind": kind, "kind_label": dict(ClassifierKind.choices).get(kind, ""),
        "items": Classifier.objects.filter(kind=kind).order_by("order", "name"),
    })


@login_required
def classifier_edit(request, pk=None):
    _require_manager(request.user)
    item = get_object_or_404(Classifier, pk=pk) if pk else None
    if request.method == "POST":
        form = ClassifierForm(request.POST, instance=item)
        if form.is_valid():
            item = form.save()
            log_action(request, "klassifikator_saqlandi", item, f"{item.get_kind_display()}: {item.name}")
            request._audit_logged = True
            messages.success(request, "Klassifikator saqlandi.")
            return redirect(f"{reverse('core:classifier_list')}?kind={item.kind}")
    else:
        form = ClassifierForm(instance=item, initial={"kind": request.GET.get("kind")} if not item else None)
    return render(request, "core/form.html", {"form": form, "title": "Klassifikator qiymati", "back": "core:classifier_list"})


# --- Sudlar ---------------------------------------------------------------------

@login_required
def court_list(request):
    qs = Court.objects.select_related("court_type", "region").annotate(case_count=Count("cases")).order_by("name")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(name_key__icontains=normalize_name(q))
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "core/court_list.html", {"page": page, "q": q})


@login_required
def court_edit(request, pk=None):
    _require_manager(request.user)
    court = get_object_or_404(Court, pk=pk) if pk else None
    if request.method == "POST":
        form = CourtForm(request.POST, instance=court)
        if form.is_valid():
            court = form.save()
            messages.success(request, "Sud ma’lumotlari saqlandi.")
            return redirect("core:court_list")
    else:
        form = CourtForm(instance=court)
    return render(request, "core/form.html", {"form": form, "title": "Sud", "back": "core:court_list"})
