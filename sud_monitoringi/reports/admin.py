from django.contrib import admin

from .models import GeneratedReport, ReportTemplate

admin.site.register(ReportTemplate)
admin.site.register(GeneratedReport)
