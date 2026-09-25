from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.notification_list, name="list"),
    path("<int:pk>/", views.notification_open, name="open"),
    path("hammasi-oqildi/", views.mark_all_read, name="mark_all_read"),
]
