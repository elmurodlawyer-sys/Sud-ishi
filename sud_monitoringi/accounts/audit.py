"""Harakatlar jurnaliga yozish uchun yordamchi funksiyalar."""
import logging

logger = logging.getLogger(__name__)


def client_ip(request):
    if request is None:
        return None
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def log_action(request, action, obj=None, description="", user=None, username=None):
    """Jurnalga yozuv qo'shadi. Xatolik asosiy jarayonni to'xtatmaydi."""
    from .models import AuditLog

    try:
        if user is None and request is not None and getattr(request, "user", None) is not None:
            if request.user.is_authenticated:
                user = request.user
        AuditLog.objects.create(
            user=user,
            username=username or (user.username if user else ""),
            action=action,
            object_type=obj.__class__.__name__ if obj is not None else "",
            object_id=str(getattr(obj, "pk", "") or "") if obj is not None else "",
            description=description[:5000],
            path=((request.path or "")[:500] if request is not None else ""),
            method=((request.method or "") if request is not None else ""),
            ip_address=client_ip(request),
            is_admin_action=bool(user and user.is_system_admin),
        )
    except Exception:  # pragma: no cover - jurnal xatosi tizimni to'xtatmasligi kerak
        logger.exception("Audit yozuvini saqlab bo'lmadi")
