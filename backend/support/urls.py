from django.urls import path

from . import api

urlpatterns = [
    path("conversations/", api.ConversationList.as_view()),
    path("conversations/<int:pk>/", api.ConversationDetail.as_view()),
    path("conversations/<int:pk>/messages/", api.Messages.as_view()),
    path("conversations/<int:pk>/read/", api.Read.as_view()),
    path("conversations/<int:pk>/close/", api.Close.as_view()),
    path("ops/conversations/", api.OpsConversationList.as_view()),
    path("ops/conversations/<int:pk>/", api.OpsConversationDetail.as_view()),
    path("ops/conversations/<int:pk>/messages/", api.OpsMessages.as_view()),
    path("ops/conversations/<int:pk>/read/", api.OpsRead.as_view()),
    path("ops/conversations/<int:pk>/close/", api.OpsClose.as_view()),
    path("ops/conversations/<int:pk>/assign/", api.Assign.as_view()),
]
