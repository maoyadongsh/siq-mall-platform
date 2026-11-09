from django.urls import path

from . import api

urlpatterns = [
    path("cms/home/", api.PublicHome.as_view()),
    path("cms/pages/<slug:identifier>/", api.PublicPage.as_view()),
    path(
        "cms/announcements/<int:identifier>/",
        api.PublicAnnouncement.as_view(),
    ),
    path("ops/cms/", api.OpsContentList.as_view()),
    path("ops/cms/<int:pk>/", api.OpsContentDetail.as_view()),
    path("ops/cms/<int:pk>/draft/", api.OpsDraft.as_view()),
    path("ops/cms/<int:pk>/preview/", api.OpsPreview.as_view()),
    path("ops/cms/<int:pk>/publish/", api.OpsPublication.as_view()),
    path(
        "ops/cms/<int:pk>/unpublish/",
        api.OpsPublication.as_view(publish=False),
    ),
]
