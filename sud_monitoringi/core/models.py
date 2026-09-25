from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from .normalize import normalize_name


class ClassifierKind(models.TextChoices):
    REGION = "region", "Hududlar"
    ORG_TYPE = "org_type", "Tashkilot turlari"
    COURT_TYPE = "court_type", "Sud turlari"
    INSTANCE = "instance", "Sud instansiyalari (bosqichlari)"
    CASE_CATEGORY = "case_category", "Ish turkumlari (turlari)"
    CASE_STATUS = "case_status", "Ish holatlari"
    OUTCOME = "outcome", "Ish natijalari"
    DOCUMENT_TYPE = "document_type", "Hujjat turlari"
    HEARING_RESULT = "hearing_result", "Sud majlisi natijalari"
    DEADLINE_TYPE = "deadline_type", "Muddat turlari"


class ClassifierQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)

    def of(self, kind):
        return self.filter(kind=kind)


class Classifier(models.Model):
    """Yagona klassifikator jadvali.

    Klassifikatorlar dastur kodiga o'zgartirish kiritmasdan tizim ichidan
    boshqariladi (9-bo'lim). `code` qiymati tizim mantig'ida foydalaniladigan
    yozuvlar uchun o'zgarmas bo'lib, `is_system` belgisi bilan himoyalangan.
    """

    kind = models.CharField("Klassifikator turi", max_length=30, choices=ClassifierKind.choices, db_index=True)
    code = models.SlugField("Kod", max_length=50)
    name = models.CharField("Nomi", max_length=255)
    order = models.PositiveIntegerField("Tartib raqami", default=100)
    is_active = models.BooleanField("Faol", default=True)
    is_system = models.BooleanField(
        "Tizim yozuvi", default=False, help_text="Tizim mantig'ida ishlatiladi: kodi o'zgartirilmaydi, o'chirilmaydi."
    )
    is_final = models.BooleanField(
        "Yakuniy holat", default=False, help_text="Ish holati uchun: ushbu holatdagi ishlar yakunlangan hisoblanadi."
    )
    description = models.TextField("Izoh", blank=True)

    objects = ClassifierQuerySet.as_manager()

    class Meta:
        verbose_name = "Klassifikator qiymati"
        verbose_name_plural = "Klassifikatorlar"
        ordering = ["kind", "order", "name"]
        constraints = [models.UniqueConstraint(fields=["kind", "code"], name="uniq_classifier_kind_code")]

    def __str__(self):
        return self.name

    @classmethod
    def get(cls, kind, code):
        return cls.objects.filter(kind=kind, code=code).first()


def classifier_fk(kind, verbose_name, related_name, null=True, **kwargs):
    return models.ForeignKey(
        Classifier,
        verbose_name=verbose_name,
        on_delete=models.PROTECT,
        null=null,
        blank=null,
        related_name=related_name,
        limit_choices_to={"kind": kind},
        **kwargs,
    )


class Court(models.Model):
    name = models.CharField("Sud nomi", max_length=500)
    court_type = classifier_fk(ClassifierKind.COURT_TYPE, "Sud turi", "+")
    region = classifier_fk(ClassifierKind.REGION, "Hudud", "+")
    address = models.CharField("Manzil", max_length=500, blank=True)
    is_active = models.BooleanField("Faol", default=True)
    name_key = models.CharField(max_length=500, editable=False, db_index=True)

    class Meta:
        verbose_name = "Sud"
        verbose_name_plural = "Sudlar"
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.name_key = normalize_name(self.name)
        super().save(*args, **kwargs)


stir_validator = RegexValidator(r"^\d{9}$", "STIR 9 ta raqamdan iborat bo‘lishi kerak.")


class Organization(models.Model):
    """Agentlik va uning tizimidagi tashkilotlar ma'lumotnomasi (3.1-band)."""

    full_name = models.CharField("To‘liq nomi", max_length=500)
    short_name = models.CharField("Qisqartirilgan nomi", max_length=255, blank=True)
    stir = models.CharField("STIR", max_length=9, blank=True, validators=[stir_validator], db_index=True)
    org_type = classifier_fk(ClassifierKind.ORG_TYPE, "Tashkilot turi", "+", null=False)
    region = classifier_fk(ClassifierKind.REGION, "Hudud", "+")
    district = models.CharField("Tuman (shahar)", max_length=255, blank=True)
    parent = models.ForeignKey(
        "self",
        verbose_name="Yuqori turuvchi tashkilot",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="children",
    )
    previous_names = models.TextField("Oldingi nomlari", blank=True, help_text="Har bir nom alohida qatorda.")
    alt_names = models.TextField(
        "Muqobil yozilish variantlari", blank=True, help_text="Har bir variant alohida qatorda (kirill, rus tilida va h.k.)."
    )
    is_active = models.BooleanField("Faol", default=True)
    match_keys = models.TextField("Qidiruv kalitlari", blank=True, editable=False)
    created_at = models.DateTimeField("Yaratilgan", auto_now_add=True)
    updated_at = models.DateTimeField("Yangilangan", auto_now=True)

    class Meta:
        verbose_name = "Tashkilot"
        verbose_name_plural = "Tashkilotlar"
        ordering = ["full_name"]
        constraints = [
            models.UniqueConstraint(fields=["stir"], condition=~models.Q(stir=""), name="uniq_organization_stir"),
        ]

    def __str__(self):
        return self.short_name or self.full_name

    def clean(self):
        node, seen = self.parent, set()
        while node is not None:
            if node.pk == self.pk or node.pk in seen:
                raise ValidationError({"parent": "Tashkilot o‘ziga yoki o‘z quyi tashkilotiga bo‘ysunishi mumkin emas."})
            seen.add(node.pk)
            node = node.parent

    @staticmethod
    def _lines(text):
        return [line.strip() for line in (text or "").splitlines() if line.strip()]

    def all_names(self):
        names = [self.full_name, self.short_name, *self._lines(self.previous_names), *self._lines(self.alt_names)]
        return [n for n in names if n]

    def build_match_keys(self):
        keys = []
        for name in self.all_names():
            key = normalize_name(name)
            if key and key not in keys:
                keys.append(key)
        return keys

    def save(self, *args, **kwargs):
        self.match_keys = "\n".join(self.build_match_keys())
        super().save(*args, **kwargs)

    def descendant_ids(self, include_self=True):
        ids = [self.pk] if include_self else []
        frontier = [self.pk]
        while frontier:
            children = list(Organization.objects.filter(parent_id__in=frontier).values_list("pk", flat=True))
            children = [c for c in children if c not in ids]
            ids.extend(children)
            frontier = children
        return ids
