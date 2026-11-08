from django.urls import path

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
    path("auth/logout/", LogoutAPIView.as_view(), name="logout"),
    path(
        "auth/password/change/", PasswordChangeAPIView.as_view(), name="password-change"
    ),
    path("auth/verifications/", VerificationAPIView.as_view(), name="verification"),
    path("auth/password/reset/", PasswordResetAPIView.as_view(), name="password-reset"),
    path("ops/roles/", RoleListAPIView.as_view(), name="roles"),
]
