"""Muddatlar va sud majlislari bo'yicha avtomatik eslatmalar (3.5 va 5-bo'limlar)."""
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from cases.models import Case, Deadline, Hearing, HearingStatus

from .models import NotificationKind
from .services import notify_case


def send_reminders():
    now = timezone.now()
    stats = {"hearings": 0, "deadlines_soon": 0, "overdue": 0, "stale": 0}

    # Navbatdagi majlis sanasi o'tib ketgan kartochkalarni yangilash
    for case in Case.objects.filter(next_hearing_at__lt=now):
        case.refresh_next_hearing()

    hearings = Hearing.objects.filter(
        status=HearingStatus.SCHEDULED, case__is_cancelled=False,
        scheduled_at__gte=now, scheduled_at__lte=now + timedelta(days=settings.HEARING_REMINDER_DAYS),
    ).select_related("case", "case__organization", "responsible")
    for h in hearings:
        local = timezone.localtime(h.scheduled_at)
        sent = notify_case(
            h.case, NotificationKind.HEARING_SOON,
            f"Sud majlisi yaqinlashmoqda: {h.case.case_number} — {local:%d.%m.%Y %H:%M}",
            f"{h.case.court or ''} {h.location}".strip(),
            extra=[h.responsible] if h.responsible_id else None,
            dedup_key=f"hearing-{h.pk}-{local:%Y%m%d%H%M}",
        )
        stats["hearings"] += len(sent)

    for d in Deadline.objects.upcoming().select_related("case", "responsible"):
        sent = notify_case(
            d.case, NotificationKind.DEADLINE_SOON,
            f"Muddat yaqinlashmoqda: {d.title} — {d.due_date:%d.%m.%Y}",
            f"Sud ishi: {d.case.case_number}. {d.get_kind_display()}.",
            extra=[d.responsible] if d.responsible_id else None,
            dedup_key=f"deadline-soon-{d.pk}-{d.due_date:%Y%m%d}",
        )
        stats["deadlines_soon"] += len(sent)

    for d in Deadline.objects.overdue().select_related("case", "responsible"):
        sent = notify_case(
            d.case, NotificationKind.OVERDUE,
            f"Muddat o‘tib ketdi: {d.title} — {d.due_date:%d.%m.%Y}",
            f"Sud ishi: {d.case.case_number}. Zudlik bilan choralar ko‘ring.",
            include_legal=True, extra=[d.responsible] if d.responsible_id else None,
            dedup_key=f"deadline-overdue-{d.pk}-{d.due_date:%Y%m%d}",
        )
        stats["overdue"] += len(sent)

    for case in Case.objects.valid().stale().select_related("organization", "responsible"):
        sent = notify_case(
            case, NotificationKind.STALE,
            f"Sud ishi uzoq muddat yangilanmagan: {case.case_number}",
            f"Oxirgi o‘zgarish: {timezone.localtime(case.last_activity_at):%d.%m.%Y}. Ma’lumotlarni dolzarblashtiring.",
            dedup_key=f"stale-{case.pk}-{case.last_activity_at:%Y%m%d}",
        )
        stats["stale"] += len(sent)
    return stats
