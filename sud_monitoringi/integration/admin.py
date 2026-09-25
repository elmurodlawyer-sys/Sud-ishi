from django.contrib import admin

from .models import ExternalRecord, IntegrationRun, IntegrationSource

admin.site.register(IntegrationSource)
admin.site.register(IntegrationRun)
admin.site.register(ExternalRecord)
