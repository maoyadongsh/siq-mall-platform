from django.urls import path
from . import api

urlpatterns = [
    path("reviews/", api.Submit.as_view()),
    path("users/me/reviews/", api.Mine.as_view()),
    path("products/<int:pk>/reviews/", api.Public.as_view()),
    path("ops/reviews/", api.Queue.as_view()),
    path("ops/reviews/<int:pk>/moderate/", api.Moderate.as_view()),
]
