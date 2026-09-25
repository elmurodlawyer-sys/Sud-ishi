"""Sud ishlarini qidirish va filtrlash (3.7-band). Ro'yxat, eksport, hisobot va dashboard uchun umumiy."""
from datetime import timedelta

from django import forms
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from core.models import Classifier, ClassifierKind, Court, Organization
from core.normalize import normalize_case_number

from .models import AgencyResult, Case, CaseSource, ProceduralRole, ReviewStatus

EMPTY = [("", "— barchasi —")]


def _classifier_choices(kind):
    return forms.ModelChoiceField(
        queryset=Classifier.objects.filter(kind=kind).order_by("order", "name"), required=False, empty_label="— barchasi —"
    )


class CaseFilterForm(forms.Form):
    q = forms.CharField(label="Umumiy qidiruv", required=False, widget=forms.TextInput(attrs={"placeholder": "Ish raqami, taraf, predmet..."}))
    case_number = forms.CharField(label="Ish raqami", required=False)
    organization = forms.ModelChoiceField(queryset=Organization.objects.none(), required=False, label="Tashkilot", empty_label="— barchasi —")
    include_children = forms.BooleanField(label="Quyi tashkilotlar bilan", required=False)
    org_type = _classifier_choices(ClassifierKind.ORG_TYPE)
    region = _classifier_choices(ClassifierKind.REGION)
    court_type = _classifier_choices(ClassifierKind.COURT_TYPE)
    court = forms.ModelChoiceField(queryset=Court.objects.order_by("name"), required=False, label="Sud nomi", empty_label="— barchasi —")
    instance = _classifier_choices(ClassifierKind.INSTANCE)
    category = _classifier_choices(ClassifierKind.CASE_CATEGORY)
    plaintiff = forms.CharField(label="Da’vogar", required=False)
    defendant = forms.CharField(label="Javobgar", required=False)
    third_party = forms.CharField(label="Uchinchi shaxs", required=False)
    role = forms.ChoiceField(label="Protsessual maqom", choices=EMPTY + list(ProceduralRole.choices), required=False)
    responsible = forms.ModelChoiceField(queryset=User.objects.none(), required=False, label="Mas’ul xodim", empty_label="— barchasi —")
    status = _classifier_choices(ClassifierKind.CASE_STATUS)
    state = forms.ChoiceField(
        label="Jarayon", required=False, choices=EMPTY + [("open", "Jarayondagi"), ("closed", "Yakunlangan / arxiv")]
    )
    outcome = _classifier_choices(ClassifierKind.OUTCOME)
    agency_result = forms.ChoiceField(label="Agentlik uchun natija", choices=EMPTY + list(AgencyResult.choices), required=False)
    review_status = forms.ChoiceField(label="Tasdiqlash holati", choices=EMPTY + list(ReviewStatus.choices), required=False)
    source = forms.ChoiceField(label="Ma’lumot manbasi", choices=EMPTY + list(CaseSource.choices), required=False)
    hearing_from = forms.DateField(label="Sud majlisi (dan)", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    hearing_to = forms.DateField(label="Sud majlisi (gacha)", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    created_from = forms.DateField(label="Ro‘yxatga olingan (dan)", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    created_to = forms.DateField(label="Ro‘yxatga olingan (gacha)", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    period = forms.ChoiceField(
        label="Davr", required=False,
        choices=EMPTY + [("today", "Bugun"), ("week", "Joriy hafta"), ("month", "Joriy oy"), ("quarter", "Joriy chorak"), ("year", "Joriy yil")],
    )
    majlis = forms.ChoiceField(
        label="Sud majlislari", required=False,
        choices=EMPTY + [("bugun", "Bugungi majlislar"), ("hafta", "Kelgusi 7 kun"), ("kelgusi", "Barcha kelgusi"), ("yoq", "Majlis belgilanmagan")],
    )
    nazorat = forms.ChoiceField(
        label="Nazorat", required=False,
        choices=EMPTY + [
            ("yaqin", "Muddati yaqinlashayotgan"), ("otgan", "Muddati o‘tib ketgan"),
            ("yangilanmagan", "Uzoq muddat yangilanmagan"), ("natijasiz", "Yakunlangan, natija kiritilmagan"),
            ("masulsiz", "Mas’ul xodim belgilanmagan"),
        ],
    )
    claim_min = forms.DecimalField(label="Da’vo summasi (dan)", required=False)
    claim_max = forms.DecimalField(label="Da’vo summasi (gacha)", required=False)
    cancelled = forms.BooleanField(label="Bekor qilinganlarni ko‘rsatish", required=False)
    sort = forms.ChoiceField(
        required=False, label="Saralash",
        choices=[("-created_at", "Avval yangilari"), ("created_at", "Avval eskilari"), ("next_hearing_at", "Yaqin majlis bo‘yicha"),
                 ("-last_activity_at", "Oxirgi faollik"), ("case_number", "Ish raqami"), ("-claim_amount", "Da’vo summasi")],
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        orgs = Organization.objects.order_by("full_name")
        users = User.objects.filter(is_active=True).order_by("last_name", "first_name")
        if user is not None:
            scope = user.scope_organization_ids()
            if scope is not None:
                orgs = orgs.filter(pk__in=scope)
                users = users.filter(Q(organization_id__in=scope) | Q(responsible_cases__organization_id__in=scope)).distinct()
        self.fields["organization"].queryset = orgs
        self.fields["responsible"].queryset = users
        labels = {
            "org_type": "Tashkilot turi", "region": "Hudud", "court_type": "Sud turi", "instance": "Sud instansiyasi (bosqichi)",
            "category": "Ish turi (turkumi)", "status": "Ish holati", "outcome": "Ish natijasi",
        }
        for name, label in labels.items():
            self.fields[name].label = label

    def active_filters(self):
        """Tanlangan filtrlar tavsifi (hisobot sarlavhasi uchun)."""
        if not self.is_valid():
            return []
        result = []
        for name, value in self.cleaned_data.items():
            if value in (None, "", False) or name in ("sort",):
                continue
            field = self.fields[name]
            if isinstance(field, forms.ChoiceField) and not isinstance(field, forms.ModelChoiceField):
                value = dict(field.choices).get(value, value)
            elif hasattr(value, "strftime"):
                value = value.strftime("%d.%m.%Y")
            elif value is True:
                value = "ha"
            result.append((field.label, str(value)))
        return result


def _period_start(period):
    today = timezone.localdate()
    if period == "today":
        return today
    if period == "week":
        return today - timedelta(days=today.weekday())
    if period == "month":
        return today.replace(day=1)
    if period == "quarter":
        return today.replace(month=(today.month - 1) // 3 * 3 + 1, day=1)
    if period == "year":
        return today.replace(month=1, day=1)
    return None


def _text(qs, field, value):
    for word in value.split():
        qs = qs.filter(**{f"{field}__icontains": word})
    return qs


def apply_filters(qs, data):
    """Tozalangan filtr qiymatlarini QuerySet'ga qo'llaydi."""
    d = data or {}
    if not d.get("cancelled"):
        qs = qs.filter(is_cancelled=False)
    if d.get("q"):
        for word in d["q"].split():
            qs = qs.filter(
                Q(case_number__icontains=word) | Q(reg_number__icontains=word) | Q(plaintiffs__icontains=word)
                | Q(defendants__icontains=word) | Q(third_parties__icontains=word) | Q(subject__icontains=word)
                | Q(organization__full_name__icontains=word) | Q(organization__short_name__icontains=word)
                | Q(judge__icontains=word) | Q(court__name__icontains=word)
            )
    if d.get("case_number"):
        key = normalize_case_number(d["case_number"])
        qs = qs.filter(Q(case_number_key__icontains=key) | Q(stages__case_number__icontains=d["case_number"].strip())).distinct()
    if d.get("organization"):
        org = d["organization"]
        ids = org.descendant_ids() if d.get("include_children") else [org.pk]
        qs = qs.filter(organization_id__in=ids)
    simple = {
        "org_type": "organization__org_type", "region": "organization__region", "court_type": "court__court_type",
        "court": "court", "instance": "instance", "category": "category", "role": "role", "responsible": "responsible",
        "status": "status", "outcome": "outcome", "agency_result": "agency_result", "review_status": "review_status",
        "source": "source",
    }
    for key, lookup in simple.items():
        if d.get(key):
            qs = qs.filter(**{lookup: d[key]})
    if d.get("plaintiff"):
        qs = _text(qs, "plaintiffs", d["plaintiff"])
    if d.get("defendant"):
        qs = _text(qs, "defendants", d["defendant"])
    if d.get("third_party"):
        qs = _text(qs, "third_parties", d["third_party"])
    if d.get("state") == "open":
        qs = qs.filter(status__is_final=False)
    elif d.get("state") == "closed":
        qs = qs.filter(status__is_final=True)
    if d.get("hearing_from"):
        qs = qs.filter(hearings__scheduled_at__date__gte=d["hearing_from"]).distinct()
    if d.get("hearing_to"):
        qs = qs.filter(hearings__scheduled_at__date__lte=d["hearing_to"]).distinct()
    if d.get("created_from"):
        qs = qs.filter(created_at__date__gte=d["created_from"])
    if d.get("created_to"):
        qs = qs.filter(created_at__date__lte=d["created_to"])
    start = _period_start(d.get("period"))
    if start:
        qs = qs.filter(created_at__date__gte=start)
    today = timezone.localdate()
    majlis = d.get("majlis")
    if majlis == "bugun":
        qs = qs.filter(hearings__scheduled_at__date=today, hearings__status="rejalashtirilgan").distinct()
    elif majlis == "hafta":
        qs = qs.filter(
            hearings__scheduled_at__date__gte=today, hearings__scheduled_at__date__lte=today + timedelta(days=7),
            hearings__status="rejalashtirilgan",
        ).distinct()
    elif majlis == "kelgusi":
        qs = qs.filter(next_hearing_at__isnull=False)
    elif majlis == "yoq":
        qs = qs.filter(next_hearing_at__isnull=True, status__is_final=False)
    nazorat = d.get("nazorat")
    if nazorat == "yaqin":
        qs = qs.filter(
            deadlines__is_done=False, deadlines__due_date__gte=today,
            deadlines__due_date__lte=today + timedelta(days=settings.DEADLINE_REMINDER_DAYS),
        ).distinct()
    elif nazorat == "otgan":
        qs = qs.filter(deadlines__is_done=False, deadlines__due_date__lt=today).distinct()
    elif nazorat == "yangilanmagan":
        qs = qs.filter(status__is_final=False, last_activity_at__lt=timezone.now() - timedelta(days=settings.STALE_CASE_DAYS))
    elif nazorat == "natijasiz":
        qs = qs.filter(status__code="yakunlangan", outcome__isnull=True)
    elif nazorat == "masulsiz":
        qs = qs.filter(responsible__isnull=True, status__is_final=False)
    if d.get("claim_min") is not None:
        qs = qs.filter(claim_amount__gte=d["claim_min"])
    if d.get("claim_max") is not None:
        qs = qs.filter(claim_amount__lte=d["claim_max"])
    return qs


def filtered_cases(request, base_qs=None):
    """So'rov parametrlari bo'yicha foydalanuvchi ko'ra oladigan ishlar va filtr formasi."""
    form = CaseFilterForm(request.GET or None, user=request.user)
    qs = (base_qs if base_qs is not None else Case.objects.all()).visible_to(request.user)
    data = form.cleaned_data if form.is_valid() else {}
    qs = apply_filters(qs, data)
    sort = data.get("sort") or "-created_at"
    if sort == "next_hearing_at":
        from django.db.models import F

        qs = qs.order_by(F("next_hearing_at").asc(nulls_last=True), "-created_at")
    else:
        qs = qs.order_by(sort, "-id")
    return form, qs
