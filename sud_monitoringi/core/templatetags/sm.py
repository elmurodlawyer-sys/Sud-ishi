from decimal import Decimal

from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def som(value):
    """Summani 1 234 567,89 ko'rinishida chiqaradi."""
    if value in (None, ""):
        return "—"
    try:
        value = Decimal(value)
    except Exception:  # noqa: BLE001
        return value
    text = f"{value:,.2f}".replace(",", " ").replace(".", ",")
    return text[:-3] if text.endswith(",00") else text


@register.filter
def num(value):
    if isinstance(value, Decimal):
        return som(value)
    if isinstance(value, int):
        return f"{value:,}".replace(",", " ")
    return value


@register.filter
def filesize(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


@register.filter
def days_until(value):
    if not value:
        return ""
    if hasattr(value, "date") and callable(value.date):
        value = timezone.localtime(value).date()
    delta = (value - timezone.localdate()).days
    if delta == 0:
        return "bugun"
    if delta == 1:
        return "ertaga"
    if delta > 0:
        return f"{delta} kundan so‘ng"
    return f"{-delta} kun oldin"


@register.simple_tag(takes_context=True)
def qs_replace(context, **kwargs):
    """Joriy GET parametrlarini saqlagan holda ayrimlarini almashtiradi."""
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    return "?" + params.urlencode()


STATUS_TONES = {
    "yangi": "primary", "aniqlashtirilmoqda": "warning", "korilmoqda": "info", "majlis_tayinlangan": "info",
    "majlis_qoldirilgan": "warning", "hujjat_qabul_qilingan": "secondary", "apellyatsiya": "purple",
    "kassatsiya": "purple", "qayta_korish": "purple", "yakunlangan": "success", "arxivlangan": "dark",
}


@register.filter
def status_tone(status):
    return STATUS_TONES.get(getattr(status, "code", ""), "secondary")


ROLE_TONES = {"davogar": "success", "javobgar": "danger", "uchinchi": "secondary"}


@register.filter
def role_tone(role):
    return ROLE_TONES.get(role, "secondary")
