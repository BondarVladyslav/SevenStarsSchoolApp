from django.urls import path

from .views import download_chat_file, request_chat_upload_url


urlpatterns = [
path('file/<int:message_id>/', download_chat_file, name='download_chat_file'),
path('upload-url/<int:conversation_id>/', request_chat_upload_url, name='chat_upload_url'),
    
]