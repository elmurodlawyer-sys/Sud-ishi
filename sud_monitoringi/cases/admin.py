from django.contrib import admin

from .models import Case, CaseDocument, CaseEvent, CaseStage, Deadline, Hearing


class ReadOnlyEventsInline(admin.TabularInline):
    model = CaseEvent
    extra = 0
    can_delete = False
    readonly_fields = ("created_at", "user", "event_type", "description", "changes", "comment")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ("reg_number", "case_number", "organization", "role", "court", "status", "is_cancelled")
    list_filter = ("status", "role", "is_cancelled", "source")
    search_fields = ("reg_number", "case_number", "plaintiffs", "defendants")
    raw_id_fields = ("organization", "court", "responsible", "created_by", "cancelled_by")
    inlines = [ReadOnlyEventsInline]

    def has_delete_permission(self, request, obj=None):
        # Sud ishini jismonan o'chirish faqat maxsus huquq bilan (4-bo'lim)
        return request.user.has_perm("cases.delete_case_physically")


for model in (CaseStage, Hearing, Deadline, CaseDocument):
    admin.site.register(model)


@admin.register(CaseEvent)
class CaseEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "case", "user", "event_type", "description")
    list_filter = ("event_type",)
    readonly_fields = [f.name for f in CaseEvent._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
