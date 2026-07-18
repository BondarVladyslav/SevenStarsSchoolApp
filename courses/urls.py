from django.urls import path
from .views import *


urlpatterns = [
    path('groups/', show_my_groups, name='show_my_groups'),
    path('groups/<int:group_id>/', show_the_group, name = 'detail_group'),
    path('homework/<int:pk>/', detail_homework_view, name = 'detail_homework'),
    path('submission-file/<int:file_id>/download/', download_submission_file, name='download_submission_file'),
    path('homework-file/<int:file_id>/download/', download_homework_file, name='download_homework_file'),
    path('detail-student/<int:group_id>/<int:student_id>/', detail_student, name='detail_student'),
    path('homework-edit/<int:group_id>/<int:homework_id>/', homework_create_or_edit, name='edit_homework'),
    path('homework-edit/<int:group_id>/', homework_create_or_edit, name='create_homework'),
    path('homework-edit/<int:group_id>/upload-url/', request_homework_upload_urls, name='homework_upload_url'),
    path('homework/<int:pk>/upload-url/', request_submission_upload_urls, name='submission_upload_url'),
    path('detail-submission/<int:submission_id>/', detail_submission_view, name='detail_submission'),
    
]