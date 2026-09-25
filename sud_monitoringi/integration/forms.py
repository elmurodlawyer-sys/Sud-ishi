import json

from django import forms

from cases.forms import BootstrapMixin

from .models import IntegrationSource


class SourceForm(BootstrapMixin, forms.ModelForm):
    new_token = forms.CharField(
        label="Kirish kaliti (token)", required=False, widget=forms.PasswordInput(render_value=False),
        help_text="Faqat yangi kalit kiritilganda almashtiriladi. O‘chirish uchun “-” kiriting.",
    )
    config_text = forms.CharField(
        label="Qo‘shimcha sozlamalar (JSON)", required=False, widget=forms.Textarea(attrs={"rows": 10, "class": "font-monospace"}),
    )

    class Meta:
        model = IntegrationSource
        fields = ["name", "adapter", "base_url", "interval_minutes", "is_active"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["config_text"].initial = json.dumps(self.instance.config or {}, ensure_ascii=False, indent=2)
        self._style()

    def clean_config_text(self):
        text = self.cleaned_data.get("config_text") or "{}"
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"JSON xato: {exc}")
        if not isinstance(value, dict):
            raise forms.ValidationError("Sozlamalar JSON obyekt ({...}) bo‘lishi kerak.")
        return value

    def save(self, commit=True):
        source = super().save(commit=False)
        source.config = self.cleaned_data["config_text"]
        token = self.cleaned_data.get("new_token")
        if token == "-":
            source.auth_token = ""
        elif token:
            source.auth_token = token
        if commit:
            source.save()
        return source


class FileImportForm(BootstrapMixin, forms.Form):
    file = forms.FileField(label="Fayl (JSON, CSV yoki XLSX)")
    source_name = forms.CharField(label="Manba nomi", initial="Fayldan import", max_length=255)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style()
