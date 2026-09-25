from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    RAHBARIYAT = "rahbariyat", "Agentlik rahbariyati"
    YURIDIK = "yuridik", "Agentlik Yuridik bo‘limi xodimi"
    HUDUDIY = "hududiy", "Hududiy boshqarma rahbari / mas’ul xodimi"
    INSON = "inson", "“Inson” ijtimoiy xizmatlar markazi rahbari / mas’ul xodimi"
    TASHKILOT = "tashkilot", "Tizimdagi boshqa tashkilot rahbari / mas’ul xodimi"
    AT_MARKAZ = "at_markaz", "Axborot texnologiyalari markazi mas’ul xodimi"
    ADMIN = "admin", "Tizim administratori"


# Barcha tashkilotlar ma'lumotlarini ko'ra oladigan (markaziy) rollar
CENTRAL_ROLES = {Role.RAHBARIYAT, Role.YURIDIK, Role.AT_MARKAZ, Role.ADMIN}
# O'z tashkiloti (va quyi tashkilotlari) doirasida ishlaydigan rollar
ORG_ROLES = {Role.HUDUDIY, Role.INSON, Role.TASHKILOT}


class User(AbstractUser):
    middle_name = models.CharField("Otasining ismi", max_length=150, blank=True)
    role = models.CharField("Rol", max_length=20, choices=Role.choices, default=Role.TASHKILOT)
    organization = models.ForeignKey(
        "core.Organization",
        verbose_name="Tashkilot",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="users",
    )
    position = models.CharField("Lavozimi", max_length=255, blank=True)
    phone = models.CharField("Telefon", max_length=50, blank=True)
    email_notifications = models.BooleanField("Xabarnomalarni e-pochtaga ham yuborish", default=True)

    class Meta:
        verbose_name = "Foydalanuvchi"
        verbose_name_plural = "Foydalanuvchilar"
        ordering = ["last_name", "first_name", "username"]

    def __str__(self):
        return self.get_full_name() or self.username

    def get_full_name(self):
        parts = [self.last_name, self.first_name, self.middle_name]
        return " ".join(p for p in parts if p).strip()

    # --- Huquqlar ----------------------------------------------------------
    @property
    def is_central(self):
        return self.is_superuser or self.role in CENTRAL_ROLES

    @property
    def is_system_admin(self):
        return self.is_superuser or self.role == Role.ADMIN

    @property
    def is_legal(self):
        """Yuridik bo'lim huquqlari (tasdiqlash, qaytarish, bekor qilish)."""
        return self.is_superuser or self.role in (Role.YURIDIK, Role.ADMIN)

    @property
    def can_edit_cases(self):
        return self.is_superuser or self.role in (Role.YURIDIK, Role.ADMIN, *ORG_ROLES)

    @property
    def can_manage_directory(self):
        """Tashkilotlar ma'lumotnomasi va klassifikatorlarni boshqarish."""
        return self.is_superuser or self.role in (Role.YURIDIK, Role.ADMIN)

    @property
    def can_manage_integration(self):
        return self.is_superuser or self.role in (Role.AT_MARKAZ, Role.ADMIN, Role.YURIDIK)

    @property
    def can_export(self):
        return self.is_active

    def scope_organization_ids(self):
        """Foydalanuvchi ko'ra oladigan tashkilotlar ID ro'yxati.

        None — cheklov yo'q (barcha tashkilotlar).
        """
        if self.is_central:
            return None
        if not self.organization_id:
            return []
        return self.organization.descendant_ids(include_self=True)


class AuditLog(models.Model):
    """Foydalanuvchi harakatlari jurnali (6-bo'lim talablari)."""

    created_at = models.DateTimeField("Vaqt", auto_now_add=True, db_index=True)
    user = models.ForeignKey(User, verbose_name="Foydalanuvchi", on_delete=models.SET_NULL, null=True, blank=True)
    username = models.CharField("Login", max_length=150, blank=True)
    action = models.CharField("Harakat", max_length=50, db_index=True)
    object_type = models.CharField("Obyekt turi", max_length=100, blank=True)
    object_id = models.CharField("Obyekt ID", max_length=64, blank=True)
    description = models.TextField("Tavsif", blank=True)
    path = models.CharField("Manzil", max_length=500, blank=True)
    method = models.CharField(max_length=10, blank=True)
    ip_address = models.GenericIPAddressField("IP manzil", null=True, blank=True)
    is_admin_action = models.BooleanField("Administrator harakati", default=False)

    class Meta:
        verbose_name = "Harakatlar jurnali yozuvi"
        verbose_name_plural = "Harakatlar jurnali"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%d.%m.%Y %H:%M} {self.username} {self.action}"
