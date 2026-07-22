from datetime import datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from users.models import Parent, Student, Teacher
from schedule.models import Lesson, LessonAbsence, LessonParticipation
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

    students = list(lesson.group.students.select_related('user').all())
    own_student_ids = {student.id for student in students}

    visiting_absences = LessonAbsence.objects.filter(
        makeup_lesson=lesson, makeup_date=lesson_date,
    ).select_related('student__user', 'lesson__group')

    visiting_group_by_student_id = {}
    for absence in visiting_absences:
        if absence.student_id not in own_student_ids:
            students.append(absence.student)
            visiting_group_by_student_id[absence.student_id] = absence.lesson.group

    custom_makeup_by_student_id = {
        absence.student_id: absence
        for absence in LessonAbsence.objects.filter(
            lesson=lesson, missed_date=lesson_date, makeup_lesson__isnull=True,
        ).exclude(makeup_date__isnull=True)
    }

    existing_participations = {
        p.student_id: p
        for p in LessonParticipation.objects.filter(lesson=lesson, lesson_date=lesson_date)
    }

    if request.method == 'POST':
        parsed_entries = []

        for student in students:
            is_absent = bool(request.POST.get(f'is_absent_{student.id}'))
            raw_score = request.POST.get(f'score_{student.id}', '').strip()

            if is_absent and raw_score != '':
                return HttpResponse('Неможливо встановлення оцінки для відсутнього учня', status=400)

            if raw_score == '':
                score = None
            else:
                try:
                    score = max(0, min(50, int(raw_score)))
                except ValueError:
                    return HttpResponse('Некоректне значення оцінки', status=400)

            parsed_entries.append((student, is_absent, score))

        with transaction.atomic():
            for student, is_absent, score in parsed_entries:
                if not is_absent and score is None and student.id not in existing_participations:
                    continue

                LessonParticipation.objects.update_or_create(
                    lesson=lesson,
                    lesson_date=lesson_date,
                    student=student,
                    defaults={'is_absent': is_absent, 'score': score},
                )

        return redirect('schedule')

    students_with_scores = [
        {
            'student': student,
            'score': existing_participations[student.id].score if student.id in existing_participations else None,
            'is_absent': existing_participations[student.id].is_absent if student.id in existing_participations else False,
            'visiting_from': visiting_group_by_student_id.get(student.id),
            'custom_makeup': custom_makeup_by_student_id.get(student.id),
        }
        for student in students
    ]
    
    context = {
        'lesson': lesson,
        'lesson_date': lesson_date,
        'students_with_scores': students_with_scores,
    }
    return render(request, 'schedule/grade.html', context)