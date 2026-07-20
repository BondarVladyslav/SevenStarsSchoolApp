import shutil
import tempfile
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from courses.models import (
    Group,
    Homework,
    HomeworkFile,
    HomeworkSubmission,
    Subject,
    SubmissionFile,
)
from users.models import Parent, Student, Teacher

User = get_user_model()


def make_user_with_role(username, role_model, **user_kwargs):
    user = User.objects.create_user(username=username, password='pass12345', **user_kwargs)
    role = role_model.objects.create(user=user)
    return user, role


class ShowMyGroupsViewTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='Математика')
        self.group = Group.objects.create(name='Group A', subject=self.subject)

    def test_student_sees_own_groups(self):
        user, student = make_user_with_role('student1', Student)
        student.groups.add(self.group)

        self.client.force_login(user)
        response = self.client.get(reverse('show_my_groups'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'courses/my_groups_student.html')
        self.assertIn(self.group, response.context['groups'])

    def test_teacher_sees_own_groups(self):
        user, teacher = make_user_with_role('teacher1', Teacher)
        self.group.teacher = teacher
        self.group.save()

        self.client.force_login(user)
        response = self.client.get(reverse('show_my_groups'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'courses/my_groups_teacher.html')

    def test_parent_redirected_to_schedule(self):
        user, parent = make_user_with_role('parent1', Parent)
        student_user, student = make_user_with_role('child1', Student)
        parent.children.add(student)

        self.client.force_login(user)
        response = self.client.get(reverse('show_my_groups'))

        self.assertRedirects(response, reverse('schedule'))

    def test_user_without_role_redirected_to_moderation(self):
        user = User.objects.create_user(username='mod1', password='pass12345', is_superuser=True, is_staff=True)

        self.client.force_login(user)
        response = self.client.get(reverse('show_my_groups'))

        self.assertRedirects(response, reverse('moderation_dashboard'))

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(reverse('show_my_groups'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)


class ShowTheGroupViewTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='Математика')
        self.teacher_user, self.teacher = make_user_with_role('teacher1', Teacher)
        self.group = Group.objects.create(name='Group A', subject=self.subject, teacher=self.teacher)

    def test_student_in_group_can_view(self):
        user, student = make_user_with_role('student1', Student)
        student.groups.add(self.group)

        self.client.force_login(user)
        response = self.client.get(reverse('detail_group', args=[self.group.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'courses/one_group_student.html')

    def test_student_not_in_group_gets_permission_denied(self):
        user, _student = make_user_with_role('student2', Student)

        self.client.force_login(user)
        response = self.client.get(reverse('detail_group', args=[self.group.id]))

        self.assertEqual(response.status_code, 403)

    def test_teacher_of_group_can_view(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('detail_group', args=[self.group.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'courses/one_group_teacher.html')

    def test_teacher_not_of_group_gets_permission_denied(self):
        other_teacher_user, _teacher = make_user_with_role('teacher2', Teacher)

        self.client.force_login(other_teacher_user)
        response = self.client.get(reverse('detail_group', args=[self.group.id]))

        self.assertEqual(response.status_code, 403)

    def test_nonexistent_group_returns_404(self):
        user, student = make_user_with_role('student3', Student)
        self.client.force_login(user)
        response = self.client.get(reverse('detail_group', args=[99999]))
        self.assertEqual(response.status_code, 404)


_DETAIL_HOMEWORK_MEDIA_ROOT = tempfile.mkdtemp(prefix='ssschool_test_media_courses_detail_hw_')


@override_settings(MEDIA_ROOT=_DETAIL_HOMEWORK_MEDIA_ROOT)
class DetailHomeworkViewTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_DETAIL_HOMEWORK_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        subject = Subject.objects.create(name='Математика')
        self.teacher_user, self.teacher = make_user_with_role('teacher1', Teacher)
        self.group = Group.objects.create(name='Group A', subject=subject, teacher=self.teacher)
        self.student_user, self.student = make_user_with_role('student1', Student)
        self.student.groups.add(self.group)
        self.homework = Homework.objects.create(
            group=self.group,
            title='ДЗ 1',
            description='Опис',
            deadline=timezone.now() + timedelta(days=3),
        )

    def test_student_of_group_can_view_homework(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('detail_homework', args=[self.homework.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'courses/detail_homework_student.html')

    def test_submission_and_chat_text_fields_have_distinct_ids(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('detail_homework', args=[self.homework.id]))

        content = response.content.decode()
        self.assertEqual(content.count('id="id_text"'), 1)
        self.assertIn('id="chatMessageForm_text"', content)

    def test_student_not_of_group_gets_permission_denied(self):
        other_user, _s = make_user_with_role('student2', Student)
        self.client.force_login(other_user)

        response = self.client.get(reverse('detail_homework', args=[self.homework.id]))

        self.assertEqual(response.status_code, 403)

    def test_teacher_of_group_sees_submissions_list(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('detail_homework', args=[self.homework.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'courses/detail_homework_teacher.html')

    def test_student_can_submit_homework(self):
        self.client.force_login(self.student_user)
        response = self.client.post(reverse('detail_homework', args=[self.homework.id]), {
            'action': 'send_homework',
            'text': 'Моя відповідь',
        })

        self.assertRedirects(response, reverse('detail_homework', args=[self.homework.id]))
        submission = HomeworkSubmission.objects.get(homework=self.homework, student=self.student)
        self.assertEqual(submission.text, 'Моя відповідь')
        self.assertEqual(submission.status, 'pending')

    def test_resubmitting_resets_status_to_pending(self):
        submission = HomeworkSubmission.objects.create(
            homework=self.homework, student=self.student, text='Старе', status='need_revision',
        )
        self.client.force_login(self.student_user)

        self.client.post(reverse('detail_homework', args=[self.homework.id]), {
            'action': 'send_homework',
            'text': 'Нове',
        })

        submission.refresh_from_db()
        self.assertEqual(submission.text, 'Нове')
        self.assertEqual(submission.status, 'pending')

    def test_too_many_files_rejected(self):
        from django.core.files.storage import default_storage

        self.client.force_login(self.student_user)
        keys = []
        for i in range(8):
            key = f'submission_files/f{i}.txt'
            default_storage.save(key, SimpleUploadedFile(f'f{i}.txt', b'content'))
            keys.append(key)

        response = self.client.post(
            reverse('detail_homework', args=[self.homework.id]),
            {'action': 'send_homework', 'text': 'Text', 'uploaded_keys': keys},
        )

        self.assertEqual(response.status_code, 400)

    def test_nonexistent_uploaded_key_rejected(self):
        self.client.force_login(self.student_user)

        response = self.client.post(
            reverse('detail_homework', args=[self.homework.id]),
            {'action': 'send_homework', 'text': 'Text', 'uploaded_keys': ['submission_files/does-not-exist.txt']},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(HomeworkSubmission.objects.filter(homework=self.homework, student=self.student).exists())

    def test_submission_with_file_is_attached(self):
        from django.core.files.storage import default_storage

        self.client.force_login(self.student_user)
        key = 'submission_files/ok.txt'
        default_storage.save(key, SimpleUploadedFile('ok.txt', b'answer content'))

        response = self.client.post(
            reverse('detail_homework', args=[self.homework.id]),
            {'action': 'send_homework', 'text': 'Text', 'uploaded_keys': [key]},
        )

        self.assertRedirects(response, reverse('detail_homework', args=[self.homework.id]))
        submission = HomeworkSubmission.objects.get(homework=self.homework, student=self.student)
        self.assertEqual(submission.files.count(), 1)

    def test_oversized_uploaded_file_is_rejected_and_deleted(self):
        from django.core.files.storage import default_storage

        self.client.force_login(self.student_user)
        key = 'submission_files/big.bin'
        oversized_content = b'x' * (settings.MAX_UPLOAD_SIZE_STUDENT + 1)
        default_storage.save(key, SimpleUploadedFile('big.bin', oversized_content))

        response = self.client.post(
            reverse('detail_homework', args=[self.homework.id]),
            {'action': 'send_homework', 'text': 'Text', 'uploaded_keys': [key]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(HomeworkSubmission.objects.filter(homework=self.homework, student=self.student).exists())
        self.assertFalse(default_storage.exists(key))

    def test_student_can_delete_pending_submission(self):
        submission = HomeworkSubmission.objects.create(
            homework=self.homework, student=self.student, text='Текст', status='pending',
        )
        self.client.force_login(self.student_user)

        response = self.client.post(reverse('detail_homework', args=[self.homework.id]), {
            'action': 'delete_submission',
        })

        self.assertRedirects(response, reverse('detail_homework', args=[self.homework.id]))
        self.assertFalse(HomeworkSubmission.objects.filter(id=submission.id).exists())

    def test_student_cannot_delete_checked_submission(self):
        submission = HomeworkSubmission.objects.create(
            homework=self.homework, student=self.student, text='Текст', status='checked',
        )
        self.client.force_login(self.student_user)

        response = self.client.post(reverse('detail_homework', args=[self.homework.id]), {
            'action': 'delete_submission',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTrue(HomeworkSubmission.objects.filter(id=submission.id).exists())


class HomeworkCreateOrEditViewTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name='Математика')
        self.teacher_user, self.teacher = make_user_with_role('teacher1', Teacher)
        self.group = Group.objects.create(name='Group A', subject=subject, teacher=self.teacher)

    def test_non_teacher_gets_permission_denied(self):
        user, _s = make_user_with_role('student1', Student)
        self.client.force_login(user)

        response = self.client.get(reverse('create_homework', args=[self.group.id]))

        self.assertEqual(response.status_code, 403)

    def test_teacher_of_other_group_gets_404(self):
        other_teacher_user, _t = make_user_with_role('teacher2', Teacher)
        self.client.force_login(other_teacher_user)

        response = self.client.get(reverse('create_homework', args=[self.group.id]))

        self.assertEqual(response.status_code, 404)

    def test_teacher_can_create_homework(self):
        self.client.force_login(self.teacher_user)

        response = self.client.post(reverse('create_homework', args=[self.group.id]), {
            'action': 'save',
            'title': 'Нове ДЗ',
            'description': 'Опис',
            'deadline': '2026-08-01T10:00',
        })

        self.assertRedirects(response, reverse('detail_group', kwargs={'group_id': self.group.id}))
        self.assertTrue(Homework.objects.filter(group=self.group, title='Нове ДЗ').exists())

    def test_teacher_can_delete_homework(self):
        homework = Homework.objects.create(
            group=self.group, title='ДЗ', description='Опис',
            deadline=timezone.now() + timedelta(days=1),
        )
        self.client.force_login(self.teacher_user)

        response = self.client.post(reverse('create_homework', args=[self.group.id]), {
            'action': 'delete',
            'homework_id': homework.id,
        })

        self.assertRedirects(response, reverse('detail_group', kwargs={'group_id': self.group.id}))
        self.assertFalse(Homework.objects.filter(id=homework.id).exists())

    def test_too_many_files_on_creation_rejected(self):
        self.client.force_login(self.teacher_user)
        files = [SimpleUploadedFile(f'f{i}.txt', b'content') for i in range(8)]

        response = self.client.post(reverse('create_homework', args=[self.group.id]), {
            'action': 'save',
            'title': 'ДЗ',
            'description': 'Опис',
            'deadline': '2026-08-01T10:00',
            'files': files,
        })

        self.assertEqual(response.status_code, 400)


class DetailStudentViewTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name='Математика')
        self.teacher_user, self.teacher = make_user_with_role('teacher1', Teacher)
        self.group = Group.objects.create(name='Group A', subject=subject, teacher=self.teacher)
        self.student_user, self.student = make_user_with_role('student1', Student)
        self.student.groups.add(self.group)

    def test_teacher_can_view_their_student(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('detail_student', args=[self.group.id, self.student.id]))
        self.assertEqual(response.status_code, 200)

    def test_non_teacher_gets_permission_denied(self):
        other_user, _s = make_user_with_role('student2', Student)
        self.client.force_login(other_user)

        response = self.client.get(reverse('detail_student', args=[self.group.id, self.student.id]))

        self.assertEqual(response.status_code, 403)

    def test_student_not_in_group_returns_404(self):
        other_student_user, other_student = make_user_with_role('student3', Student)
        self.client.force_login(self.teacher_user)

        response = self.client.get(reverse('detail_student', args=[self.group.id, other_student.id]))

        self.assertEqual(response.status_code, 404)

    def test_teacher_can_reset_student_password(self):
        self.client.force_login(self.teacher_user)
        old_password_hash = self.student_user.password

        response = self.client.post(
            reverse('detail_student', args=[self.group.id, self.student.id]),
            {'action': 'reset_password'},
        )

        self.assertEqual(response.status_code, 200)
        self.student_user.refresh_from_db()
        self.assertNotEqual(self.student_user.password, old_password_hash)
        self.assertIsNotNone(response.context['new_password'])

    def test_teacher_can_remove_student_from_group(self):
        self.client.force_login(self.teacher_user)

        response = self.client.post(
            reverse('detail_student', args=[self.group.id, self.student.id]),
            {'action': 'remove_from_group'},
        )

        self.assertRedirects(response, reverse('detail_group', kwargs={'group_id': self.group.id}))
        self.assertFalse(self.group.students.filter(pk=self.student.pk).exists())

    def test_homework_linked_lesson_grade_is_attached_to_submission(self):
        from schedule.models import Lesson, LessonParticipation

        lesson = Lesson.objects.create(group=self.group, weekday=0, start_time='10:00', end_time='11:00')
        lesson_date = timezone.now().date()
        homework = Homework.objects.create(
            group=self.group, title='ДЗ 1', description='Опис',
            deadline=timezone.now() + timedelta(days=1),
            lesson=lesson, lesson_date=lesson_date,
        )
        submission = HomeworkSubmission.objects.create(homework=homework, student=self.student)
        participation = LessonParticipation.objects.create(
            lesson=lesson, lesson_date=lesson_date, student=self.student, score=8,
        )

        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('detail_student', args=[self.group.id, self.student.id]))

        rendered_item = response.context['student_homeworks'][0]
        self.assertEqual(rendered_item['submission'].id, submission.id)
        self.assertEqual(rendered_item['lesson_participation'], participation)

    def test_unsubmitted_homework_shows_not_submitted_badge(self):
        Homework.objects.create(
            group=self.group, title='Нездане ДЗ', description='Опис',
            deadline=timezone.now() + timedelta(days=1),
        )

        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('detail_student', args=[self.group.id, self.student.id]))

        content = response.content.decode()
        self.assertIn('Нездане ДЗ', content)
        self.assertIn('Не здано', content)

        rendered_item = response.context['student_homeworks'][0]
        self.assertIsNone(rendered_item['submission'])

    def test_standalone_lesson_grade_is_not_attached_to_any_homework(self):
        from schedule.models import Lesson, LessonParticipation

        lesson = Lesson.objects.create(group=self.group, weekday=0, start_time='10:00', end_time='11:00')
        lesson_date = timezone.now().date()
        participation = LessonParticipation.objects.create(
            lesson=lesson, lesson_date=lesson_date, student=self.student, score=6,
        )

        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('detail_student', args=[self.group.id, self.student.id]))

        self.assertEqual(list(response.context['standalone_lesson_grades']), [participation])

    def test_lesson_grade_from_another_group_is_excluded(self):
        from schedule.models import Lesson, LessonParticipation

        subject = Subject.objects.create(name='Англійська')
        other_group = Group.objects.create(name='Group B', subject=subject, teacher=self.teacher)
        other_lesson = Lesson.objects.create(group=other_group, weekday=1, start_time='12:00', end_time='13:00')
        LessonParticipation.objects.create(
            lesson=other_lesson, lesson_date=timezone.now().date(), student=self.student, score=9,
        )

        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('detail_student', args=[self.group.id, self.student.id]))

        self.assertEqual(list(response.context['standalone_lesson_grades']), [])

    def test_homework_without_lesson_shows_only_dz_badge(self):
        deadline = timezone.now() + timedelta(days=1)
        homework = Homework.objects.create(
            group=self.group, title='ДЗ без уроку', description='Опис',
            deadline=deadline,
        )
        HomeworkSubmission.objects.create(homework=homework, student=self.student, status='checked', grade=45)

        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('detail_student', args=[self.group.id, self.student.id]))

        content = response.content.decode()
        expected_date = deadline.strftime('%d.%m')
        self.assertIn(f'дз {expected_date}: 45/50%', content)
        self.assertNotIn('урок ', content)

    def test_homework_with_lesson_shows_both_badges(self):
        from schedule.models import Lesson, LessonParticipation

        lesson = Lesson.objects.create(group=self.group, weekday=0, start_time='10:00', end_time='11:00')
        lesson_date = timezone.now().date()
        deadline = timezone.now() + timedelta(days=1)
        homework = Homework.objects.create(
            group=self.group, title='ДЗ з уроком', description='Опис',
            deadline=deadline,
            lesson=lesson, lesson_date=lesson_date,
        )
        HomeworkSubmission.objects.create(homework=homework, student=self.student, status='checked', grade=40)
        LessonParticipation.objects.create(
            lesson=lesson, lesson_date=lesson_date, student=self.student, score=35,
        )

        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('detail_student', args=[self.group.id, self.student.id]))

        content = response.content.decode()
        self.assertIn(f'урок {lesson_date.strftime("%d.%m")}: 35/50%', content)
        self.assertIn(f'дз {deadline.strftime("%d.%m")}: 40/50%', content)


class DetailSubmissionViewTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name='Математика')
        self.teacher_user, self.teacher = make_user_with_role('teacher1', Teacher)
        self.group = Group.objects.create(name='Group A', subject=subject, teacher=self.teacher)
        self.student_user, self.student = make_user_with_role('student1', Student)
        self.student.groups.add(self.group)
        self.homework = Homework.objects.create(
            group=self.group, title='ДЗ 1', description='Опис',
            deadline=timezone.now() + timedelta(days=1),
        )
        self.submission = HomeworkSubmission.objects.create(
            homework=self.homework, student=self.student, text='Відповідь',
        )

    def test_teacher_of_group_can_view_submission(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('detail_submission', args=[self.submission.id]))
        self.assertEqual(response.status_code, 200)

    def test_other_user_gets_404(self):
        other_teacher_user, _t = make_user_with_role('teacher2', Teacher)
        self.client.force_login(other_teacher_user)

        response = self.client.get(reverse('detail_submission', args=[self.submission.id]))

        self.assertEqual(response.status_code, 404)

    def test_teacher_can_grade_submission(self):
        self.client.force_login(self.teacher_user)

        response = self.client.post(reverse('detail_submission', args=[self.submission.id]), {
            'action': 'check_submission',
            'grade': 45,
            'status': 'checked',
            'teacher_comment': 'Молодець',
        })

        self.assertRedirects(response, reverse('detail_submission', kwargs={'submission_id': self.submission.id}))
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.grade, 45)
        self.assertEqual(self.submission.status, 'checked')
        self.assertIsNotNone(self.submission.checked_at)


_TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix='ssschool_test_media_courses_')


@override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
class DownloadFileViewTests(TestCase):
    """Uses an isolated temp MEDIA_ROOT instead of the real media/ folder, and
    removes it wholesale in tearDownClass. This avoids Windows' PermissionError
    when trying to delete a file that FileResponse just streamed and the OS
    hasn't fully released the handle for yet."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        subject = Subject.objects.create(name='Математика')
        self.teacher_user, self.teacher = make_user_with_role('teacher1', Teacher)
        self.group = Group.objects.create(name='Group A', subject=subject, teacher=self.teacher)
        self.student_user, self.student = make_user_with_role('student1', Student)
        self.student.groups.add(self.group)
        self.homework = Homework.objects.create(
            group=self.group, title='ДЗ 1', description='Опис',
            deadline=timezone.now() + timedelta(days=1),
        )
        self.homework_file = HomeworkFile.objects.create(
            homework=self.homework,
            file=SimpleUploadedFile('task.txt', b'homework content'),
        )
        self.submission = HomeworkSubmission.objects.create(homework=self.homework, student=self.student)
        self.submission_file = SubmissionFile.objects.create(
            submission=self.submission,
            file=SimpleUploadedFile('answer.txt', b'submission content'),
        )

    def test_student_of_group_can_download_homework_file(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('download_homework_file', args=[self.homework_file.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.homework_file.file.url)

    def test_unrelated_user_cannot_download_homework_file(self):
        other_user, _s = make_user_with_role('student2', Student)
        self.client.force_login(other_user)
        response = self.client.get(reverse('download_homework_file', args=[self.homework_file.id]))
        self.assertEqual(response.status_code, 403)

    def test_owner_can_download_own_submission_file(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('download_submission_file', args=[self.submission_file.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.submission_file.file.url)

    def test_teacher_of_group_can_download_submission_file(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('download_submission_file', args=[self.submission_file.id]))
        self.assertEqual(response.status_code, 302)

    def test_unrelated_user_cannot_download_submission_file(self):
        other_user, _s = make_user_with_role('student3', Student)
        self.client.force_login(other_user)
        response = self.client.get(reverse('download_submission_file', args=[self.submission_file.id]))
        self.assertEqual(response.status_code, 403)

    def test_missing_homework_file_on_disk_returns_404(self):
        self.homework_file.file.delete(save=False)
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('download_homework_file', args=[self.homework_file.id]))
        self.assertEqual(response.status_code, 404)

    def test_missing_submission_file_on_disk_returns_404(self):
        self.submission_file.file.delete(save=False)
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('download_submission_file', args=[self.submission_file.id]))
        self.assertEqual(response.status_code, 404)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class HomeworkCreateOrEditViewTests(TestCase):

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._overridden_settings['MEDIA_ROOT'], ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.subject = Subject.objects.create(name='Математика')
        self.teacher_user, self.teacher = make_user_with_role('teacher1', Teacher)
        self.group = Group.objects.create(name='Group A', subject=self.subject, teacher=self.teacher)

        self.other_teacher_user, self.other_teacher = make_user_with_role('teacher2', Teacher)
        self.other_group = Group.objects.create(
            name='Group B', subject=self.subject, teacher=self.other_teacher
        )

        self.homework = Homework.objects.create(group=self.group, title='ДЗ 1', deadline=timezone.now() + timedelta(days=3))
        self.homework_file = HomeworkFile.objects.create(
            homework=self.homework,
            file=SimpleUploadedFile('task.txt', b'homework content'),
        )

    def test_non_teacher_gets_permission_denied(self):
        student_user, student = make_user_with_role('student1', Student)
        self.client.force_login(student_user)

        response = self.client.get(reverse('create_homework', args=[self.group.id]))

        self.assertEqual(response.status_code, 403)

    def test_teacher_cannot_open_create_form_for_foreign_group(self):
        self.client.force_login(self.other_teacher_user)

        response = self.client.get(reverse('create_homework', args=[self.group.id]))

        self.assertEqual(response.status_code, 404)

    def test_teacher_cannot_open_edit_form_for_foreign_groups_homework(self):
        self.client.force_login(self.other_teacher_user)

        response = self.client.get(
            reverse('edit_homework', args=[self.group.id, self.homework.id])
        )

        self.assertEqual(response.status_code, 404)

    def test_teacher_cannot_delete_file_from_foreign_groups_homework(self):
        self.client.force_login(self.other_teacher_user)

        response = self.client.post(
            reverse('edit_homework', args=[self.group.id, self.homework.id]),
            {'action': 'delete_file', 'file_id': self.homework_file.id},
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(HomeworkFile.objects.filter(id=self.homework_file.id).exists())

    def test_owning_teacher_can_delete_file(self):
        self.client.force_login(self.teacher_user)

        response = self.client.post(
            reverse('edit_homework', args=[self.group.id, self.homework.id]),
            {'action': 'delete_file', 'file_id': self.homework_file.id},
        )

        self.assertRedirects(
            response, reverse('edit_homework', args=[self.group.id, self.homework.id])
        )
        self.assertFalse(HomeworkFile.objects.filter(id=self.homework_file.id).exists())

    def test_owning_teacher_can_create_homework_with_files(self):
        from django.core.files.storage import default_storage

        self.client.force_login(self.teacher_user)
        key = 'homework_files/new_task.txt'
        default_storage.save(key, SimpleUploadedFile('new_task.txt', b'new homework content'))

        response = self.client.post(
            reverse('create_homework', args=[self.group.id]),
            {
                'action': 'save',
                'title': 'Нове ДЗ',
                'description': 'Опис нового ДЗ',
                'deadline': (timezone.now() + timedelta(days=5)).strftime('%Y-%m-%dT%H:%M'),
                'uploaded_keys': [key],
            },
        )

        self.assertRedirects(response, reverse('detail_group', args=[self.group.id]))
        new_homework = Homework.objects.exclude(id=self.homework.id).get(group=self.group)
        self.assertEqual(new_homework.files.count(), 1)

    def test_create_homework_rejects_too_many_files(self):
        from django.core.files.storage import default_storage

        self.client.force_login(self.teacher_user)
        keys = []
        for i in range(8):
            key = f'homework_files/f{i}.txt'
            default_storage.save(key, SimpleUploadedFile(f'f{i}.txt', b'x'))
            keys.append(key)

        response = self.client.post(
            reverse('create_homework', args=[self.group.id]),
            {'action': 'save', 'title': 'ДЗ з файлами', 'uploaded_keys': keys},
        )

        self.assertEqual(response.status_code, 400)

    def test_owning_teacher_can_delete_homework(self):
        self.client.force_login(self.teacher_user)

        response = self.client.post(
            reverse('edit_homework', args=[self.group.id, self.homework.id]),
            {'action': 'delete', 'homework_id': self.homework.id},
        )

        self.assertRedirects(response, reverse('detail_group', args=[self.group.id]))
        self.assertFalse(Homework.objects.filter(id=self.homework.id).exists())

    def test_foreign_teacher_cannot_delete_homework_by_spoofing_post_id(self):
        other_group_homework = Homework.objects.create(group=self.other_group, title='Чуже ДЗ', deadline=timezone.now() + timedelta(days=3))
        self.client.force_login(self.other_teacher_user)

        response = self.client.post(
            reverse('create_homework', args=[self.other_group.id]),
            {'action': 'delete', 'homework_id': self.homework.id},
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Homework.objects.filter(id=self.homework.id).exists())
        self.assertTrue(Homework.objects.filter(id=other_group_homework.id).exists())


class DetailSubmissionViewTeacherActionsTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(name='Математика')
        self.teacher_user, self.teacher = make_user_with_role('teacher1', Teacher)
        self.group = Group.objects.create(name='Group A', subject=self.subject, teacher=self.teacher)
        self.student_user, self.student = make_user_with_role('student1', Student)
        self.student.groups.add(self.group)
        self.homework = Homework.objects.create(group=self.group, title='ДЗ 1', deadline=timezone.now() + timedelta(days=3))
        self.submission = HomeworkSubmission.objects.create(homework=self.homework, student=self.student)

    def test_owning_teacher_can_check_submission(self):
        self.client.force_login(self.teacher_user)

        response = self.client.post(
            reverse('detail_submission', args=[self.submission.id]),
            {'action': 'check_submission', 'status': 'checked', 'grade': '10'},
        )

        self.assertRedirects(response, reverse('detail_submission', args=[self.submission.id]))
        self.submission.refresh_from_db()
        self.assertEqual(self.submission.status, 'checked')
        self.assertIsNotNone(self.submission.checked_at)

    def test_owning_teacher_can_send_message_from_submission_page(self):
        self.client.force_login(self.teacher_user)

        response = self.client.post(
            reverse('detail_submission', args=[self.submission.id]),
            {'action': 'send_message', 'text': 'Перероби другий пункт'},
        )

        self.assertRedirects(response, reverse('detail_submission', args=[self.submission.id]))

    def test_unrelated_teacher_gets_404_on_foreign_submission(self):
        other_teacher_user, _t = make_user_with_role('teacher2', Teacher)
        self.client.force_login(other_teacher_user)

        response = self.client.get(reverse('detail_submission', args=[self.submission.id]))

        self.assertEqual(response.status_code, 404)


class HomeworkUploadUrlViewTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name='Математика')
        self.teacher_user, self.teacher = make_user_with_role('teacher1', Teacher)
        self.group = Group.objects.create(name='Group A', subject=subject, teacher=self.teacher)

        self.other_teacher_user, self.other_teacher = make_user_with_role('teacher2', Teacher)

    def test_owning_teacher_with_local_storage_gets_bad_request(self):
        self.client.force_login(self.teacher_user)

        response = self.client.post(
            reverse('homework_upload_url', args=[self.group.id]),
            data='{"files": [{"name": "a.txt", "size": 100}]}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)

    def test_foreign_teacher_gets_404(self):
        self.client.force_login(self.other_teacher_user)

        response = self.client.post(
            reverse('homework_upload_url', args=[self.group.id]),
            data='{"files": [{"name": "a.txt", "size": 100}]}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)

    def test_non_teacher_denied(self):
        student_user, _s = make_user_with_role('student1', Student)
        self.client.force_login(student_user)

        response = self.client.post(
            reverse('homework_upload_url', args=[self.group.id]),
            data='{"files": [{"name": "a.txt", "size": 100}]}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)

    def test_get_request_is_bad_request(self):
        self.client.force_login(self.teacher_user)
        response = self.client.get(reverse('homework_upload_url', args=[self.group.id]))
        self.assertEqual(response.status_code, 400)

    def test_too_many_filenames_is_bad_request(self):
        self.client.force_login(self.teacher_user)
        files_json = ', '.join(f'{{"name": "{c}.txt", "size": 100}}' for c in 'abcdefgh')
        response = self.client.post(
            reverse('homework_upload_url', args=[self.group.id]),
            data='{"files": [' + files_json + ']}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_file_over_teacher_limit_is_rejected(self):
        self.client.force_login(self.teacher_user)
        oversized = settings.MAX_UPLOAD_SIZE_TEACHER + 1

        response = self.client.post(
            reverse('homework_upload_url', args=[self.group.id]),
            data='{"files": [{"name": "big.mp4", "size": %d}]}' % oversized,
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('big.mp4', response.content.decode())


class SubmissionUploadUrlViewTests(TestCase):
    def setUp(self):
        subject = Subject.objects.create(name='Математика')
        self.teacher_user, self.teacher = make_user_with_role('teacher1', Teacher)
        self.group = Group.objects.create(name='Group A', subject=subject, teacher=self.teacher)
        self.student_user, self.student = make_user_with_role('student1', Student)
        self.student.groups.add(self.group)
        self.homework = Homework.objects.create(
            group=self.group, title='ДЗ 1', deadline=timezone.now() + timedelta(days=3),
        )

    def test_enrolled_student_with_local_storage_gets_bad_request(self):
        self.client.force_login(self.student_user)

        response = self.client.post(
            reverse('submission_upload_url', args=[self.homework.id]),
            data='{"files": [{"name": "answer.txt", "size": 100}]}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)

    def test_unrelated_student_denied(self):
        other_student_user, _s = make_user_with_role('student2', Student)
        self.client.force_login(other_student_user)

        response = self.client.post(
            reverse('submission_upload_url', args=[self.homework.id]),
            data='{"files": [{"name": "answer.txt", "size": 100}]}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)

    def test_teacher_denied(self):
        self.client.force_login(self.teacher_user)

        response = self.client.post(
            reverse('submission_upload_url', args=[self.homework.id]),
            data='{"files": [{"name": "answer.txt", "size": 100}]}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 403)

    def test_file_over_student_limit_is_rejected(self):
        self.client.force_login(self.student_user)
        oversized = settings.MAX_UPLOAD_SIZE_STUDENT + 1

        response = self.client.post(
            reverse('submission_upload_url', args=[self.homework.id]),
            data='{"files": [{"name": "big.zip", "size": %d}]}' % oversized,
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('big.zip', response.content.decode())