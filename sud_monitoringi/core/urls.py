from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("tashkilotlar/", views.organization_list, name="organization_list"),
    path("tashkilotlar/yangi/", views.organization_edit, name="organization_create"),
    path("tashkilotlar/import/", views.organization_import, name="organization_import"),
    path("tashkilotlar/<int:pk>/", views.organization_detail, name="organization_detail"),
    path("tashkilotlar/<int:pk>/tahrirlash/", views.organization_edit, name="organization_edit"),
    path("klassifikatorlar/", views.classifier_list, name="classifier_list"),
    path("klassifikatorlar/yangi/", views.classifier_edit, name="classifier_create"),
    path("klassifikatorlar/<int:pk>/", views.classifier_edit, name="classifier_edit"),
    path("sudlar/", views.court_list, name="court_list"),
    path("sudlar/yangi/", views.court_edit, name="court_create"),
    path("sudlar/<int:pk>/", views.court_edit, name="court_edit"),
]
