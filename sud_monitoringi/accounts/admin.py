from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import AuditLog, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "last_name", "first_name", "role", "organization", "is_active")
    list_filter = ("role", "is_active", "is_superuser")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Sud monitoringi", {"fields": ("middle_name", "role", "organization", "position", "phone", "email_notifications")}),
    )
    raw_id_fields = ("organization",)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "username", "action", "object_type", "object_id", "ip_address")
    list_filter = ("action", "is_admin_action")
    search_fields = ("username", "description", "path")
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
