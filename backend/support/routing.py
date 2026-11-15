from django.urls import re_path

from .consumer import SupportConsumer

websocket_urlpatterns = [
    re_path(r"^ws/support/(?P<pk>\d+)/$", SupportConsumer.as_asgi()),
]
