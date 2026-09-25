from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("created_at", "user", "kind", "title", "is_read", "emailed")
    list_filter = ("kind", "is_read")
