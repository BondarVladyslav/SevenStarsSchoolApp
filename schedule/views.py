from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from users.models import Parent, Student, Teacher
from schedule.models import Lesson, LessonParticipation
from schedule.utils import get_schedule_range

DAYS_BEFORE = 14
DAYS_AFTER = 14


@login_required
def schedule_view(request):
    user = request.user
    today = timezone.localdate()
    start_date = today - timedelta(days=DAYS_BEFORE)
    end_date = today + timedelta(days=DAYS_AFTER)

    student = Student.objects.filter(user=user).select_related('user').first()
    if student:
        week_start = start_date - timedelta(days=start_date.weekday())
        week_end = end_date + timedelta(days=(6 - end_date.weekday()))

        group_ids = student.groups.values_list('id', flat=True)
        days = get_schedule_range(group_ids, week_start, week_end, student=student)
        weeks = [days[i:i + 7] for i in range(0, len(days), 7)]

        context = {
            'weeks': weeks,
            'schedule_owner_name': student.user.get_full_name(),
            'today': today,
        }
        return render(request, 'schedule/student_and_parent_schedule.html', context)

    teacher = Teacher.objects.filter(user=user).select_related('user').first()
    if teacher:
        group_ids = teacher.groups.values_list('id', flat=True)
        context = {
            'schedule': get_schedule_range(group_ids, start_date, end_date),
            'schedule_owner_name': teacher.user.get_full_name(),
            'today': today,
            'is_teacher_view': True,
        }
        return render(request, 'schedule/schedule.html', context)

    parent = Parent.objects.filter(user=user).select_related('user').first()
    if parent:
        children = parent.children.select_related('user').all()
        if not children:
            raise PermissionDenied

        child_id = request.GET.get('child_id')
        selected_child = children.filter(id=child_id).first() or children.first()

        week_start = start_date - timedelta(days=start_date.weekday())
        week_end = end_date + timedelta(days=(6 - end_date.weekday()))

        group_ids = selected_child.groups.values_list('id', flat=True)
        days = get_schedule_range(group_ids, week_start, week_end, student=selected_child)
        weeks = [days[i:i + 7] for i in range(0, len(days), 7)]

        context = {
            'weeks': weeks,
            'schedule_owner_name': selected_child.user.get_full_name(),
            'children': children,
            'selected_child': selected_child,
            'today': today,
            'show_combined_score': True,
        }
        return render(request, 'schedule/student_and_parent_schedule.html', context)

    raise PermissionDenied


@login_required
def grade_lesson_participation(request, lesson_id, date):
    teacher = Teacher.objects.filter(user=request.user).first()
    if not teacher:
        raise PermissionDenied

    lesson = get_object_or_404(Lesson, id=lesson_id, group__teacher=teacher)
    lesson_date = datetime.strptime(date, '%Y-%m-%d').date()

    students = lesson.group.students.select_related('user').all()

    existing_scores = {
        p.student_id: p.score
        for p in LessonParticipation.objects.filter(lesson=lesson, lesson_date=lesson_date)
    }

    if request.method == 'POST':
        for student in students:
            raw_score = request.POST.get(f'score_{student.id}', '').strip()
            if raw_score == '':
                continue

            score = max(0, min(50, int(raw_score)))

            LessonParticipation.objects.update_or_create(
                lesson=lesson,
                lesson_date=lesson_date,
                student=student,
                defaults={'score': score},
            )

        return redirect('schedule')

    students_with_scores = [
        {'student': student, 'score': existing_scores.get(student.id)}
        for student in students
    ]

    context = {
        'lesson': lesson,
        'lesson_date': lesson_date,
        'students_with_scores': students_with_scores,
    }
    return render(request, 'schedule/grade.html', context)