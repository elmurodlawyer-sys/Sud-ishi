from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import Case, StatusCode


def can_view(user, case):
    scope = user.scope_organization_ids()
    return scope is None or case.organization_id in scope


def can_edit(user, case):
    if not (user.can_edit_cases and can_view(user, case)) or case.is_cancelled:
        return False
    if case.status_id and case.status.code == StatusCode.ARCHIVED and not user.is_legal:
        return False
    return True


def get_case(request, pk, edit=False):
    case = get_object_or_404(
        Case.objects.select_related(
            "organization", "organization__org_type", "organization__region", "court", "court__court_type", "instance",
            "category", "status", "outcome", "responsible",
        ),
        pk=pk,
    )
    if not can_view(request.user, case):
        raise PermissionDenied("Ushbu sud ishini ko‘rish huquqingiz yo‘q.")
    if edit and not can_edit(request.user, case):
        raise PermissionDenied("Ushbu sud ishini o‘zgartirish huquqingiz yo‘q.")
    return case


def require(condition, message="Ushbu amal uchun huquqingiz yo‘q."):
    if not condition:
        raise PermissionDenied(message)
