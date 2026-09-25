from django.urls import path

from . import views

app_name = "integration"

urlpatterns = [
    path("", views.source_list, name="source_list"),
    path("manba/yangi/", views.source_edit, name="source_create"),
    path("manba/<int:pk>/", views.source_edit, name="source_edit"),
    path("manba/<int:pk>/ishga-tushirish/", views.source_run, name="source_run"),
    path("seans/<int:pk>/", views.run_detail, name="run_detail"),
    path("fayldan-import/", views.file_import, name="file_import"),
]
