import os
import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from courses.models import (
    Group,
    Homework,
    HomeworkFile,
    HomeworkSubmission,
    Subject,
    SubmissionFile,
)
from users.models import Student

User = get_user_model()

_TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix='ssschool_test_media_purge_homework_')


@override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
class PurgeOldHomeworkCommandTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        subject = Subject.objects.create(name='Математика')
        self.group = Group.objects.create(name='Group A', subject=subject)
        user = User.objects.create_user(username='student1', password='pass12345')
        self.student = Student.objects.create(user=user)

    def _make_homework(self, days_ago, with_files=False):
        homework = Homework.objects.create(
            group=self.group,
            title=f'ДЗ {days_ago}',
            description='Опис',
            deadline=timezone.now() - timedelta(days=days_ago),
        )
        if with_files:
            homework_file = HomeworkFile.objects.create(
                homework=homework, file=SimpleUploadedFile('task.txt', b'task content'),
            )
            submission = HomeworkSubmission.objects.create(homework=homework, student=self.student)
            submission_file = SubmissionFile.objects.create(
                submission=submission, file=SimpleUploadedFile('answer.txt', b'answer content'),
            )
            return homework, homework_file, submission_file
        return homework, None, None

    def test_dry_run_does_not_delete_anything(self):
        old_homework, _hf, _sf = self._make_homework(days_ago=90)

        call_command('purge_old_homework', '--older-than-days=60')

        self.assertTrue(Homework.objects.filter(id=old_homework.id).exists())

    def test_force_deletes_homework_past_cutoff(self):
        old_homework, _hf, _sf = self._make_homework(days_ago=90)
        recent_homework, _hf2, _sf2 = self._make_homework(days_ago=10)

        call_command('purge_old_homework', '--older-than-days=60', '--force')

        self.assertFalse(Homework.objects.filter(id=old_homework.id).exists())
        self.assertTrue(Homework.objects.filter(id=recent_homework.id).exists())

    def test_homework_just_inside_cutoff_is_kept(self):
        homework, _hf, _sf = self._make_homework(days_ago=59)

        call_command('purge_old_homework', '--older-than-days=60', '--force')

        self.assertTrue(Homework.objects.filter(id=homework.id).exists())

    def test_homework_just_past_cutoff_is_deleted(self):
        homework, _hf, _sf = self._make_homework(days_ago=61)

        call_command('purge_old_homework', '--older-than-days=60', '--force')

        self.assertFalse(Homework.objects.filter(id=homework.id).exists())

    def test_force_deletes_submissions_and_grades(self):
        homework, _hf, _sf = self._make_homework(days_ago=90)
        submission = HomeworkSubmission.objects.create(
            homework=homework, student=self.student, grade=45, status='checked',
        )

        call_command('purge_old_homework', '--older-than-days=60', '--force')

        self.assertFalse(HomeworkSubmission.objects.filter(id=submission.id).exists())

    def test_force_deletes_physical_files(self):
        homework, homework_file, submission_file = self._make_homework(days_ago=90, with_files=True)
        homework_file_path = homework_file.file.path
        submission_file_path = submission_file.file.path

        self.assertTrue(os.path.exists(homework_file_path))
        self.assertTrue(os.path.exists(submission_file_path))

        call_command('purge_old_homework', '--older-than-days=60', '--force')

        self.assertFalse(os.path.exists(homework_file_path))
        self.assertFalse(os.path.exists(submission_file_path))

    def test_no_homework_to_delete_is_a_no_op(self):
        recent_homework, _hf, _sf = self._make_homework(days_ago=10)

        call_command('purge_old_homework', '--older-than-days=60', '--force')

        self.assertTrue(Homework.objects.filter(id=recent_homework.id).exists())