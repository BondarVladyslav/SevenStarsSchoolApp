from django.urls import path
from .views import *


urlpatterns = [
    path('list/', materials_view, name='materials_list'),
    path('<int:material_id>/', material_detail_view, name='material_detail'),
    path('file/<int:file_id>/download/', download_material_file, name='download_material_file'),
]
