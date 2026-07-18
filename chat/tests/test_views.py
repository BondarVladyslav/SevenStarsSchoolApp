import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from chat.models import Conversation, Message
from users.models import Student, Teacher

User = get_user_model()

_TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix='ssschool_test_media_')


@override_settings(MEDIA_ROOT=_TEST_MEDIA_ROOT)
class DownloadChatFileViewTests(TestCase):
    """Uses an isolated temp MEDIA_ROOT instead of the real media/ folder, and
    removes it wholesale in tearDownClass. This avoids two problems: polluting
    the real media directory with test files, and Windows' PermissionError
    when trying to delete a file that FileResponse just streamed and the OS
    hasn't fully released the handle for yet."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(_TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        teacher_user = User.objects.create_user(username='teacher1', password='pass12345')
        self.teacher = Teacher.objects.create(user=teacher_user)
        student_user = User.objects.create_user(username='student1', password='pass12345')
        self.student = Student.objects.create(user=student_user)
        self.conversation = Conversation.objects.create(teacher=self.teacher, student=self.student)
        self.message = Message.objects.create(
            conversation=self.conversation,
            sender=teacher_user,
            file=SimpleUploadedFile('doc.txt', b'chat file content'),
        )

    def test_student_participant_can_download(self):
        self.client.force_login(self.student.user)
        response = self.client.get(reverse('download_chat_file', args=[self.message.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(self.message.file.name.rsplit('/', 1)[-1], response.url)

    def test_teacher_participant_can_download(self):
        self.client.force_login(self.teacher.user)
        response = self.client.get(reverse('download_chat_file', args=[self.message.id]))
        self.assertEqual(response.status_code, 302)

    def test_superuser_can_download(self):
        admin_user = User.objects.create_user(username='admin1', password='pass12345', is_superuser=True)
        self.client.force_login(admin_user)
        response = self.client.get(reverse('download_chat_file', args=[self.message.id]))
        self.assertEqual(response.status_code, 302)

    def test_unrelated_user_gets_404(self):
        other_user = User.objects.create_user(username='other1', password='pass12345')
        self.client.force_login(other_user)
        response = self.client.get(reverse('download_chat_file', args=[self.message.id]))
        self.assertEqual(response.status_code, 404)

    def test_anonymous_user_redirected_to_login(self):
        response = self.client.get(reverse('download_chat_file', args=[self.message.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_redirects_to_the_files_storage_url(self):
        self.client.force_login(self.student.user)
        response = self.client.get(reverse('download_chat_file', args=[self.message.id]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.message.file.url)

    def test_missing_file_on_disk_returns_404(self):
        self.message.file.delete(save=False)
        self.client.force_login(self.student.user)
        response = self.client.get(reverse('download_chat_file', args=[self.message.id]))
        self.assertEqual(response.status_code, 404)


class ChatUploadUrlViewTests(TestCase):
    def setUp(self):
        teacher_user = User.objects.create_user(username='teacher1', password='pass12345')
        self.teacher = Teacher.objects.create(user=teacher_user)
        student_user = User.objects.create_user(username='student1', password='pass12345')
        self.student = Student.objects.create(user=student_user)
        self.conversation = Conversation.objects.create(teacher=self.teacher, student=self.student)

    def test_student_participant_with_local_storage_gets_bad_request(self):
        self.client.force_login(self.student.user)

        response = self.client.post(
            reverse('chat_upload_url', args=[self.conversation.id]),
            data='{"filenames": ["a.txt"]}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)

    def test_teacher_participant_with_local_storage_gets_bad_request(self):
        self.client.force_login(self.teacher.user)

        response = self.client.post(
            reverse('chat_upload_url', args=[self.conversation.id]),
            data='{"filenames": ["a.txt"]}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 400)

    def test_unrelated_user_gets_404(self):
        other_user = User.objects.create_user(username='other1', password='pass12345')
        self.client.force_login(other_user)

        response = self.client.post(
            reverse('chat_upload_url', args=[self.conversation.id]),
            data='{"filenames": ["a.txt"]}',
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)

    def test_get_request_is_bad_request(self):
        self.client.force_login(self.student.user)
        response = self.client.get(reverse('chat_upload_url', args=[self.conversation.id]))
        self.assertEqual(response.status_code, 400)

    def test_too_many_filenames_is_bad_request(self):
        self.client.force_login(self.student.user)
        response = self.client.post(
            reverse('chat_upload_url', args=[self.conversation.id]),
            data='{"filenames": ["a.txt", "b.txt"]}',
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)