from django.contrib import admin

from .models import Classifier, Court, Organization


@admin.register(Classifier)
class ClassifierAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "code", "order", "is_active", "is_system", "is_final")
    list_filter = ("kind", "is_active", "is_system")
    search_fields = ("name", "code")

    def has_delete_permission(self, request, obj=None):
        return bool(obj is None or not obj.is_system) and super().has_delete_permission(request, obj)


@admin.register(Court)
class CourtAdmin(admin.ModelAdmin):
    list_display = ("name", "court_type", "region", "is_active")
    list_filter = ("court_type", "region", "is_active")
    search_fields = ("name",)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("full_name", "stir", "org_type", "region", "parent", "is_active")
    list_filter = ("org_type", "region", "is_active")
    search_fields = ("full_name", "short_name", "stir", "alt_names", "previous_names")
    raw_id_fields = ("parent",)
