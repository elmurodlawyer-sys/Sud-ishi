from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from reports.exports import export_response

from . import backup
from .audit import log_action
from .forms import LoginForm, ProfileForm, UserForm
from .models import AuditLog, Role, User


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


def _require_admin(user):
    if not user.is_system_admin:
        raise PermissionDenied("Faqat tizim administratori uchun.")


@login_required
def profile(request):
    profile_form = ProfileForm(instance=request.user)
    password_form = PasswordChangeForm(request.user)
    for f in password_form.fields.values():
        f.widget.attrs["class"] = "form-control"
    if request.method == "POST":
        if request.POST.get("form") == "password":
            password_form = PasswordChangeForm(request.user, request.POST)
            for f in password_form.fields.values():
                f.widget.attrs["class"] = "form-control"
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                log_action(request, "parol_ozgartirildi", user)
                messages.success(request, "Parol o‘zgartirildi.")
                return redirect("accounts:profile")
        else:
            profile_form = ProfileForm(request.POST, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Ma’lumotlar saqlandi.")
                return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"profile_form": profile_form, "password_form": password_form})


@login_required
def user_list(request):
    _require_admin(request.user)
    qs = User.objects.select_related("organization").order_by("last_name", "first_name")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(last_name__icontains=q) | Q(first_name__icontains=q) | Q(organization__full_name__icontains=q))
    if request.GET.get("role"):
        qs = qs.filter(role=request.GET["role"])
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    return render(request, "accounts/user_list.html", {"page": page, "q": q, "roles": Role.choices})


@login_required
def user_edit(request, pk=None):
    _require_admin(request.user)
    obj = get_object_or_404(User, pk=pk) if pk else None
    if request.method == "POST":
        form = UserForm(request.POST, instance=obj)
        if form.is_valid():
            user = form.save()
            log_action(request, "foydalanuvchi_saqlandi", user, f"{user.username}, rol: {user.get_role_display()}")
            request._audit_logged = True
            messages.success(request, "Foydalanuvchi saqlandi.")
            return redirect("accounts:user_list")
    else:
        form = UserForm(instance=obj, initial={"organization": request.GET.get("organization")} if not obj else None)
    return render(request, "core/form.html", {"form": form, "title": f"Foydalanuvchi: {obj}" if obj else "Yangi foydalanuvchi", "back": "accounts:user_list"})


@login_required
def audit_log(request):
    if not (request.user.is_system_admin or request.user.role == Role.AT_MARKAZ):
        raise PermissionDenied
    qs = AuditLog.objects.select_related("user")
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(username__icontains=q) | Q(description__icontains=q) | Q(action__icontains=q) | Q(path__icontains=q))
    if request.GET.get("action"):
        qs = qs.filter(action=request.GET["action"])
    if request.GET.get("admin"):
        qs = qs.filter(is_admin_action=True)
    if request.GET.get("from"):
        qs = qs.filter(created_at__date__gte=request.GET["from"])
    if request.GET.get("to"):
        qs = qs.filter(created_at__date__lte=request.GET["to"])
    fmt = request.GET.get("export")
    if fmt in ("xlsx", "pdf"):
        rows = [[a.created_at, a.username, a.action, a.object_type, a.object_id, a.description, a.ip_address or ""] for a in qs[:20000]]
        return export_response(request, fmt, "Foydalanuvchilar harakatlari jurnali",
                               ["Vaqt", "Login", "Harakat", "Obyekt", "ID", "Tavsif", "IP"], rows, filename="jurnal")
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    actions = AuditLog.objects.order_by().values_list("action", flat=True).distinct()
    return render(request, "accounts/audit_log.html", {"page": page, "q": q, "actions": sorted(set(actions)), "querystring": params.urlencode()})


@login_required
def backups(request):
    _require_admin(request.user)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            path = backup.create_backup(label=f"qo‘lda: {request.user.username}")
            log_action(request, "zaxira_yaratildi", description=path.name)
            request._audit_logged = True
            messages.success(request, f"Zaxira nusxa yaratildi: {path.name}")
        elif action == "restore":
            if request.POST.get("confirm") != "TIKLASH":
                messages.error(request, "Tiklashni tasdiqlash uchun maydonga TIKLASH so‘zini kiriting.")
            else:
                try:
                    path = backup.resolve_backup(request.POST.get("name", ""))
                    backup.create_backup(label="tiklashdan oldingi avtomatik nusxa")
                    backup.restore_backup(path)
                    messages.success(request, f"Ma’lumotlar {path.name} nusxasidan tiklandi. Qayta tizimga kiring.")
                    return redirect("accounts:login")
                except FileNotFoundError:
                    messages.error(request, "Zaxira nusxa topilmadi.")
                except Exception as exc:  # noqa: BLE001
                    messages.error(request, f"Tiklashda xato: {exc}")
        return redirect("accounts:backups")
    return render(request, "accounts/backups.html", {"backups": backup.list_backups()})


@login_required
def backup_download(request, name):
    _require_admin(request.user)
    try:
        path = backup.resolve_backup(name)
    except FileNotFoundError:
        raise Http404
    log_action(request, "zaxira_yuklab_olindi", description=path.name)
    return FileResponse(open(path, "rb"), as_attachment=True, filename=path.name)
