from django.urls import path

from . import views

app_name = "cases"

urlpatterns = [
    path("", views.case_list, name="list"),
    path("yangi/", views.case_create, name="create"),
    path("majlislar/", views.hearing_list, name="hearings"),
    path("nazorat/", views.control_list, name="control"),
    path("<int:pk>/", views.case_detail, name="detail"),
    path("<int:pk>/tahrirlash/", views.case_edit, name="edit"),
    path("<int:pk>/bosqich/", views.stage_add, name="stage_add"),
    path("<int:pk>/bosqich/<int:stage_id>/yakunlash/", views.stage_close, name="stage_close"),
    path("<int:pk>/majlis/", views.hearing_edit, name="hearing_add"),
    path("<int:pk>/majlis/<int:hearing_id>/", views.hearing_edit, name="hearing_edit"),
    path("<int:pk>/muddat/", views.deadline_edit, name="deadline_add"),
    path("<int:pk>/muddat/<int:deadline_id>/", views.deadline_edit, name="deadline_edit"),
    path("<int:pk>/muddat/<int:deadline_id>/bajarildi/", views.deadline_done, name="deadline_done"),
    path("<int:pk>/hujjat/", views.document_upload, name="document_upload"),
    path("<int:pk>/hujjat/<int:doc_id>/", views.document_download, name="document_download"),
    path("<int:pk>/amal/<str:action>/", views.review_action, name="action"),
]
