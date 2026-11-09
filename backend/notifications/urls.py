from django.urls import path

from . import api

urlpatterns = [
    path("notifications/", api.NoticeList.as_view()),
    path("notifications/unread-count/", api.UnreadCount.as_view()),
    path("notifications/read/", api.MarkRead.as_view()),
    path("notifications/subscriptions/", api.Subscriptions.as_view()),
    path("ops/notification-templates/", api.TemplateList.as_view()),
    path("ops/notification-templates/<int:pk>/", api.TemplateDetail.as_view()),
    path(
        "ops/notification-templates/<int:pk>/activate/",
        api.TemplateActivateView.as_view(),
    ),
]
