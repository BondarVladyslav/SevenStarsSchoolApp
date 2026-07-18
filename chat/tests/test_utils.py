from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from chat.models import Conversation, Message
from chat.utils import handle_chat_message
from users.models import Student, Teacher

User = get_user_model()


class HandleChatMessageTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        teacher_user = User.objects.create_user(username='teacher1', password='pass12345')
        self.teacher = Teacher.objects.create(user=teacher_user)
        student_user = User.objects.create_user(username='student1', password='pass12345')
        self.student = Student.objects.create(user=student_user)
        self.conversation = Conversation.objects.create(teacher=self.teacher, student=self.student)

    def test_get_request_returns_empty_unbound_form(self):
        request = self.factory.get('/')
        request.user = self.student.user

        form, sent = handle_chat_message(request, self.conversation)

        self.assertFalse(sent)
        self.assertFalse(form.is_bound)

    def test_post_without_send_action_does_not_create_message(self):
        request = self.factory.post('/', {'action': 'something_else', 'text': 'hi'})
        request.user = self.student.user

        form, sent = handle_chat_message(request, self.conversation)

        self.assertFalse(sent)
        self.assertEqual(Message.objects.count(), 0)

    def test_valid_post_creates_message(self):
        request = self.factory.post('/', {'action': 'send_message', 'text': 'Привіт вчителю'})
        request.user = self.student.user

        form, sent = handle_chat_message(request, self.conversation)

        self.assertTrue(sent)
        message = Message.objects.get()
        self.assertEqual(message.text, 'Привіт вчителю')
        self.assertEqual(message.sender, self.student.user)
        self.assertEqual(message.conversation, self.conversation)

    def test_message_linked_to_homework_when_provided(self):
        from courses.models import Group, Homework, Subject
        from django.utils import timezone
        from datetime import timedelta

        subject = Subject.objects.create(name='Математика')
        group = Group.objects.create(name='Group A', subject=subject)
        homework = Homework.objects.create(
            group=group, title='ДЗ', description='Опис', deadline=timezone.now() + timedelta(days=1),
        )

        request = self.factory.post('/', {'action': 'send_message', 'text': 'Ось моя робота'})
        request.user = self.student.user

        form, sent = handle_chat_message(request, self.conversation, homework)

        self.assertTrue(sent)
        message = Message.objects.get()
        self.assertEqual(message.homework, homework)

    def test_post_with_nonexistent_uploaded_key_is_rejected(self):
        request = self.factory.post('/', {
            'action': 'send_message',
            'text': '',
            'uploaded_key': 'chat_files/does-not-exist.txt',
        })
        request.user = self.student.user

        form, sent = handle_chat_message(request, self.conversation)

        self.assertFalse(sent)
        self.assertEqual(Message.objects.count(), 0)

    def test_post_with_valid_uploaded_key_attaches_file(self):
        from django.core.files.storage import default_storage
        from django.core.files.uploadedfile import SimpleUploadedFile

        key = 'chat_files/note.txt'
        default_storage.save(key, SimpleUploadedFile('note.txt', b'content'))

        request = self.factory.post('/', {
            'action': 'send_message',
            'text': '',
            'uploaded_key': key,
        })
        request.user = self.student.user

        form, sent = handle_chat_message(request, self.conversation)

        self.assertTrue(sent)
        message = Message.objects.get()
        self.assertEqual(message.file.name, key)

    def test_empty_message_without_file_is_rejected(self):
        request = self.factory.post('/', {'action': 'send_message', 'text': ''})
        request.user = self.student.user

        form, sent = handle_chat_message(request, self.conversation)

        self.assertFalse(sent)
        self.assertEqual(Message.objects.count(), 0)

    def test_whitespace_only_message_without_file_is_rejected(self):
        request = self.factory.post('/', {'action': 'send_message', 'text': '   '})
        request.user = self.student.user

        form, sent = handle_chat_message(request, self.conversation)

        self.assertFalse(sent)
        self.assertEqual(Message.objects.count(), 0)