def notifications(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    qs = user.notifications.filter(is_read=False)
    return {"unread_notifications_count": qs.count(), "latest_notifications": qs.select_related("case")[:6]}
