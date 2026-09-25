import os

from django import forms
from django.conf import settings
from django.db.models import Q

from accounts.models import User
from core.models import Classifier, ClassifierKind, Court, Organization

from . import services
from .models import Case, CaseDocument, CaseStage, Deadline, Hearing, StatusCode


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%dT%H:%M", **kwargs)


def _active_classifiers(field, kind, current=None):
    qs = Classifier.objects.filter(kind=kind).filter(Q(is_active=True) | Q(pk=getattr(current, "pk", None)))
    field.queryset = qs.order_by("order", "name")


def scoped_users(user):
    qs = User.objects.filter(is_active=True)
    scope = user.scope_organization_ids()
    if scope is not None:
        qs = qs.filter(organization_id__in=scope)
    return qs.order_by("last_name", "first_name")


class BootstrapMixin:
    def _style(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput,)):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")
            if isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("rows", 2)


class CaseForm(BootstrapMixin, forms.ModelForm):
    change_comment = forms.CharField(
        label="O‘zgartirish izohi",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
        help_text="Holat yoki sud bosqichi o‘zgartirilganda majburiy.",
    )

    class Meta:
        model = Case
        fields = [
            "case_number", "organization", "role", "plaintiffs", "defendants", "third_parties", "court", "instance",
            "category", "subject", "claim_amount", "judge", "filed_date", "responsible", "status", "outcome", "outcome_date",
            "agency_result", "awarded_amount", "outcome_note", "source_url",
        ]
        widgets = {
            "filed_date": DateInput(),
            "outcome_date": DateInput(),
            "subject": forms.Textarea(attrs={"rows": 3}),
            "outcome_note": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        instance = self.instance
        orgs = Organization.objects.filter(Q(is_active=True) | Q(pk=instance.organization_id))
        scope = user.scope_organization_ids()
        if scope is not None:
            orgs = orgs.filter(pk__in=scope)
        self.fields["organization"].queryset = orgs.order_by("full_name")
        self.fields["court"].queryset = Court.objects.filter(Q(is_active=True) | Q(pk=instance.court_id)).order_by("name")
        self.fields["responsible"].queryset = scoped_users(user)
        _active_classifiers(self.fields["instance"], ClassifierKind.INSTANCE, instance.instance if instance.instance_id else None)
        _active_classifiers(self.fields["category"], ClassifierKind.CASE_CATEGORY, instance.category if instance.category_id else None)
        _active_classifiers(self.fields["outcome"], ClassifierKind.OUTCOME, instance.outcome if instance.outcome_id else None)
        status_qs = Classifier.objects.filter(kind=ClassifierKind.CASE_STATUS).filter(
            Q(is_active=True) | Q(pk=instance.status_id)
        )
        if not user.is_legal:
            # Arxivga olish faqat vakolatli foydalanuvchi tomonidan, sabab ko'rsatilgan holda
            status_qs = status_qs.exclude(Q(code=StatusCode.ARCHIVED) & ~Q(pk=instance.status_id))
        self.fields["status"].queryset = status_qs.order_by("order")
        self.fields["status"].required = False
        if not instance.pk:
            self.fields["status"].help_text = "Bo‘sh qoldirilsa “Yangi aniqlangan” holati beriladi."
            self.fields.pop("change_comment")
        self._style()

    def clean(self):
        data = super().clean()
        dup = services.find_duplicate(
            data.get("case_number") or "", data.get("court"), data.get("organization"), exclude_pk=self.instance.pk
        )
        if dup is not None:
            raise forms.ValidationError(
                f"Ushbu sud ishi tizimda allaqachon ro‘yxatga olingan: {dup.reg_number} ({dup.organization}). "
                "Takroriy kartochka yaratilmaydi — mavjud kartochkadan foydalaning."
            )
        status = data.get("status")
        if status and status.code == StatusCode.FINISHED and not data.get("outcome"):
            self.add_error("outcome", "Ish yakunlangan holatga o‘tkazilganda yakuniy natija kiritilishi shart.")
        if self.instance.pk and "change_comment" in self.fields:
            changed = {"status", "instance"} & set(self.changed_data)
            if changed and not (data.get("change_comment") or "").strip():
                self.add_error("change_comment", "Holat yoki sud bosqichi o‘zgarganda izoh kiritish majburiy.")
        return data


class StageForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = CaseStage
        fields = ["instance", "court", "case_number", "judge", "started_on", "note"]
        widgets = {"started_on": DateInput(), "note": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_classifiers(self.fields["instance"], ClassifierKind.INSTANCE)
        self.fields["court"].queryset = Court.objects.filter(is_active=True).order_by("name")
        self.fields["note"].required = True
        self.fields["note"].label = "Izoh (bosqich o‘zgarishi sababi)"
        self._style()


class StageCloseForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = CaseStage
        fields = ["ended_on", "result", "note"]
        widgets = {"ended_on": DateInput(), "note": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_classifiers(self.fields["result"], ClassifierKind.OUTCOME)
        self.fields["ended_on"].required = True
        self._style()


class HearingForm(BootstrapMixin, forms.ModelForm):
    next_hearing_at = forms.DateTimeField(
        label="Keyingi sud majlisi sanasi va vaqti",
        required=False,
        widget=DateTimeInput(),
        input_formats=["%Y-%m-%dT%H:%M"],
        help_text="Majlis qoldirilgan yoki davom etsa, keyingi majlis avtomatik yaratiladi.",
    )

    class Meta:
        model = Hearing
        fields = ["scheduled_at", "location", "responsible", "status", "result", "result_note"]
        widgets = {"scheduled_at": DateTimeInput(), "result_note": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["scheduled_at"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["responsible"].queryset = scoped_users(user)
        _active_classifiers(self.fields["result"], ClassifierKind.HEARING_RESULT)
        self._style()

    def clean(self):
        data = super().clean()
        nxt, current = data.get("next_hearing_at"), data.get("scheduled_at")
        if nxt and current and nxt <= current:
            self.add_error("next_hearing_at", "Keyingi majlis joriy majlisdan keyin bo‘lishi kerak.")
        return data


class DeadlineForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Deadline
        fields = ["kind", "deadline_type", "title", "due_date", "responsible", "note"]
        widgets = {"due_date": DateInput(), "note": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        _active_classifiers(self.fields["deadline_type"], ClassifierKind.DEADLINE_TYPE)
        self.fields["responsible"].queryset = scoped_users(user)
        self._style()


class DocumentForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = CaseDocument
        fields = ["doc_type", "title", "number", "doc_date", "file", "note"]
        widgets = {"doc_date": DateInput(), "note": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _active_classifiers(self.fields["doc_type"], ClassifierKind.DOCUMENT_TYPE)
        self.fields["file"].widget.attrs["accept"] = ",".join(f".{e}" for e in settings.DOCUMENT_ALLOWED_EXTENSIONS)
        self._style()

    def clean_file(self):
        f = self.cleaned_data["file"]
        ext = os.path.splitext(f.name)[1].lower().lstrip(".")
        if ext not in settings.DOCUMENT_ALLOWED_EXTENSIONS:
            raise forms.ValidationError(
                "Ruxsat etilmagan fayl turi. Ruxsat etilganlar: " + ", ".join(settings.DOCUMENT_ALLOWED_EXTENSIONS)
            )
        if f.size > settings.DOCUMENT_MAX_SIZE_MB * 1024 * 1024:
            raise forms.ValidationError(f"Fayl hajmi {settings.DOCUMENT_MAX_SIZE_MB} MB dan oshmasligi kerak.")
        return f


class ReasonForm(BootstrapMixin, forms.Form):
    reason = forms.CharField(label="Sabab / izoh", widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, required=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["reason"].required = required
        self._style()
