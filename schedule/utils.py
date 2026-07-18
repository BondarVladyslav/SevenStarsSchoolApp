from datetime import timedelta

from .models import Lesson, ScheduleException, LessonParticipation
from courses.models import Homework, HomeworkSubmission

WEEKDAY_NAMES = ['Понеділок', 'Вівторок', 'Середа', 'Четвер', "П'ятниця", 'Субота', 'Неділя']


def get_schedule_range(group_ids, start_date, end_date, student=None):
    lessons = list(Lesson.objects.filter(group_id__in=group_ids).select_related('group'))

    exceptions = ScheduleException.objects.filter(
        lesson__group_id__in=group_ids,
        original_date__gte=start_date,
        original_date__lte=end_date,
    ).select_related('lesson', 'lesson__group')

    exceptions_by_lesson_and_date = {}
    rescheduled_arrivals = {}

    for exc in exceptions:
        exceptions_by_lesson_and_date[(exc.lesson_id, exc.original_date)] = exc
        if exc.exception_type == 'rescheduled' and exc.new_date:
            rescheduled_arrivals.setdefault(exc.new_date, []).append(exc)

    homework_by_lesson_and_date = {}
    submission_by_homework = {}
    participation_by_lesson_and_date = {}

    if student is not None:
        homeworks = Homework.objects.filter(
            group_id__in=group_ids,
            lesson__isnull=False,
            lesson_date__gte=start_date,
            lesson_date__lte=end_date,
        ).select_related('lesson')

        for hw in homeworks:
            homework_by_lesson_and_date[(hw.lesson_id, hw.lesson_date)] = hw

        homework_ids = [hw.id for hw in homeworks]
        submissions = HomeworkSubmission.objects.filter(
            student=student, homework_id__in=homework_ids,
        )
        for sub in submissions:
            submission_by_homework[sub.homework_id] = sub

        participations = LessonParticipation.objects.filter(
            student=student,
            lesson__group_id__in=group_ids,
            lesson_date__gte=start_date,
            lesson_date__lte=end_date,
        )
        for part in participations:
            participation_by_lesson_and_date[(part.lesson_id, part.lesson_date)] = part

    def attach_grades(entry, lesson_id, date):
        homework = homework_by_lesson_and_date.get((lesson_id, date))
        if homework:
            submission = submission_by_homework.get(homework.id)
            entry['homework'] = homework
            entry['homework_grade'] = submission.grade if submission and submission.grade is not None else None
            entry['homework_status'] = submission.status if submission else None

        participation = participation_by_lesson_and_date.get((lesson_id, date))
        if participation and participation.score is not None:
            entry['participation_score'] = participation.score

        if entry.get('homework_grade') is not None or entry.get('participation_score') is not None:
            entry['combined_score'] = (entry.get('participation_score') or 0) + (entry.get('homework_grade') or 0)

    days = []
    current = start_date

    while current <= end_date:
        weekday = current.weekday()
        day_lessons = []

        for lesson in lessons:
            if lesson.weekday != weekday:
                continue

            exc = exceptions_by_lesson_and_date.get((lesson.id, current))
            if exc:
                continue

            entry = {
                'lesson': lesson,
                'group': lesson.group,
                'start_time': lesson.start_time,
                'end_time': lesson.end_time,
                'status': 'normal',
            }
            attach_grades(entry, lesson.id, current)
            day_lessons.append(entry)

        for exc in rescheduled_arrivals.get(current, []):
            entry = {
                'lesson': exc.lesson,
                'group': exc.lesson.group,
                'start_time': exc.new_start_time,
                'end_time': exc.new_end_time,
                'status': 'moved_here',
                'original_date': exc.original_date,
            }
            attach_grades(entry, exc.lesson_id, exc.original_date)
            day_lessons.append(entry)

        cancelled_today = [
            exc for exc in exceptions_by_lesson_and_date.values()
            if exc.original_date == current and exc.exception_type == 'cancelled'
        ]
        for exc in cancelled_today:
            entry = {
                'lesson': exc.lesson,
                'group': exc.lesson.group,
                'start_time': exc.lesson.start_time,
                'end_time': exc.lesson.end_time,
                'status': 'cancelled',
            }
            attach_grades(entry, exc.lesson_id, current)
            day_lessons.append(entry)

        moved_away_today = [
            exc for exc in exceptions_by_lesson_and_date.values()
            if exc.original_date == current and exc.exception_type == 'rescheduled'
        ]
        for exc in moved_away_today:
            entry = {
                'lesson': exc.lesson,
                'group': exc.lesson.group,
                'start_time': exc.lesson.start_time,
                'end_time': exc.lesson.end_time,
                'status': 'moved_away',
                'new_date': exc.new_date,
            }
            attach_grades(entry, exc.lesson_id, current)
            day_lessons.append(entry)

        day_lessons.sort(key=lambda entry: entry['start_time'])

        days.append({
            'date': current,
            'weekday_name': WEEKDAY_NAMES[weekday],
            'lessons': day_lessons,
        })

        current += timedelta(days=1)

    return days


def get_upcoming_lesson_occurrences(group, weeks_ahead=8):
    from django.utils import timezone

    today = timezone.localdate()
    lessons = list(Lesson.objects.filter(group=group))

    exceptions = ScheduleException.objects.filter(
        lesson__group=group,
        original_date__gte=today,
        original_date__lte=today + timedelta(weeks=weeks_ahead),
        exception_type='cancelled',
    ).values_list('lesson_id', 'original_date')
    cancelled = set(exceptions)

    occurrences = []
    for offset in range(weeks_ahead * 7):
        date = today + timedelta(days=offset)
        weekday = date.weekday()
        for lesson in lessons:
            if lesson.weekday != weekday:
                continue
            if (lesson.id, date) in cancelled:
                continue
            occurrences.append({'lesson': lesson, 'date': date})

    return occurrences