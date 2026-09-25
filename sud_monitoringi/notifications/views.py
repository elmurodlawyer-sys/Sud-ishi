from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Notification


@login_required
def notification_list(request):
    qs = request.user.notifications.select_related("case")
    if request.GET.get("unread"):
        qs = qs.filter(is_read=False)
    page = Paginator(qs, 30).get_page(request.GET.get("page"))
    return render(request, "notifications/list.html", {"page": page, "unread_only": bool(request.GET.get("unread"))})


@login_required
def notification_open(request, pk):
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    if not n.is_read:
        n.is_read, n.read_at = True, timezone.now()
        n.save(update_fields=["is_read", "read_at"])
    return redirect(n.case.get_absolute_url() if n.case_id else "notifications:list")


@login_required
@require_POST
def mark_all_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True, read_at=timezone.now())
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("notifications:list")
