from django.urls import path

from .mini_api import MiniLogin, MiniLogout, MiniRefresh
from .role_api import Options, Update, Users
from .views import (
    CsrfAPIView,
    LoginAPIView,
    LogoutAPIView,
    PasswordChangeAPIView,
    PasswordResetAPIView,
    RegisterAPIView,
    RoleListAPIView,
    VerificationAPIView,
    WebRefreshAPIView,
)

app_name = "accounts"

urlpatterns = [
    path("auth/csrf/", CsrfAPIView.as_view(), name="csrf"),
    path("auth/register/", RegisterAPIView.as_view(), name="register"),
    path("auth/login/", LoginAPIView.as_view(), name="login"),
    path("auth/web/refresh/", WebRefreshAPIView.as_view(), name="web-refresh"),
    path("auth/mini/login/", MiniLogin.as_view(), name="mini-login"),
    path("auth/mini/refresh/", MiniRefresh.as_view(), name="mini-refresh"),
    path("auth/mini/logout/", MiniLogout.as_view(), name="mini-logout"),
    path("auth/logout/", LogoutAPIView.as_view(), name="logout"),
    path(
        "auth/password/change/", PasswordChangeAPIView.as_view(), name="password-change"
    ),
    path("auth/verifications/", VerificationAPIView.as_view(), name="verification"),
    path("auth/password/reset/", PasswordResetAPIView.as_view(), name="password-reset"),
    path("ops/roles/", RoleListAPIView.as_view(), name="roles"),
    path("ops/users/", Users.as_view(), name="role-users"),
    path("ops/role-options/", Options.as_view(), name="role-options"),
    path("ops/users/<int:pk>/roles/", Update.as_view(), name="user-role-update"),
]
