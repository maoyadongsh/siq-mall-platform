from django.urls import path

from common.views import HealthCheckView, TokenRefreshAPIView

app_name = "common"

urlpatterns = [
    path("health/", HealthCheckView.as_view(), name="health"),
    path("auth/refresh/", TokenRefreshAPIView.as_view(), name="auth-refresh"),
]
