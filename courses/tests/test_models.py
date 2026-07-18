from datetime import date, time, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from courses.models import (
    Group,
    Homework,
    HomeworkFile,
    HomeworkSubmission,
    Level,
    Subject,
    SubmissionFile,
)
from users.models import Student, Teacher

User = get_user_model()


class SubjectModelTests(TestCase):
    def test_create_subject(self):
        subject = Subject.objects.create(name='Англійська мова')
        self.assertEqual(str(subject.name), 'Англійська мова')


class LevelModelTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='Англійська мова')

    def test_str_representation(self):
        level = Level.objects.create(subject=self.subject, name='Beginner', order=1)
        self.assertEqual(str(level), 'Англійська мова — Beginner')

    def test_unique_together_subject_name(self):
        Level.objects.create(subject=self.subject, name='Beginner', order=1)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Level.objects.create(subject=self.subject, name='Beginner', order=2)

    def test_ordering_by_order_field(self):
        level_b = Level.objects.create(subject=self.subject, name='Intermediate', order=2)
        level_a = Level.objects.create(subject=self.subject, name='Beginner', order=1)

        levels = list(Level.objects.filter(subject=self.subject))

        self.assertEqual(levels, [level_a, level_b])


class GroupModelTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='Математика')

    def test_str_representation(self):
        group = Group.objects.create(name='Group A', subject=self.subject)
        self.assertEqual(str(group), 'Group A')

    def test_group_teacher_set_null_on_teacher_delete(self):
        user = User.objects.create_user(username='teacher1', password='pass12345')
        teacher = Teacher.objects.create(user=user)
        group = Group.objects.create(name='Group A', subject=self.subject, teacher=teacher)

        teacher.delete()
        group.refresh_from_db()

        self.assertIsNone(group.teacher)

    def test_group_deleted_when_subject_deleted(self):
        group = Group.objects.create(name='Group A', subject=self.subject)
        group_id = group.id

        self.subject.delete()

        self.assertFalse(Group.objects.filter(id=group_id).exists())


class HomeworkModelTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name='Математика')
        self.group = Group.objects.create(name='Group A', subject=subject)

    def test_create_homework(self):
        homework = Homework.objects.create(
            group=self.group,
            title='ДЗ 1',
            description='Опис',
            deadline=timezone.now() + timedelta(days=3),
        )
        self.assertEqual(homework.group, self.group)

    def test_homework_ordering_is_by_id(self):
        hw1 = Homework.objects.create(
            group=self.group, title='ДЗ 1', description='Опис',
            deadline=timezone.now() + timedelta(days=1),
        )
        hw2 = Homework.objects.create(
            group=self.group, title='ДЗ 2', description='Опис',
            deadline=timezone.now() + timedelta(days=1),
        )
        self.assertEqual(list(Homework.objects.all()), [hw1, hw2])

    def test_homework_deleted_when_group_deleted(self):
        homework = Homework.objects.create(
            group=self.group, title='ДЗ 1', description='Опис',
            deadline=timezone.now() + timedelta(days=1),
        )
        homework_id = homework.id

        self.group.delete()

        self.assertFalse(Homework.objects.filter(id=homework_id).exists())


class HomeworkFileModelTests(TestCase):
    def test_homework_deleted_cascades_to_files(self):
        subject = Subject.objects.create(name='Математика')
        group = Group.objects.create(name='Group A', subject=subject)
        homework = Homework.objects.create(
            group=group, title='ДЗ 1', description='Опис',
            deadline=timezone.now() + timedelta(days=1),
        )
        homework_file = HomeworkFile.objects.create(homework=homework, file='homework_files/test.txt')
        file_id = homework_file.id

        homework.delete()

        self.assertFalse(HomeworkFile.objects.filter(id=file_id).exists())


class HomeworkSubmissionModelTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name='Математика')
        self.group = Group.objects.create(name='Group A', subject=subject)
        self.homework = Homework.objects.create(
            group=self.group, title='ДЗ 1', description='Опис',
            deadline=timezone.now() + timedelta(days=1),
        )
        user = User.objects.create_user(username='student1', password='pass12345')
        self.student = Student.objects.create(user=user)

    def test_default_status_is_pending(self):
        submission = HomeworkSubmission.objects.create(homework=self.homework, student=self.student)
        self.assertEqual(submission.status, 'pending')

    def test_unique_together_homework_student(self):
        HomeworkSubmission.objects.create(homework=self.homework, student=self.student)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                HomeworkSubmission.objects.create(homework=self.homework, student=self.student)

    def test_grade_validators_reject_out_of_range(self):
        submission = HomeworkSubmission(homework=self.homework, student=self.student, grade=51)
        with self.assertRaises(ValidationError):
            submission.full_clean()

    def test_grade_validators_accept_valid_range(self):
        submission = HomeworkSubmission(homework=self.homework, student=self.student, grade=50)
        submission.full_clean()
        submission.save()
        self.assertEqual(submission.grade, 50)


class SubmissionFileModelTests(TestCase):
    def test_submission_deleted_cascades_to_files(self):
        subject = Subject.objects.create(name='Математика')
        group = Group.objects.create(name='Group A', subject=subject)
        homework = Homework.objects.create(
            group=group, title='ДЗ 1', description='Опис',
            deadline=timezone.now() + timedelta(days=1),
        )
        user = User.objects.create_user(username='student1', password='pass12345')
        student = Student.objects.create(user=user)
        submission = HomeworkSubmission.objects.create(homework=homework, student=student)

        submission_file = SubmissionFile.objects.create(submission=submission, file='submission_files/a.txt')
        file_id = submission_file.id

        submission.delete()

        self.assertFalse(SubmissionFile.objects.filter(id=file_id).exists())
