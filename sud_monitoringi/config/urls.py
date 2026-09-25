from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "“Sud monitoringi” — tizim administratori"
admin.site.site_title = "Sud monitoringi"
admin.site.index_title = "Ma’lumotlarni boshqarish"

urlpatterns = [
    path("", include("reports.urls")),
    path("tizim/", include("accounts.urls")),
    path("ishlar/", include("cases.urls")),
    path("malumotnomalar/", include("core.urls")),
    path("integratsiya/", include("integration.urls")),
    path("xabarnomalar/", include("notifications.urls")),
    path("admin/", admin.site.urls),
]
