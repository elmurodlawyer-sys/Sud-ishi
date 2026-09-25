from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("situatsion-markaz/", views.situation, name="situation"),
    path("hisobotlar/", views.report_builder, name="builder"),
    path("hisobotlar/saqlash/", views.report_save, name="save"),
    path("hisobotlar/saqlanganlar/", views.generated_list, name="generated"),
    path("hisobotlar/saqlanganlar/<int:pk>/<str:kind>/", views.generated_download, name="generated_download"),
    path("hisobotlar/shablon/<int:pk>/<str:action>/", views.template_action, name="template_action"),
]
