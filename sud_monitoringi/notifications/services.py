"""Xabarnomalarni yaratish va yuborish (5-bo'lim)."""
import logging

from django.conf import settings
from django.core.mail import send_mail

from accounts.models import ORG_ROLES, Role, User

from .models import Notification

logger = logging.getLogger(__name__)


def case_org_users(case):
    """Ish tegishli bo'lgan tashkilot va uning yuqori turuvchi tashkilotlari xodimlari."""
    org_ids, node = [], case.organization
    while node is not None:
        org_ids.append(node.pk)
        node = node.parent
    return User.objects.filter(is_active=True, role__in=list(ORG_ROLES), organization_id__in=org_ids)


def legal_users():
    return User.objects.filter(is_active=True, role=Role.YURIDIK)


def recipients_for(case, include_legal=False, extra=None, exclude=None):
    users = {u.pk: u for u in case_org_users(case)}
    if case.responsible_id and case.responsible.is_active:
        users[case.responsible_id] = case.responsible
    if include_legal or not users:
        # Tashkilotda foydalanuvchi bo'lmasa, xabar Yuridik bo'limga yuboriladi — hech kim xabarsiz qolmaydi
        users.update({u.pk: u for u in legal_users()})
    for u in extra or []:
        if u is not None and u.is_active:
            users[u.pk] = u
    if exclude is not None:
        users.pop(exclude.pk, None)
    return list(users.values())


def _send_email(notification):
    user = notification.user
    if not (settings.EMAIL_NOTIFICATIONS and user.email and user.email_notifications):
        return
    link = ""
    if notification.case_id:
        link = f"\n\nSud ishi kartochkasi: {settings.SITE_URL.rstrip('/')}{notification.case.get_absolute_url()}"
    try:
        send_mail(
            f"[Sud monitoringi] {notification.title}",
            f"{notification.message}{link}",
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        Notification.objects.filter(pk=notification.pk).update(emailed=True)
    except Exception:
        # Pochta ishlamasligi tizim ichidagi xabarnomaga ta'sir qilmaydi
        logger.exception("Xabarnomani e-pochtaga yuborib bo'lmadi (foydalanuvchi %s)", user.pk)


def notify(users, kind, title, message="", case=None, dedup_key=""):
    """Foydalanuvchilarga xabarnoma yuboradi. dedup_key bo'lsa, takroriy yubormaydi."""
    created = []
    for user in users:
        if dedup_key and Notification.objects.filter(user=user, dedup_key=dedup_key).exists():
            continue
        n = Notification.objects.create(
            user=user, case=case, kind=kind, title=title[:255], message=message, dedup_key=dedup_key[:120]
        )
        _send_email(n)
        created.append(n)
    return created


def notify_case(case, kind, title, message="", include_legal=False, extra=None, exclude=None, dedup_key=""):
    users = recipients_for(case, include_legal=include_legal, extra=extra, exclude=exclude)
    return notify(users, kind, title, message, case=case, dedup_key=dedup_key)
