"""Integratsiya jarayoni: yozuvlarni olish, solishtirish, kartochka yaratish/yangilash (3.2-band)."""
import hashlib
import json
import logging
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from cases import services as case_services
from cases.models import Case, CaseSource, Hearing, HearingStatus
from core.models import Court
from core.normalize import normalize_case_number, normalize_name

from .adapters import AdapterError, get_adapter, parse_datetime_value
from .matching import OrganizationMatcher, category_from_text, court_type_from_text, instance_from_text, region_from_text
from .models import ExternalRecord, IntegrationRun, RunStatus

logger = logging.getLogger(__name__)


def record_hash(record):
    payload = {k: v for k, v in record.items() if k != "external_key"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def external_key(record):
    if record.get("external_key"):
        return record["external_key"][:500]
    return f"{normalize_case_number(record.get('case_number'))}|{normalize_name(record.get('court_name'))}"[:500]


def parse_amount(value):
    if not value:
        return None
    text = str(value).replace("\xa0", "").replace(" ", "").replace(",", ".")
    text = "".join(ch for ch in text if ch.isdigit() or ch == ".")
    if text.count(".") > 1:
        head, _, tail = text.rpartition(".")
        text = head.replace(".", "") + "." + tail
    try:
        return Decimal(text) if text else None
    except InvalidOperation:
        return None


def get_or_create_court(record):
    name = (record.get("court_name") or "").strip()
    if not name:
        return None
    key = normalize_name(name)
    court = Court.objects.filter(name_key=key).first()
    if court is None:
        court = Court.objects.create(
            name=name,
            court_type=court_type_from_text(record.get("court_type") or name),
            region=region_from_text(record.get("region") or name),
        )
    return court


def _sync_hearing(case, record, user=None, notify_users=True):
    """Manbadagi majlis sanasini kartochkaga kiritadi. O'zgarish bo'lsa True qaytaradi."""
    hearing_at = parse_datetime_value(record.get("hearing_at"))
    if hearing_at is None:
        return False
    window = timedelta(minutes=1)
    if case.hearings.filter(scheduled_at__gte=hearing_at - window, scheduled_at__lte=hearing_at + window).exists():
        return False
    # Manbadan olingan, hali o'tmagan majlis sanasi o'zgargan bo'lsa — uni ko'chiramiz
    existing = (
        case.hearings.filter(source=CaseSource.INTEGRATION, status=HearingStatus.SCHEDULED, scheduled_at__gte=timezone.now())
        .order_by("scheduled_at")
        .first()
    )
    if existing is not None and hearing_at >= timezone.now():
        old = existing.scheduled_at
        existing.scheduled_at = hearing_at
        existing.location = record.get("location") or existing.location
        existing.save()
        case_services.after_hearing_change(
            case, existing, user, created=False, old_scheduled_at=old, via_integration=True, notify_users=notify_users
        )
        return True
    hearing = Hearing.objects.create(
        case=case,
        stage=case.stages.filter(ended_on__isnull=True).last(),
        scheduled_at=hearing_at,
        location=record.get("location", ""),
        status=HearingStatus.SCHEDULED if hearing_at >= timezone.now() else HearingStatus.HELD,
        source=CaseSource.INTEGRATION,
        responsible=case.responsible,
    )
    case_services.after_hearing_change(
        case, hearing, user, created=True, via_integration=True, notify_users=notify_users
    )
    return True


def _other_orgs_text(match):
    return "\n".join(f"{m.organization.full_name} ({dict(Case._meta.get_field('role').choices)[m.role]})" for m in match.others)


def _create_case(source, record, match, court, user=None):
    now = timezone.now()
    case = Case(
        case_number=record["case_number"],
        organization=match.primary.organization,
        role=match.primary.role,
        other_system_orgs=_other_orgs_text(match),
        plaintiffs=record.get("plaintiffs", ""),
        defendants=record.get("defendants", ""),
        third_parties=record.get("third_parties", ""),
        court=court,
        instance=instance_from_text(record.get("instance", "")),
        category=category_from_text(record.get("category", "")),
        subject=record.get("subject", ""),
        claim_amount=parse_amount(record.get("claim_amount")),
        judge=record.get("judge", ""),
        source=CaseSource.INTEGRATION,
        source_name=source.name,
        source_url=record.get("url", "")[:1000],
        source_fetched_at=now,
        source_updated_at=now,
    )
    case_services.register_case(case, user, comment=f"Manba: {source.name}")
    # Yangi ish haqidagi xabarnoma yuborilgan; majlis bo'yicha alohida xabar shart emas
    _sync_hearing(case, record, user, notify_users=False)
    return case


def _update_case(source, case, record, match, court, user=None):
    """Manbadagi yangi qiymatlarni kartochkaga kiritadi; foydalanuvchi kiritgan qiymatlar ustidan yozilmaydi."""
    old = case_services.snapshot(case)
    overwrite = {
        "plaintiffs": record.get("plaintiffs"),
        "defendants": record.get("defendants"),
        "third_parties": record.get("third_parties"),
        "judge": record.get("judge"),
    }
    for field_name, value in overwrite.items():
        if value:
            setattr(case, field_name, value)
    if court and case.court_id != court.pk and not case_services.find_duplicate(case.case_number, court, exclude_pk=case.pk):
        case.court = court
    fill_if_empty = {
        "subject": record.get("subject"),
        "claim_amount": parse_amount(record.get("claim_amount")),
        "source_url": (record.get("url") or "")[:1000],
    }
    for field_name, value in fill_if_empty.items():
        if value and not getattr(case, field_name):
            setattr(case, field_name, value)
    if not case.category_id and record.get("category"):
        case.category = category_from_text(record["category"])
    if record.get("instance"):
        instance = instance_from_text(record["instance"])
        if instance and instance.pk != case.instance_id and instance.code != "birinchi":
            case.instance = instance
            code = case_services.INSTANCE_TO_STATUS.get(instance.code)
            if code and not case.is_closed:
                case.status = case_services.status_by_code(code)
    if match and match.others:
        case.other_system_orgs = _other_orgs_text(match)
    case.source_updated_at = timezone.now()
    case.save()
    changes = case_services.apply_changes(case, user, old, comment=f"Manba: {source.name}", via_integration=True)
    hearing_changed = _sync_hearing(case, record, user)
    return bool(changes) or hearing_changed


def process_records(source, records, run, user=None):
    """Yozuvlarni qayta ishlaydi. Har bir yozuv alohida tranzaksiyada — bittasidagi xato boshqalarga ta'sir qilmaydi."""
    matcher = OrganizationMatcher()
    errors = []
    for record in records:
        run.fetched += 1
        try:
            with transaction.atomic():
                if not record.get("case_number"):
                    continue
                key = external_key(record)
                digest = record_hash(record)
                ext = ExternalRecord.objects.filter(source=source, external_key=key).select_related("case").first()
                linked = ext.case if ext and ext.case and not ext.case.is_cancelled else None
                if ext and ext.data_hash == digest and linked:
                    run.matched += 1
                    run.unchanged += 1
                    ext.save(update_fields=["last_seen_at"])
                    continue
                match = matcher.match(record)
                if match is None and linked is None:
                    continue
                run.matched += 1
                court = get_or_create_court(record)
                case = linked or case_services.find_duplicate(
                    record["case_number"], court, match.primary.organization if match else None
                )
                if case is None:
                    case = _create_case(source, record, match, court, user)
                    run.created += 1
                elif _update_case(source, case, record, match, court, user):
                    run.updated += 1
                else:
                    run.unchanged += 1
                if ext is None:
                    ext = ExternalRecord(source=source, external_key=key)
                if ext.data_hash and ext.data_hash != digest:
                    ext.last_changed_at = timezone.now()
                ext.data, ext.data_hash, ext.case = record, digest, case
                ext.save()
        except Exception as exc:  # noqa: BLE001 - har bir yozuv xatosi jurnalga yoziladi
            logger.exception("Integratsiya yozuvini qayta ishlashda xato")
            errors.append(f"{record.get('case_number', '?')}: {exc}")
    return errors


def run_source(source, user=None, records=None):
    """Manbani tekshiradi. Tashqi manba ishlamasa ham tizim o'z ma'lumotlari bilan ishlashda davom etadi."""
    run = IntegrationRun.objects.create(source=source, triggered_by=user)
    errors = []
    try:
        if records is None:
            records = list(get_adapter(source).fetch())
        errors = process_records(source, records, run, user)
        run.status = RunStatus.PARTIAL if errors else RunStatus.SUCCESS
    except AdapterError as exc:
        errors.append(str(exc))
        run.status = RunStatus.FAILED
    except Exception as exc:  # noqa: BLE001
        logger.exception("Integratsiya manbasini tekshirishda kutilmagan xato")
        errors.append(f"Kutilmagan xato: {exc}")
        run.status = RunStatus.FAILED
    run.errors = "\n".join(errors)[:20000]
    run.finished_at = timezone.now()
    run.save()

    source.last_run_at = run.finished_at
    if run.status != RunStatus.FAILED:
        source.last_success_at = run.finished_at
    source.last_status = (
        f"{run.get_status_display()}: olingan {run.fetched}, mos {run.matched}, yangi {run.created}, yangilangan {run.updated}"
    )
    source.save(update_fields=["last_run_at", "last_success_at", "last_status"])
    return run


def due_sources(now=None):
    from .models import IntegrationSource

    now = now or timezone.now()
    for source in IntegrationSource.objects.filter(is_active=True).exclude(adapter="file"):
        if source.last_run_at is None or source.last_run_at + timedelta(minutes=source.interval_minutes) <= now:
            yield source
