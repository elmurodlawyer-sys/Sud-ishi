from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.db.models import Q
from django.utils import timezone

from cases.forms import BootstrapMixin
from core.models import Organization

from .models import CENTRAL_ROLES, AuditLog, User


class LoginForm(BootstrapMixin, AuthenticationForm):
    """Ketma-ket noto'g'ri urinishlarda vaqtincha bloklaydigan kirish formasi."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Login"
        self.fields["password"].label = "Parol"
        self._style()

    def clean(self):
        username = (self.data.get("username") or "").strip()
        if username:
            since = timezone.now() - timedelta(minutes=settings.LOGIN_LOCK_MINUTES)
            last_ok = AuditLog.objects.filter(username=username, action="kirish").order_by("-created_at").values_list("created_at", flat=True).first()
            failures = AuditLog.objects.filter(username=username, action="kirish_xato", created_at__gte=since)
            if last_ok:
                failures = failures.filter(created_at__gt=last_ok)
            if failures.count() >= settings.LOGIN_MAX_ATTEMPTS:
                raise forms.ValidationError(
                    f"Ko‘p marta noto‘g‘ri parol kiritildi. {settings.LOGIN_LOCK_MINUTES} daqiqadan so‘ng qayta urinib ko‘ring.",
                    code="locked",
                )
        return super().clean()


class UserForm(BootstrapMixin, forms.ModelForm):
    password1 = forms.CharField(label="Parol", widget=forms.PasswordInput, required=False)
    password2 = forms.CharField(label="Parolni takrorlang", widget=forms.PasswordInput, required=False)

    class Meta:
        model = User
        fields = [
            "username", "last_name", "first_name", "middle_name", "email", "phone", "position", "role", "organization",
            "is_active", "email_notifications",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["organization"].queryset = Organization.objects.filter(
            Q(is_active=True) | Q(pk=self.instance.organization_id)
        ).order_by("full_name")
        if not self.instance.pk:
            self.fields["password1"].required = True
            self.fields["password2"].required = True
        else:
            self.fields["password1"].help_text = "Parolni o‘zgartirmaslik uchun bo‘sh qoldiring."
        self._style()

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "Parollar mos kelmadi.")
            else:
                try:
                    password_validation.validate_password(p1, self.instance)
                except forms.ValidationError as exc:
                    self.add_error("password1", exc)
        role = data.get("role")
        if role and role not in CENTRAL_ROLES and not data.get("organization"):
            self.add_error("organization", "Ushbu rol uchun tashkilot ko‘rsatilishi shart.")
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("password1"):
            user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class ProfileForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ["last_name", "first_name", "middle_name", "email", "phone", "position", "email_notifications"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
