from datetime import date, time

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from courses.models import Group, Subject
from schedule.models import Lesson, LessonAbsence, LessonParticipation, ScheduleException
from users.models import Student

User = get_user_model()


class LessonModelTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name='Математика')
        self.group = Group.objects.create(name='Group A', subject=subject)

    def test_lessons_ordered_by_weekday_then_start_time(self):
        lesson_tuesday = Lesson.objects.create(
            group=self.group, weekday=1, start_time=time(9, 0), end_time=time(10, 0),
        )
        lesson_monday_late = Lesson.objects.create(
            group=self.group, weekday=0, start_time=time(12, 0), end_time=time(13, 0),
        )
        lesson_monday_early = Lesson.objects.create(
            group=self.group, weekday=0, start_time=time(9, 0), end_time=time(10, 0),
        )

        lessons = list(Lesson.objects.all())

        self.assertEqual(lessons, [lesson_monday_early, lesson_monday_late, lesson_tuesday])

    def test_lesson_deleted_when_group_deleted(self):
        lesson = Lesson.objects.create(group=self.group, weekday=0, start_time=time(9, 0), end_time=time(10, 0))
        lesson_id = lesson.id

        self.group.delete()

        self.assertFalse(Lesson.objects.filter(id=lesson_id).exists())


class LessonAbsenceModelTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name='Математика')
        group = Group.objects.create(name='Group A', subject=subject)
        self.lesson = Lesson.objects.create(group=group, weekday=0, start_time=time(9, 0), end_time=time(10, 0))
        self.other_lesson = Lesson.objects.create(
            group=group, weekday=1, start_time=time(9, 0), end_time=time(10, 0),
        )
        user = User.objects.create_user(username='student1', password='pass12345')
        self.student = Student.objects.create(user=user)

    def test_clean_rejects_both_makeup_lesson_and_custom_time(self):
        absence = LessonAbsence(
            student=self.student,
            lesson=self.lesson,
            missed_date=date(2026, 7, 6),
            makeup_lesson=self.other_lesson,
            makeup_start_time=time(15, 0),
        )
        with self.assertRaises(ValidationError):
            absence.clean()

    def test_clean_allows_only_makeup_lesson(self):
        absence = LessonAbsence(
            student=self.student,
            lesson=self.lesson,
            missed_date=date(2026, 7, 6),
            makeup_lesson=self.other_lesson,
        )
        absence.clean()  # should not raise

    def test_clean_allows_only_custom_time(self):
        absence = LessonAbsence(
            student=self.student,
            lesson=self.lesson,
            missed_date=date(2026, 7, 6),
            makeup_start_time=time(15, 0),
            makeup_end_time=time(16, 0),
        )
        absence.clean()  # should not raise

    def test_resolved_time_uses_makeup_lesson_when_present(self):
        absence = LessonAbsence.objects.create(
            student=self.student, lesson=self.lesson, missed_date=date(2026, 7, 6),
            makeup_lesson=self.other_lesson,
        )
        self.assertEqual(absence.resolved_start_time, self.other_lesson.start_time)
        self.assertEqual(absence.resolved_end_time, self.other_lesson.end_time)

    def test_resolved_time_uses_custom_time_when_no_makeup_lesson(self):
        absence = LessonAbsence.objects.create(
            student=self.student, lesson=self.lesson, missed_date=date(2026, 7, 6),
            makeup_start_time=time(15, 0), makeup_end_time=time(16, 0),
        )
        self.assertEqual(absence.resolved_start_time, time(15, 0))
        self.assertEqual(absence.resolved_end_time, time(16, 0))

    def test_unique_together_student_lesson_missed_date(self):
        LessonAbsence.objects.create(student=self.student, lesson=self.lesson, missed_date=date(2026, 7, 6))
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                LessonAbsence.objects.create(
                    student=self.student, lesson=self.lesson, missed_date=date(2026, 7, 6),
                )


class ScheduleExceptionModelTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name='Математика')
        group = Group.objects.create(name='Group A', subject=subject)
        self.lesson = Lesson.objects.create(group=group, weekday=0, start_time=time(9, 0), end_time=time(10, 0))

    def test_rescheduled_requires_new_date(self):
        exception = ScheduleException(
            lesson=self.lesson, original_date=date(2026, 7, 6), exception_type='rescheduled',
        )
        with self.assertRaises(ValidationError):
            exception.clean()

    def test_cancelled_must_not_have_new_date(self):
        exception = ScheduleException(
            lesson=self.lesson, original_date=date(2026, 7, 6), exception_type='cancelled',
            new_date=date(2026, 7, 13),
        )
        with self.assertRaises(ValidationError):
            exception.clean()

    def test_valid_cancelled_exception(self):
        exception = ScheduleException(
            lesson=self.lesson, original_date=date(2026, 7, 6), exception_type='cancelled',
        )
        exception.clean()  # should not raise

    def test_valid_rescheduled_exception(self):
        exception = ScheduleException(
            lesson=self.lesson, original_date=date(2026, 7, 6), exception_type='rescheduled',
            new_date=date(2026, 7, 13),
        )
        exception.clean()  # should not raise

    def test_unique_together_lesson_original_date(self):
        ScheduleException.objects.create(
            lesson=self.lesson, original_date=date(2026, 7, 6), exception_type='cancelled',
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                ScheduleException.objects.create(
                    lesson=self.lesson, original_date=date(2026, 7, 6), exception_type='cancelled',
                )


class LessonParticipationModelTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name='Математика')
        group = Group.objects.create(name='Group A', subject=subject)
        self.lesson = Lesson.objects.create(group=group, weekday=0, start_time=time(9, 0), end_time=time(10, 0))
        user = User.objects.create_user(username='student1', password='pass12345')
        self.student = Student.objects.create(user=user)

    def test_unique_together_lesson_date_student(self):
        LessonParticipation.objects.create(
            lesson=self.lesson, lesson_date=date(2026, 7, 6), student=self.student, score=40,
        )
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                LessonParticipation.objects.create(
                    lesson=self.lesson, lesson_date=date(2026, 7, 6), student=self.student, score=30,
                )

    def test_score_validators_reject_out_of_range(self):
        from django.core.exceptions import ValidationError as DjValidationError

        participation = LessonParticipation(
            lesson=self.lesson, lesson_date=date(2026, 7, 6), student=self.student, score=51,
        )
        with self.assertRaises(DjValidationError):
            participation.full_clean()
