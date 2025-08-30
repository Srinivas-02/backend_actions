"""CCTV Websocket Consumers Route"""

from django.urls import re_path

from .consumers import TestConsumer

websocket_urlpatterns = [
    re_path(r"testing/", TestConsumer.as_asgi()),
]
