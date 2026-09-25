from django.conf import settings
from django.db import models


class Periodicity(models.TextChoices):
    DAILY = "kunlik", "Har kuni"
    WEEKLY = "haftalik", "Har hafta (dushanba)"
    MONTHLY = "oylik", "Har oy (1-sana)"
    QUARTERLY = "choraklik", "Har chorak"
    YEARLY = "yillik", "Har yil"


class ReportTemplate(models.Model):
    """Saqlangan hisobot shabloni. Davriy avtomatik shakllantirish mumkin (7-bo'lim)."""

    name = models.CharField("Nomi", max_length=255)
    params = models.JSONField("Parametrlar", default=dict)
    periodicity = models.CharField("Avtomatik shakllantirish", max_length=20, choices=Periodicity.choices, blank=True)
    recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL, verbose_name="Xabardor qilinadiganlar", blank=True, related_name="+"
    )
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    last_generated_at = models.DateTimeField("Oxirgi shakllantirilgan", null=True, blank=True)

    class Meta:
        verbose_name = "Hisobot shabloni"
        verbose_name_plural = "Hisobot shablonlari"
        ordering = ["name"]

    def __str__(self):
        return self.name


class GeneratedReport(models.Model):
    """Shakllantirilgan va saqlangan hisobot fayli."""

    template = models.ForeignKey(ReportTemplate, on_delete=models.SET_NULL, null=True, blank=True, related_name="generated")
    title = models.CharField("Nomi", max_length=255)
    params = models.JSONField("Parametrlar", default=dict)
    file_xlsx = models.CharField("Excel fayl", max_length=500, blank=True)
    file_pdf = models.CharField("PDF fayl", max_length=500, blank=True)
    is_automatic = models.BooleanField("Avtomatik", default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Shakllantirilgan hisobot"
        verbose_name_plural = "Shakllantirilgan hisobotlar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
