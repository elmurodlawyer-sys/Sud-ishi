from django.conf import settings
from django.db import models


class NotificationKind(models.TextChoices):
    NEW_CASE = "yangi_ish", "Yangi sud ishi aniqlandi"
    ASSIGNED = "biriktirildi", "Sud ishi biriktirildi"
    HEARING_SET = "majlis_belgilandi", "Sud majlisi belgilandi / o‘zgartirildi"
    HEARING_SOON = "majlis_yaqin", "Sud majlisi yaqinlashmoqda"
    DEADLINE_SOON = "muddat_yaqin", "Muddat yaqinlashmoqda"
    OVERDUE = "muddat_otdi", "Muddat o‘tib ketdi"
    NEW_INFO = "yangi_malumot", "Yangi ma’lumot yoki hujjat"
    STATUS = "holat", "Holat yoki bosqich o‘zgardi"
    FINISHED = "yakunlandi", "Ish yakunlandi"
    RETURNED = "qaytarildi", "Aniqlashtirish uchun qaytarildi"
    REVIEW = "tasdiqlash", "Tasdiqlash so‘ralmoqda"
    STALE = "yangilanmagan", "Ish uzoq muddat yangilanmagan"
    SYSTEM = "tizim", "Tizim xabari"


class Notification(models.Model):
    """Tizim ichidagi xabarnoma (5-bo'lim)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    case = models.ForeignKey("cases.Case", on_delete=models.CASCADE, null=True, blank=True, related_name="notifications")
    kind = models.CharField("Turi", max_length=30, choices=NotificationKind.choices)
    title = models.CharField("Sarlavha", max_length=255)
    message = models.TextField("Matn", blank=True)
    created_at = models.DateTimeField("Vaqt", auto_now_add=True, db_index=True)
    is_read = models.BooleanField("O‘qilgan", default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    emailed = models.BooleanField("E-pochtaga yuborilgan", default=False)
    # Bir xil eslatmani qayta-qayta yubormaslik uchun kalit (masalan, "hearing-12-3d")
    dedup_key = models.CharField(max_length=120, blank=True, db_index=True)

    class Meta:
        verbose_name = "Xabarnoma"
        verbose_name_plural = "Xabarnomalar"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
