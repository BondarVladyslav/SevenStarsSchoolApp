from django.urls import path
from .views import *


urlpatterns = [
    path('',schedule_view , name='schedule'),
    path('schedule/lesson/<int:lesson_id>/<str:date>/grade/', grade_lesson_participation, name='grade_lesson_participation'),
]
