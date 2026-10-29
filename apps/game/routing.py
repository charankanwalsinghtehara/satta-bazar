from django.urls import path

from .consumers import MarketConsumer, PrivateUserConsumer

websocket_urlpatterns = [
    path("ws/market/", MarketConsumer.as_asgi()),
    path("ws/private/", PrivateUserConsumer.as_asgi()),
]
