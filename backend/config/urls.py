"""URL 总路由：/api/v1/ 为唯一对外前缀（架构文档 §5.1）。"""

from django.contrib import admin
from django.conf import settings
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

handler404 = "common.exceptions.handler404"
handler500 = "common.exceptions.handler500"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("common.urls")),
    path("api/v1/", include("accounts.urls")),
    path("api/v1/", include("users.urls")),
]

if settings.DEBUG:
    urlpatterns += [
        path(
            "api/v1/schema/",
            SpectacularAPIView.as_view(permission_classes=[]),
            name="schema",
        ),
        path(
            "api/v1/docs/",
            SpectacularSwaggerView.as_view(url_name="schema", permission_classes=[]),
            name="swagger-ui",
        ),
    ]
