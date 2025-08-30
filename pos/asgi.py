import os
from django.core.asgi import get_asgi_application
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

from pos.apps.accounts.routing import websocket_urlpatterns as accounts_websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pos.settings')

websocket_urlpatterns = accounts_websocket_urlpatterns 

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(accounts_websocket_urlpatterns))
        ),
})