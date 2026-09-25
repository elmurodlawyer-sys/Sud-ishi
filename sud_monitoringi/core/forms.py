from django import forms
from django.db.models import Q

from cases.forms import BootstrapMixin

from .models import Classifier, ClassifierKind, Court, Organization


class OrganizationForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Organization
        fields = [
            "full_name", "short_name", "stir", "org_type", "region", "district", "parent", "previous_names", "alt_names",
            "is_active",
        ]
        widgets = {"previous_names": forms.Textarea(attrs={"rows": 3}), "alt_names": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        inst = self.instance
        self.fields["org_type"].queryset = Classifier.objects.filter(kind=ClassifierKind.ORG_TYPE).filter(
            Q(is_active=True) | Q(pk=inst.org_type_id)
        )
        self.fields["region"].queryset = Classifier.objects.filter(kind=ClassifierKind.REGION).filter(
            Q(is_active=True) | Q(pk=inst.region_id)
        )
        parents = Organization.objects.order_by("full_name")
        if inst.pk:
            parents = parents.exclude(pk__in=inst.descendant_ids())
        self.fields["parent"].queryset = parents
        self._style()


class ClassifierForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Classifier
        fields = ["kind", "code", "name", "order", "is_active", "is_final", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["kind"].disabled = True
            if self.instance.is_system:
                self.fields["code"].disabled = True
                self.fields["is_final"].disabled = True
                self.fields["is_active"].disabled = True
        self.fields["code"].help_text = "Lotin harflari, raqam va chiziqcha. Masalan: mehnat_nizolari"
        self._style()

    def clean(self):
        data = super().clean()
        kind, code = data.get("kind") or self.instance.kind, data.get("code")
        if kind and code and Classifier.objects.filter(kind=kind, code=code).exclude(pk=self.instance.pk).exists():
            self.add_error("code", "Ushbu turdagi klassifikatorda bunday kod mavjud.")
        return data


class CourtForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Court
        fields = ["name", "court_type", "region", "address", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["court_type"].queryset = Classifier.objects.filter(kind=ClassifierKind.COURT_TYPE)
        self.fields["region"].queryset = Classifier.objects.filter(kind=ClassifierKind.REGION)
        self._style()


class ImportForm(BootstrapMixin, forms.Form):
    file = forms.FileField(label="Excel fayl (.xlsx)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
