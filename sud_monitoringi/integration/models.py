from django.conf import settings
from django.db import models


class AdapterType(models.TextChoices):
    JSON_API = "json_api", "Rasmiy API / veb-servis (JSON)"
    HTML = "html", "Veb-sahifa jadvalini o‘qish (jadval2.sud.uz)"
    FILE = "file", "Fayldan import (JSON / CSV / Excel)"
    DEMO = "demo", "Sinov (demo) manba"


class IntegrationSource(models.Model):
    """Tashqi ma'lumot manbasi (3.2 va 8-bo'limlar)."""

    name = models.CharField("Nomi", max_length=255)
    adapter = models.CharField("Ulanish usuli", max_length=20, choices=AdapterType.choices)
    base_url = models.URLField("Manzil (URL)", max_length=1000, blank=True)
    auth_token = models.CharField(
        "Kirish kaliti (token)", max_length=1000, blank=True, help_text="API rasmiy kaliti. Sahifada ko‘rsatilmaydi."
    )
    config = models.JSONField(
        "Qo‘shimcha sozlamalar (JSON)",
        default=dict,
        blank=True,
        help_text="Maydonlar moslamasi, so‘rov parametrlari, sahifalar ro‘yxati va h.k. (README'ga qarang).",
    )
    interval_minutes = models.PositiveIntegerField("Tekshirish davriyligi (daqiqa)", default=360)
    is_active = models.BooleanField("Faol", default=True)
    last_run_at = models.DateTimeField("Oxirgi tekshiruv", null=True, blank=True)
    last_success_at = models.DateTimeField("Oxirgi muvaffaqiyatli tekshiruv", null=True, blank=True)
    last_status = models.CharField("Oxirgi holat", max_length=255, blank=True)

    class Meta:
        verbose_name = "Integratsiya manbasi"
        verbose_name_plural = "Integratsiya manbalari"
        ordering = ["name"]

    def __str__(self):
        return self.name


class RunStatus(models.TextChoices):
    RUNNING = "jarayonda", "Jarayonda"
    SUCCESS = "muvaffaqiyatli", "Muvaffaqiyatli"
    PARTIAL = "qisman", "Qisman (xatoliklar bilan)"
    FAILED = "xato", "Xato"


class IntegrationRun(models.Model):
    source = models.ForeignKey(IntegrationSource, on_delete=models.CASCADE, related_name="runs")
    started_at = models.DateTimeField("Boshlangan", auto_now_add=True)
    finished_at = models.DateTimeField("Tugagan", null=True, blank=True)
    status = models.CharField("Holat", max_length=20, choices=RunStatus.choices, default=RunStatus.RUNNING)
    triggered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    fetched = models.PositiveIntegerField("Olingan yozuvlar", default=0)
    matched = models.PositiveIntegerField("Tizim tashkilotlariga tegishli", default=0)
    created = models.PositiveIntegerField("Yangi kartochkalar", default=0)
    updated = models.PositiveIntegerField("Yangilangan kartochkalar", default=0)
    unchanged = models.PositiveIntegerField("O‘zgarmagan", default=0)
    errors = models.TextField("Xatoliklar", blank=True)

    class Meta:
        verbose_name = "Integratsiya seansi"
        verbose_name_plural = "Integratsiya seanslari"
        ordering = ["-started_at"]

    def __str__(self):
        return f"{self.source} — {self.started_at:%d.%m.%Y %H:%M}"


class ExternalRecord(models.Model):
    """Manbadan olingan xom yozuv. Oldingi tekshiruv bilan solishtirish uchun saqlanadi."""

    source = models.ForeignKey(IntegrationSource, on_delete=models.CASCADE, related_name="records")
    external_key = models.CharField("Tashqi kalit", max_length=500)
    data = models.JSONField("Ma’lumot", default=dict)
    data_hash = models.CharField(max_length=64)
    case = models.ForeignKey("cases.Case", on_delete=models.SET_NULL, null=True, blank=True, related_name="external_records")
    first_seen_at = models.DateTimeField("Birinchi aniqlangan", auto_now_add=True)
    last_seen_at = models.DateTimeField("Oxirgi aniqlangan", auto_now=True)
    last_changed_at = models.DateTimeField("Oxirgi o‘zgargan", null=True, blank=True)

    class Meta:
        verbose_name = "Tashqi yozuv"
        verbose_name_plural = "Tashqi yozuvlar"
        constraints = [models.UniqueConstraint(fields=["source", "external_key"], name="uniq_external_record")]

    def __str__(self):
        return self.external_key
