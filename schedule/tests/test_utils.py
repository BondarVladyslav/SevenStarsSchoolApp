from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from courses.models import Group, Homework, HomeworkSubmission, Subject
from schedule.models import Lesson, ScheduleException
from schedule.utils import get_schedule_range, get_upcoming_lesson_occurrences
from users.models import Student

User = get_user_model()


class GetScheduleRangeTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='Математика')
        self.group = Group.objects.create(name='Group 1', subject=self.subject)
        user = User.objects.create_user(username='student1', password='pass12345')
        self.student = Student.objects.create(user=user)
        self.student.groups.add(self.group)

    def test_includes_homework_grade_for_lesson_bound_homework(self):
        lesson = Lesson.objects.create(
            group=self.group, weekday=0, start_time=time(10, 0), end_time=time(11, 0),
        )
        homework = Homework.objects.create(
            group=self.group,
            lesson=lesson,
            lesson_date=date(2026, 7, 13),
            title='Домашня робота',
            description='Тест',
            deadline=timezone.now() + timedelta(days=1),
        )
        HomeworkSubmission.objects.create(
            homework=homework,
            student=self.student,
            text='Done',
            status='checked',
            grade=42,
        )

        days = get_schedule_range([self.group.id], date(2026, 7, 13), date(2026, 7, 13), student=self.student)
        entry = days[0]['lessons'][0]

        self.assertEqual(entry['homework'].id, homework.id)
        self.assertEqual(entry['homework_grade'], 42)

    def test_normal_lesson_present_on_matching_weekday(self):
        Lesson.objects.create(group=self.group, weekday=0, start_time=time(10, 0), end_time=time(11, 0))

        days = get_schedule_range([self.group.id], date(2026, 7, 13), date(2026, 7, 13))

        self.assertEqual(len(days[0]['lessons']), 1)
        self.assertEqual(days[0]['lessons'][0]['status'], 'normal')

    def test_cancelled_lesson_marked_as_cancelled(self):
        lesson = Lesson.objects.create(group=self.group, weekday=0, start_time=time(10, 0), end_time=time(11, 0))
        ScheduleException.objects.create(
            lesson=lesson, original_date=date(2026, 7, 13), exception_type='cancelled',
        )

        days = get_schedule_range([self.group.id], date(2026, 7, 13), date(2026, 7, 13))

        self.assertEqual(days[0]['lessons'][0]['status'], 'cancelled')

    def test_rescheduled_lesson_appears_on_new_date(self):
        lesson = Lesson.objects.create(group=self.group, weekday=0, start_time=time(10, 0), end_time=time(11, 0))
        ScheduleException.objects.create(
            lesson=lesson, original_date=date(2026, 7, 13), exception_type='rescheduled',
            new_date=date(2026, 7, 15), new_start_time=time(14, 0), new_end_time=time(15, 0),
        )

        days = get_schedule_range([self.group.id], date(2026, 7, 13), date(2026, 7, 15))
        by_date = {d['date']: d for d in days}

        self.assertEqual(by_date[date(2026, 7, 13)]['lessons'][0]['status'], 'moved_away')
        self.assertEqual(by_date[date(2026, 7, 15)]['lessons'][0]['status'], 'moved_here')
        self.assertEqual(by_date[date(2026, 7, 15)]['lessons'][0]['start_time'], time(14, 0))

    def test_combined_score_sums_homework_and_participation(self):
        from schedule.models import LessonParticipation

        lesson = Lesson.objects.create(group=self.group, weekday=0, start_time=time(10, 0), end_time=time(11, 0))
        homework = Homework.objects.create(
            group=self.group, lesson=lesson, lesson_date=date(2026, 7, 13),
            title='ДЗ', description='Опис', deadline=timezone.now() + timedelta(days=1),
        )
        HomeworkSubmission.objects.create(homework=homework, student=self.student, grade=20, status='checked')
        LessonParticipation.objects.create(
            lesson=lesson, lesson_date=date(2026, 7, 13), student=self.student, score=15,
        )

        days = get_schedule_range([self.group.id], date(2026, 7, 13), date(2026, 7, 13), student=self.student)
        entry = days[0]['lessons'][0]

        self.assertEqual(entry['combined_score'], 35)


class GetUpcomingLessonOccurrencesTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name='Математика')
        self.group = Group.objects.create(name='Group 1', subject=subject)

    def test_occurrence_generated_for_matching_weekday(self):
        today = timezone.localdate()
        Lesson.objects.create(
            group=self.group, weekday=today.weekday(), start_time=time(10, 0), end_time=time(11, 0),
        )

        occurrences = get_upcoming_lesson_occurrences(self.group, weeks_ahead=1)

        self.assertTrue(any(o['date'] == today for o in occurrences))

    def test_cancelled_occurrence_excluded(self):
        today = timezone.localdate()
        lesson = Lesson.objects.create(
            group=self.group, weekday=today.weekday(), start_time=time(10, 0), end_time=time(11, 0),
        )
        ScheduleException.objects.create(lesson=lesson, original_date=today, exception_type='cancelled')

        occurrences = get_upcoming_lesson_occurrences(self.group, weeks_ahead=1)

        self.assertFalse(any(o['date'] == today for o in occurrences))
