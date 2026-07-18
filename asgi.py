"""
ASGI config for SevenStarsSchool project.
It exposes the ASGI callable as a module-level variable named ``application``.
For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/asgi/
"""
import asyncio
import os
import sys

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

from channels.security.websocket import OriginValidator
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

import chat.routing

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': OriginValidator(
        AuthMiddlewareStack(
            URLRouter(chat.routing.websocket_urlpatterns)
        ),
        ['sevenstarsschool.com.ua', 'www.sevenstarsschool.com.ua'],
    ),
})