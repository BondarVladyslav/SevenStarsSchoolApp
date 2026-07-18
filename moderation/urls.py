from django.urls import path
from .views import *

urlpatterns = [
    path('', moderation_dashboard, name='moderation_dashboard'),
    path('edit-group/<int:group_id>/', group_create_or_edit, name='edit_group'),
    path('create-group/', group_create_or_edit, name='create_group'),
    path('edit-student/<int:student_id>/', student_edit_or_create, name='edit_student'),
    path('create-student/', student_edit_or_create, name='create_student'),
    path('edit-parent/<int:parent_id>/', parent_edit_or_create, name='edit_parent'),
    path('create-parent/', parent_edit_or_create, name='create_parent'),
    path('edit-teacher/<int:teacher_id>/', teacher_edit_or_create, name='edit_teacher'),
    path('create-teacher/', teacher_edit_or_create, name='create_teacher'),
    path('group-schedule/<int:group_id>/', manage_group_schedule, name='manage_group_schedule'),
    path('material/<int:material_id>/', material_edit_or_create, name='edit_material'),
    path('material/create/', material_edit_or_create, name='create_material'),
    path('material/upload-url/', request_material_upload_urls, name='material_upload_url'),
    path('create-subject/', subject_edit_or_create, name='create_subject'),
    path('edit-subject/<int:subject_id>/', subject_edit_or_create, name='edit_subject'),
    path('create-level/', level_edit_or_create, name='create_level'),
    path('edit-level/<int:level_id>/', level_edit_or_create, name='edit_level'),
    path('group-schedule/<int:group_id>/exceptions/', manage_schedule_exceptions, name='manage_schedule_exceptions'),
]