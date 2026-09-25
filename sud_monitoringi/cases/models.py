import os
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.models import ClassifierKind, Court, Organization, classifier_fk
from core.normalize import normalize_case_number


class ProceduralRole(models.TextChoices):
    PLAINTIFF = "davogar", "Da’vogar"
    DEFENDANT = "javobgar", "Javobgar"
    THIRD_PARTY = "uchinchi", "Uchinchi shaxs"


class CaseSource(models.TextChoices):
    INTEGRATION = "integratsiya", "Integratsiya (avtomatik)"
    MANUAL = "qolda", "Foydalanuvchi tomonidan kiritilgan"


class ReviewStatus(models.TextChoices):
    DRAFT = "kiritilmoqda", "Ma’lumot kiritilmoqda"
    PENDING = "tasdiqlashda", "Yuridik bo‘lim tasdig‘ida"
    APPROVED = "tasdiqlangan", "Tasdiqlangan"
    RETURNED = "qaytarilgan", "Aniqlashtirish uchun qaytarilgan"


class AgencyResult(models.TextChoices):
    FAVOR = "foydasiga", "Agentlik tizimi foydasiga"
    AGAINST = "zarariga", "Agentlik tizimi zarariga"
    PARTIAL = "qisman", "Qisman foydasiga"
    NEUTRAL = "neytral", "Neytral / boshqa"


# Ish holatlari kodlari (tizim mantig'ida ishlatiladi, nomlari klassifikatorda boshqariladi)
class StatusCode:
    NEW = "yangi"
    CLARIFYING = "aniqlashtirilmoqda"
    IN_PROGRESS = "korilmoqda"
    HEARING_SET = "majlis_tayinlangan"
    HEARING_POSTPONED = "majlis_qoldirilgan"
    ACT_ADOPTED = "hujjat_qabul_qilingan"
    APPEAL = "apellyatsiya"
    CASSATION = "kassatsiya"
    OTHER_REVIEW = "qayta_korish"
    FINISHED = "yakunlangan"
    ARCHIVED = "arxivlangan"


class CaseQuerySet(models.QuerySet):
    def visible_to(self, user):
        qs = self
        scope = user.scope_organization_ids()
        if scope is not None:
            qs = qs.filter(organization_id__in=scope)
        return qs

    def valid(self):
        return self.filter(is_cancelled=False)

    def open(self):
        return self.filter(status__is_final=False)

    def closed(self):
        return self.filter(status__is_final=True)

    def stale(self):
        limit = timezone.now() - timedelta(days=settings.STALE_CASE_DAYS)
        return self.open().filter(last_activity_at__lt=limit)


class Case(models.Model):
    """Sud ishining elektron kartochkasi (3.3-band)."""

    reg_number = models.CharField("Tizimdagi yagona raqam", max_length=30, unique=True, blank=True, editable=False)
    case_number = models.CharField("Sud ishi raqami", max_length=100)
    case_number_key = models.CharField(max_length=100, editable=False, db_index=True)

    organization = models.ForeignKey(
        Organization, verbose_name="Agentlik tizimidagi tashkilot", on_delete=models.PROTECT, related_name="cases"
    )
    role = models.CharField("Protsessual maqomi", max_length=20, choices=ProceduralRole.choices)
    other_system_orgs = models.TextField(
        "Ishda ishtirok etuvchi tizimdagi boshqa tashkilotlar", blank=True, help_text="Integratsiyada aniqlangan qo‘shimcha tashkilotlar."
    )

    plaintiffs = models.TextField("Da’vogar", blank=True)
    defendants = models.TextField("Javobgar", blank=True)
    third_parties = models.TextField("Uchinchi shaxslar", blank=True)

    court = models.ForeignKey(Court, verbose_name="Sud", on_delete=models.PROTECT, null=True, blank=True, related_name="cases")
    instance = classifier_fk(ClassifierKind.INSTANCE, "Sud instansiyasi (joriy bosqich)", "+")
    category = classifier_fk(ClassifierKind.CASE_CATEGORY, "Ish turkumi (turi)", "+")
    subject = models.TextField("Ish predmeti", blank=True)
    claim_amount = models.DecimalField("Da’vo summasi (so‘m)", max_digits=20, decimal_places=2, null=True, blank=True)
    judge = models.CharField("Mas’ul sudya", max_length=255, blank=True)
    filed_date = models.DateField("Da’vo (ariza) berilgan sana", null=True, blank=True)

    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Tashkilotdagi mas’ul xodim",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responsible_cases",
    )
    status = classifier_fk(ClassifierKind.CASE_STATUS, "Ishning joriy holati", "+", null=False)
    next_hearing_at = models.DateTimeField("Navbatdagi sud majlisi", null=True, blank=True, db_index=True)

    outcome = classifier_fk(ClassifierKind.OUTCOME, "Ishning yakuniy natijasi", "+")
    outcome_date = models.DateField("Yakuniy sud hujjati sanasi", null=True, blank=True)
    agency_result = models.CharField("Agentlik tizimi uchun natija", max_length=20, choices=AgencyResult.choices, blank=True)
    awarded_amount = models.DecimalField(
        "Sud qarori bo‘yicha summa (so‘m)", max_digits=20, decimal_places=2, null=True, blank=True
    )
    outcome_note = models.TextField("Natija bo‘yicha izoh", blank=True)

    source = models.CharField("Ma’lumot manbasi", max_length=20, choices=CaseSource.choices, default=CaseSource.MANUAL)
    source_name = models.CharField("Manba nomi", max_length=255, blank=True)
    source_url = models.URLField("Manbadagi havola", max_length=1000, blank=True)
    source_fetched_at = models.DateTimeField("Manbadan birinchi olingan vaqt", null=True, blank=True)
    source_updated_at = models.DateTimeField("Manbadan oxirgi yangilangan vaqt", null=True, blank=True)

    review_status = models.CharField(
        "Tasdiqlash holati", max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.DRAFT
    )
    review_comment = models.TextField("Yuridik bo‘lim izohi", blank=True)

    is_cancelled = models.BooleanField("Bekor qilingan", default=False, db_index=True)
    cancel_reason = models.TextField("Bekor qilish sababi", blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    cancelled_at = models.DateTimeField(null=True, blank=True)
    archive_reason = models.TextField("Arxivga olish sababi", blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Ro‘yxatga olgan", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField("Ro‘yxatga olingan sana", default=timezone.now, db_index=True)
    updated_at = models.DateTimeField("Oxirgi yangilangan sana", auto_now=True)
    last_activity_at = models.DateTimeField("Oxirgi faollik", default=timezone.now, db_index=True)

    objects = CaseQuerySet.as_manager()

    class Meta:
        verbose_name = "Sud ishi"
        verbose_name_plural = "Sud ishlari"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["case_number_key", "court"],
                condition=models.Q(is_cancelled=False),
                name="uniq_active_case_per_court",
            )
        ]
        permissions = [("delete_case_physically", "Sud ishini jismonan o‘chirish")]

    def __str__(self):
        return f"{self.reg_number or '—'} / {self.case_number}"

    def get_absolute_url(self):
        return reverse("cases:detail", args=[self.pk])

    def save(self, *args, **kwargs):
        self.case_number_key = normalize_case_number(self.case_number)
        super().save(*args, **kwargs)
        if not self.reg_number:
            self.reg_number = f"SM-{self.created_at:%Y}-{self.pk:06d}"
            Case.objects.filter(pk=self.pk).update(reg_number=self.reg_number)

    @property
    def is_closed(self):
        return bool(self.status_id and self.status.is_final)

    @property
    def is_stale(self):
        if self.is_closed or self.is_cancelled:
            return False
        return self.last_activity_at < timezone.now() - timedelta(days=settings.STALE_CASE_DAYS)

    @property
    def court_type(self):
        return self.court.court_type if self.court_id else None

    def control_warnings(self):
        """Nazoratga chiqariladigan kamchiliklar (4-bo'lim biznes qoidalari)."""
        warnings = []
        if self.is_cancelled:
            return warnings
        if self.status_id and self.status.code == StatusCode.FINISHED:
            if not self.outcome_id:
                warnings.append("Ish yakunlangan, ammo yakuniy natija kiritilmagan.")
            if not self.documents.filter(doc_type__code="yakuniy_hujjat").exists():
                warnings.append("Ish yakunlangan, ammo yakuniy sud hujjati biriktirilmagan.")
        if self.is_stale:
            warnings.append(f"Ish {settings.STALE_CASE_DAYS} kundan ortiq yangilanmagan.")
        if self.deadlines.filter(is_done=False, due_date__lt=timezone.localdate()).exists():
            warnings.append("Muddati o‘tib ketgan nazorat mavjud.")
        if not self.responsible_id:
            warnings.append("Tashkilotdagi mas’ul xodim belgilanmagan.")
        return warnings

    def refresh_next_hearing(self, save=True):
        upcoming = (
            self.hearings.filter(status=HearingStatus.SCHEDULED, scheduled_at__gte=timezone.now())
            .order_by("scheduled_at")
            .first()
        )
        self.next_hearing_at = upcoming.scheduled_at if upcoming else None
        if save:
            Case.objects.filter(pk=self.pk).update(next_hearing_at=self.next_hearing_at)


class CaseStage(models.Model):
    """Sud bosqichi: birinchi instansiya, apellyatsiya, kassatsiya va boshqalar (3.4-band)."""

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="stages")
    instance = classifier_fk(ClassifierKind.INSTANCE, "Instansiya", "+", null=False)
    court = models.ForeignKey(Court, verbose_name="Sud", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    case_number = models.CharField("Ushbu bosqichdagi ish raqami", max_length=100, blank=True)
    judge = models.CharField("Sudya", max_length=255, blank=True)
    started_on = models.DateField("Bosqich boshlangan sana", default=timezone.localdate)
    ended_on = models.DateField("Bosqich tugagan sana", null=True, blank=True)
    result = classifier_fk(ClassifierKind.OUTCOME, "Bosqich natijasi", "+")
    note = models.TextField("Izoh", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sud bosqichi"
        verbose_name_plural = "Sud bosqichlari"
        ordering = ["started_on", "id"]

    def __str__(self):
        return f"{self.instance} ({self.started_on:%d.%m.%Y})"


class HearingStatus(models.TextChoices):
    SCHEDULED = "rejalashtirilgan", "Rejalashtirilgan"
    HELD = "otkazildi", "O‘tkazildi"
    POSTPONED = "qoldirildi", "Qoldirildi"
    CANCELLED = "bekor", "Bekor qilindi"


class Hearing(models.Model):
    """Sud majlisi (3.5-band)."""

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="hearings")
    stage = models.ForeignKey(CaseStage, verbose_name="Bosqich", on_delete=models.SET_NULL, null=True, blank=True, related_name="hearings")
    scheduled_at = models.DateTimeField("Sud majlisi sanasi va vaqti", db_index=True)
    location = models.CharField("Joyi (zal)", max_length=255, blank=True)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Majlisda ishtirok etuvchi mas’ul xodim",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hearings",
    )
    status = models.CharField("Holati", max_length=20, choices=HearingStatus.choices, default=HearingStatus.SCHEDULED)
    result = classifier_fk(ClassifierKind.HEARING_RESULT, "Majlis natijasi", "+")
    result_note = models.TextField("Natija bo‘yicha izoh", blank=True)
    source = models.CharField("Manba", max_length=20, choices=CaseSource.choices, default=CaseSource.MANUAL)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sud majlisi"
        verbose_name_plural = "Sud majlislari"
        ordering = ["scheduled_at"]

    def __str__(self):
        return f"{self.case.case_number}: {timezone.localtime(self.scheduled_at):%d.%m.%Y %H:%M}"


class DeadlineKind(models.TextChoices):
    PROCEDURAL = "protsessual", "Protsessual muddat"
    INTERNAL = "ichki", "Ichki nazorat muddati"


class DeadlineQuerySet(models.QuerySet):
    def pending(self):
        return self.filter(is_done=False, case__is_cancelled=False)

    def overdue(self):
        return self.pending().filter(due_date__lt=timezone.localdate())

    def upcoming(self, days=None):
        days = settings.DEADLINE_REMINDER_DAYS if days is None else days
        today = timezone.localdate()
        return self.pending().filter(due_date__gte=today, due_date__lte=today + timedelta(days=days))


class Deadline(models.Model):
    """Protsessual va ichki nazorat muddatlari (3.5-band)."""

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="deadlines")
    kind = models.CharField("Muddat turi", max_length=20, choices=DeadlineKind.choices, default=DeadlineKind.PROCEDURAL)
    deadline_type = classifier_fk(ClassifierKind.DEADLINE_TYPE, "Muddat nomi (klassifikator)", "+")
    title = models.CharField("Mazmuni", max_length=500)
    due_date = models.DateField("Muddat", db_index=True)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Mas’ul", on_delete=models.SET_NULL, null=True, blank=True, related_name="deadlines"
    )
    is_done = models.BooleanField("Bajarildi", default=False)
    done_at = models.DateTimeField("Bajarilgan vaqt", null=True, blank=True)
    done_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    note = models.TextField("Izoh", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = DeadlineQuerySet.as_manager()

    class Meta:
        verbose_name = "Nazorat muddati"
        verbose_name_plural = "Nazorat muddatlari"
        ordering = ["due_date"]

    def __str__(self):
        return f"{self.title} — {self.due_date:%d.%m.%Y}"

    @property
    def is_overdue(self):
        return not self.is_done and self.due_date < timezone.localdate()

    @property
    def days_left(self):
        return (self.due_date - timezone.localdate()).days


def document_upload_to(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    now = timezone.now()
    return f"case_documents/{now:%Y/%m}/{instance.case_id}_{now:%Y%m%d%H%M%S%f}{ext}"


class CaseDocument(models.Model):
    """Sud ishi bo'yicha hujjat (3.6-band)."""

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="documents")
    doc_type = classifier_fk(ClassifierKind.DOCUMENT_TYPE, "Hujjat turi", "+", null=False)
    title = models.CharField("Hujjat nomi (qisqacha mazmuni)", max_length=500, blank=True)
    number = models.CharField("Hujjat raqami", max_length=100, blank=True)
    doc_date = models.DateField("Hujjat sanasi", null=True, blank=True)
    file = models.FileField("Fayl", upload_to=document_upload_to)
    original_name = models.CharField("Asl fayl nomi", max_length=255, blank=True)
    size = models.PositiveBigIntegerField("Hajmi (bayt)", default=0)
    note = models.TextField("Izoh", blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name="Yuklagan foydalanuvchi", on_delete=models.SET_NULL, null=True, related_name="+"
    )
    uploaded_at = models.DateTimeField("Yuklangan vaqt", auto_now_add=True)

    class Meta:
        verbose_name = "Hujjat"
        verbose_name_plural = "Hujjatlar"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.title or self.original_name


class EventType(models.TextChoices):
    CREATED = "yaratildi", "Kartochka yaratildi"
    UPDATED = "yangilandi", "Ma’lumotlar o‘zgartirildi"
    STATUS = "holat", "Holat o‘zgartirildi"
    STAGE = "bosqich", "Sud bosqichi o‘zgartirildi"
    HEARING = "majlis", "Sud majlisi"
    DEADLINE = "muddat", "Nazorat muddati"
    DOCUMENT = "hujjat", "Hujjat"
    INTEGRATION = "integratsiya", "Integratsiya orqali yangilandi"
    REVIEW = "tasdiqlash", "Tasdiqlash / qaytarish"
    ASSIGNED = "biriktirildi", "Biriktirildi"
    CANCELLED = "bekor", "Bekor qilindi"
    ARCHIVED = "arxiv", "Arxivga olindi"
    RESTORED = "tiklandi", "Qayta tiklandi"


class CaseEvent(models.Model):
    """Sud ishi bo'yicha o'zgarishlar tarixi (4-bo'lim: har bir muhim o'zgarish qayd etiladi)."""

    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="events")
    created_at = models.DateTimeField("Vaqt", default=timezone.now, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name="Foydalanuvchi", on_delete=models.SET_NULL, null=True, blank=True)
    event_type = models.CharField("Hodisa", max_length=20, choices=EventType.choices)
    description = models.CharField("Tavsif", max_length=1000)
    changes = models.JSONField("O‘zgarishlar", default=list, blank=True)
    comment = models.TextField("Izoh", blank=True)

    class Meta:
        verbose_name = "O‘zgarishlar tarixi yozuvi"
        verbose_name_plural = "O‘zgarishlar tarixi"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.case} — {self.description}"
