from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("kirish/", views.LoginView.as_view(), name="login"),
    path("chiqish/", auth_views.LogoutView.as_view(), name="logout"),
    path("profil/", views.profile, name="profile"),
    path("foydalanuvchilar/", views.user_list, name="user_list"),
    path("foydalanuvchilar/yangi/", views.user_edit, name="user_create"),
    path("foydalanuvchilar/<int:pk>/", views.user_edit, name="user_edit"),
    path("jurnal/", views.audit_log, name="audit_log"),
    path("zaxira/", views.backups, name="backups"),
    path("zaxira/<str:name>/", views.backup_download, name="backup_download"),
]
