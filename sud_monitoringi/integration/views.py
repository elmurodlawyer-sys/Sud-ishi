from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.audit import log_action

from .adapters import FIELDS, AdapterError, parse_uploaded_file
from .forms import FileImportForm, SourceForm
from .models import AdapterType, IntegrationRun, IntegrationSource
from .services import run_source


def _require(user):
    if not user.can_manage_integration:
        raise PermissionDenied("Integratsiyani boshqarish huquqingiz yo‘q.")


@login_required
def source_list(request):
    _require(request.user)
    return render(request, "integration/source_list.html", {
        "sources": IntegrationSource.objects.all(),
        "runs": IntegrationRun.objects.select_related("source", "triggered_by")[:30],
    })


@login_required
def source_edit(request, pk=None):
    _require(request.user)
    source = get_object_or_404(IntegrationSource, pk=pk) if pk else None
    if request.method == "POST":
        form = SourceForm(request.POST, instance=source)
        if form.is_valid():
            source = form.save()
            log_action(request, "integratsiya_sozlandi", source, source.name)
            request._audit_logged = True
            messages.success(request, "Manba sozlamalari saqlandi.")
            return redirect("integration:source_list")
    else:
        form = SourceForm(instance=source)
    return render(request, "integration/source_form.html", {"form": form, "source": source})


@login_required
@require_POST
def source_run(request, pk):
    _require(request.user)
    source = get_object_or_404(IntegrationSource, pk=pk)
    run = run_source(source, request.user)
    log_action(request, "integratsiya_ishga_tushirildi", source, source.last_status)
    request._audit_logged = True
    level = messages.success if run.status != "xato" else messages.error
    level(request, f"{source.name}: {source.last_status}")
    return redirect("integration:run_detail", pk=run.pk)


@login_required
def run_detail(request, pk):
    _require(request.user)
    run = get_object_or_404(IntegrationRun.objects.select_related("source"), pk=pk)
    return render(request, "integration/run_detail.html", {"run": run})


@login_required
def file_import(request):
    _require(request.user)
    if request.method == "POST":
        form = FileImportForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                records = parse_uploaded_file(request.FILES["file"])
            except (AdapterError, ValueError, UnicodeDecodeError) as exc:
                messages.error(request, f"Faylni o‘qib bo‘lmadi: {exc}")
            else:
                source, _ = IntegrationSource.objects.get_or_create(
                    name=form.cleaned_data["source_name"], adapter=AdapterType.FILE, defaults={"is_active": False}
                )
                run = run_source(source, request.user, records=records)
                log_action(request, "fayldan_import", source, source.last_status)
                request._audit_logged = True
                messages.success(request, source.last_status)
                return redirect("integration:run_detail", pk=run.pk)
    else:
        form = FileImportForm()
    return render(request, "integration/file_import.html", {"form": form, "fields": FIELDS})
