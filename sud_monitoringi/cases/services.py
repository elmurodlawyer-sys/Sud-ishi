"""Sud ishlari bo'yicha biznes mantiq: tarix, holat/bosqich o'zgarishi, tasdiqlash, bekor qilish.

Veb-interfeys ham, integratsiya moduli ham shu funksiyalardan foydalanadi, shuning
uchun barcha o'zgarishlar bir xil tartibda tarixga yoziladi va xabarnoma yuboriladi.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from core.models import Classifier, ClassifierKind
from core.normalize import normalize_case_number
from notifications.models import NotificationKind
from notifications.services import notify, notify_case

from .models import Case, CaseEvent, CaseStage, EventType, HearingStatus, ReviewStatus, StatusCode

TRACKED_FIELDS = [
    "case_number", "organization", "role", "other_system_orgs", "plaintiffs", "defendants", "third_parties",
    "court", "instance", "category", "subject", "claim_amount", "judge", "filed_date", "responsible", "status",
    "outcome", "outcome_date", "agency_result", "awarded_amount", "outcome_note", "source_url",
]

INSTANCE_TO_STATUS = {
    "apellyatsiya": StatusCode.APPEAL,
    "kassatsiya": StatusCode.CASSATION,
    "taftish": StatusCode.OTHER_REVIEW,
    "boshqa": StatusCode.OTHER_REVIEW,
}

# Sud majlisi tayinlanganda holat avtomatik o'zgarishi mumkin bo'lgan holatlar
AUTO_HEARING_STATUSES = {
    StatusCode.NEW, StatusCode.CLARIFYING, StatusCode.IN_PROGRESS, StatusCode.HEARING_POSTPONED, StatusCode.HEARING_SET,
}


def _display(case, field):
    value = getattr(case, field)
    if value is None or value == "":
        return ""
    model_field = Case._meta.get_field(field)
    if model_field.choices:
        return str(getattr(case, f"get_{field}_display")())
    if isinstance(value, Decimal):
        return f"{value:,.2f}".replace(",", " ")
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    return str(value)


def snapshot(case):
    return {f: _display(case, f) for f in TRACKED_FIELDS}


def diff(old, new):
    changes = []
    for field in TRACKED_FIELDS:
        if old.get(field, "") != new.get(field, ""):
            changes.append({
                "field": field,
                "label": str(Case._meta.get_field(field).verbose_name),
                "old": old.get(field, ""),
                "new": new.get(field, ""),
            })
    return changes


def record_event(case, user, event_type, description, changes=None, comment=""):
    event = CaseEvent.objects.create(
        case=case, user=user, event_type=event_type, description=description[:1000], changes=changes or [], comment=comment
    )
    now = timezone.now()
    Case.objects.filter(pk=case.pk).update(last_activity_at=now)
    case.last_activity_at = now
    return event


def status_by_code(code):
    return Classifier.get(ClassifierKind.CASE_STATUS, code)


def find_duplicate(case_number, court, organization=None, exclude_pk=None):
    """Takroriy kartochkani aniqlaydi (bir sud ishi — bitta kartochka)."""
    key = normalize_case_number(case_number)
    if not key:
        return None
    qs = Case.objects.valid().filter(case_number_key=key)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if court is not None:
        qs = qs.filter(court=court)
    elif organization is not None:
        qs = qs.filter(court__isnull=True, organization=organization)
    dup = qs.first()
    if dup is None:
        # Ish boshqa bosqichdagi raqami bilan ro'yxatda bo'lishi mumkin
        stage_qs = CaseStage.objects.filter(case__is_cancelled=False, case_number__iexact=case_number.strip())
        if court is not None:
            stage_qs = stage_qs.filter(court=court)
        if exclude_pk:
            stage_qs = stage_qs.exclude(case_id=exclude_pk)
        stage = stage_qs.select_related("case").first()
        dup = stage.case if stage else None
    return dup


def ensure_stage(case, user, comment=""):
    """Joriy instansiya uchun ochiq bosqich bo'lmasa, uni yaratadi va oldingisini yopadi."""
    if not case.instance_id:
        return None
    open_stage = case.stages.filter(ended_on__isnull=True).order_by("-started_on", "-id").first()
    if open_stage and open_stage.instance_id == case.instance_id:
        return open_stage
    today = timezone.localdate()
    if open_stage:
        open_stage.ended_on = today
        open_stage.save(update_fields=["ended_on"])
    return CaseStage.objects.create(
        case=case, instance=case.instance, court=case.court, case_number=case.case_number, judge=case.judge,
        started_on=today, note=comment, created_by=user,
    )


@transaction.atomic
def register_case(case, user, comment="", notify_users=True):
    """Yangi kartochkani saqlaydi, tarixga yozadi va xabarnoma yuboradi."""
    case.created_by = user
    if not case.status_id:
        case.status = status_by_code(StatusCode.NEW)
    case.save()
    ensure_stage(case, user)
    record_event(case, user, EventType.CREATED, "Sud ishi kartochkasi yaratildi", comment=comment)
    if notify_users:
        notify_case(
            case,
            NotificationKind.NEW_CASE,
            f"Yangi sud ishi: {case.case_number}",
            f"{case.organization} — {case.get_role_display().lower()} sifatida. Sud: {case.court or '—'}.",
            include_legal=True,
            exclude=user,
        )
    return case


@transaction.atomic
def apply_changes(
    case, user, old_snapshot, comment="", event_type=EventType.UPDATED, via_integration=False, notify_users=True
):
    """Kartochka o'zgarishlarini saqlaydi va tarix/xabarnomalarni shakllantiradi.

    `case` allaqachon yangi qiymatlar bilan saqlangan bo'lishi kerak.
    """
    new_snapshot = snapshot(case)
    changes = diff(old_snapshot, new_snapshot)
    if not changes:
        return []
    changed = {c["field"] for c in changes}
    description = "Ma’lumotlar o‘zgartirildi: " + ", ".join(c["label"] for c in changes)
    if via_integration:
        description = "Integratsiya manbasidan yangilandi: " + ", ".join(c["label"] for c in changes)
    record_event(case, user, event_type, description, changes, comment)

    if "instance" in changed:
        ensure_stage(case, user, comment)
        record_event(
            case, user, EventType.STAGE,
            f"Sud bosqichi: {old_snapshot['instance'] or '—'} → {new_snapshot['instance'] or '—'}", comment=comment,
        )
    if "status" in changed:
        record_event(
            case, user, EventType.STATUS,
            f"Ish holati: {old_snapshot['status'] or '—'} → {new_snapshot['status'] or '—'}", comment=comment,
        )
    if not notify_users:
        return changes
    if "instance" in changed or "status" in changed:
        finished = case.is_closed and case.status.code == StatusCode.FINISHED
        notify_case(
            case,
            NotificationKind.FINISHED if finished else NotificationKind.STATUS,
            f"{'Ish yakunlandi' if finished else 'Ish holati o‘zgardi'}: {case.case_number}",
            f"Holat: {new_snapshot['status']}. Bosqich: {new_snapshot['instance'] or '—'}.",
            include_legal=finished,
            exclude=user,
        )
    elif via_integration:
        notify_case(
            case, NotificationKind.NEW_INFO, f"Sud ishi bo‘yicha yangi ma’lumot: {case.case_number}", description,
            include_legal=True,
        )
    if "responsible" in changed and case.responsible_id and case.responsible != user:
        notify(
            [case.responsible], NotificationKind.ASSIGNED, f"Sizga sud ishi biriktirildi: {case.case_number}",
            f"{case.organization}. Sud: {case.court or '—'}.", case=case,
        )
    if "organization" in changed:
        notify_case(
            case, NotificationKind.ASSIGNED, f"Sud ishi tashkilotingizga biriktirildi: {case.case_number}",
            f"Protsessual maqom: {case.get_role_display()}.", exclude=user,
        )
    return changes


def set_status(case, user, code, comment="", via_integration=False, notify_users=True):
    status = status_by_code(code)
    if status is None or case.status_id == status.pk:
        return []
    old = snapshot(case)
    case.status = status
    case.save()
    return apply_changes(case, user, old, comment, via_integration=via_integration, notify_users=notify_users)


def after_hearing_change(
    case, hearing, user, created, old_scheduled_at=None, via_integration=False, notify_users=True
):
    """Sud majlisi qo'shilganda/o'zgarganda holat, tarix va xabarnomalar."""
    local = timezone.localtime(hearing.scheduled_at)
    if created:
        description = f"Sud majlisi belgilandi: {local:%d.%m.%Y %H:%M}"
    elif old_scheduled_at and old_scheduled_at != hearing.scheduled_at:
        description = (
            f"Sud majlisi sanasi o‘zgardi: {timezone.localtime(old_scheduled_at):%d.%m.%Y %H:%M} → {local:%d.%m.%Y %H:%M}"
        )
    else:
        description = f"Sud majlisi ({local:%d.%m.%Y %H:%M}) ma’lumotlari yangilandi: {hearing.get_status_display()}"
        if hearing.result_id:
            description += f", natija: {hearing.result}"
    record_event(case, user, EventType.HEARING, description, comment=hearing.result_note)
    case.refresh_next_hearing()

    current = case.status.code if case.status_id else ""
    if current in AUTO_HEARING_STATUSES:
        if hearing.status == HearingStatus.SCHEDULED and case.next_hearing_at:
            set_status(
                case, user, StatusCode.HEARING_SET, "Sud majlisi tayinlanganligi sababli avtomatik",
                via_integration, notify_users=False,
            )
        elif hearing.status == HearingStatus.POSTPONED:
            set_status(
                case, user, StatusCode.HEARING_POSTPONED, "Sud majlisi qoldirilganligi sababli avtomatik",
                via_integration, notify_users=False,
            )

    if notify_users and (created or (old_scheduled_at and old_scheduled_at != hearing.scheduled_at)):
        extra = [hearing.responsible] if hearing.responsible_id else None
        notify_case(
            case, NotificationKind.HEARING_SET, f"Sud majlisi: {case.case_number} — {local:%d.%m.%Y %H:%M}", description,
            extra=extra, exclude=user,
        )


# --- Tasdiqlash / qaytarish / bekor qilish / arxiv ---------------------------------

def submit_for_review(case, user):
    case.review_status = ReviewStatus.PENDING
    case.save(update_fields=["review_status", "updated_at"])
    record_event(case, user, EventType.REVIEW, "Ma’lumotlar Yuridik bo‘lim tasdig‘iga yuborildi")
    from notifications.services import legal_users
    notify(
        legal_users(), NotificationKind.REVIEW, f"Tasdiqlash so‘ralmoqda: {case.case_number}",
        f"{case.organization} tomonidan kiritilgan ma’lumotlar tasdiqlashni kutmoqda.", case=case,
    )


def approve(case, user, comment=""):
    case.review_status = ReviewStatus.APPROVED
    case.review_comment = comment
    case.save(update_fields=["review_status", "review_comment", "updated_at"])
    record_event(case, user, EventType.REVIEW, "Ma’lumotlar Yuridik bo‘lim tomonidan tasdiqlandi", comment=comment)


def return_for_clarification(case, user, comment):
    case.review_status = ReviewStatus.RETURNED
    case.review_comment = comment
    case.save(update_fields=["review_status", "review_comment", "updated_at"])
    record_event(case, user, EventType.REVIEW, "Ma’lumotlar aniqlashtirish uchun qaytarildi", comment=comment)
    clarifying = status_by_code(StatusCode.CLARIFYING)
    if clarifying and case.status.code in (StatusCode.NEW,):
        set_status(case, user, StatusCode.CLARIFYING, comment)
    notify_case(
        case, NotificationKind.RETURNED, f"Aniqlashtirish uchun qaytarildi: {case.case_number}", comment, exclude=user,
    )


def cancel(case, user, reason):
    case.is_cancelled = True
    case.cancel_reason = reason
    case.cancelled_by = user
    case.cancelled_at = timezone.now()
    case.save()
    record_event(case, user, EventType.CANCELLED, "Kartochka bekor qilindi (noto‘g‘ri yoki takroriy yozuv)", comment=reason)


def restore(case, user, reason):
    dup = find_duplicate(case.case_number, case.court, case.organization, exclude_pk=case.pk)
    if dup is not None:
        raise ValueError(f"Tiklab bo‘lmaydi: shu ish bo‘yicha faol kartochka mavjud ({dup.reg_number}).")
    case.is_cancelled = False
    case.save()
    record_event(case, user, EventType.RESTORED, "Kartochka qayta tiklandi", comment=reason)


def archive(case, user, reason):
    old = snapshot(case)
    case.status = status_by_code(StatusCode.ARCHIVED)
    case.archive_reason = reason
    case.save()
    apply_changes(case, user, old, reason)
    record_event(case, user, EventType.ARCHIVED, "Ish arxivga olindi", comment=reason)
