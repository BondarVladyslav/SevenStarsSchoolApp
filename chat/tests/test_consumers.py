from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.test import TransactionTestCase, override_settings

from chat.consumers import ChatConsumer
from chat.models import Conversation, Message
from courses.models import Group, Homework, Subject
from users.models import Student, Teacher

User = get_user_model()


@override_settings(CHANNEL_LAYERS={
    'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'},
})
class ChatConsumerTests(TransactionTestCase):
    def setUp(self):
        cache.clear()
        self.teacher_user = User.objects.create_user(username='teacher1', password='pass12345')
        self.teacher = Teacher.objects.create(user=self.teacher_user)
        self.student_user = User.objects.create_user(username='student1', password='pass12345')
        self.student = Student.objects.create(user=self.student_user)
        self.conversation = Conversation.objects.create(teacher=self.teacher, student=self.student)

    def _make_communicator(self, user, conversation_id=None):
        conversation_id = conversation_id or self.conversation.id
        communicator = WebsocketCommunicator(
            ChatConsumer.as_asgi(), f'/ws/chat/{conversation_id}/'
        )
        communicator.scope['user'] = user
        communicator.scope['url_route'] = {'kwargs': {'conversation_id': str(conversation_id)}}
        return communicator

    async def _connect(self, communicator):
        return await communicator.connect(timeout=10)

    async def test_anonymous_user_connection_rejected(self):
        from django.contrib.auth.models import AnonymousUser

        communicator = self._make_communicator(AnonymousUser())
        connected, _ = await self._connect(communicator)

        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_unrelated_user_connection_rejected(self):
        other_user = await self._acreate_user('outsider1')

        communicator = self._make_communicator(other_user)
        connected, _ = await self._connect(communicator)

        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_participant_can_connect(self):
        communicator = self._make_communicator(self.student_user)
        connected, _ = await self._connect(communicator)

        self.assertTrue(connected)
        await communicator.disconnect()

    async def test_nonexistent_conversation_rejected(self):
        communicator = self._make_communicator(self.student_user, conversation_id=99999)
        connected, _ = await self._connect(communicator)

        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_sending_message_broadcasts_and_persists(self):
        communicator = self._make_communicator(self.student_user)
        connected, _ = await self._connect(communicator)
        self.assertTrue(connected)

        await communicator.send_json_to({'text': 'Привіт!'})
        response = await communicator.receive_json_from(timeout=10)

        self.assertEqual(response['text'], 'Привіт!')
        self.assertEqual(response['sender_id'], self.student_user.id)

        message_count = await self._acount_messages()
        self.assertEqual(message_count, 1)

        await communicator.disconnect()

    async def test_blank_message_is_ignored(self):
        communicator = self._make_communicator(self.student_user)
        connected, _ = await self._connect(communicator)
        self.assertTrue(connected)

        await communicator.send_json_to({'text': '   '})

        message_count = await self._acount_messages()
        self.assertEqual(message_count, 0)

        await communicator.disconnect()

    async def test_rate_limit_blocks_excessive_messages(self):
        communicator = self._make_communicator(self.student_user)
        connected, _ = await self._connect(communicator)
        self.assertTrue(connected)

        for i in range(10):
            await communicator.send_json_to({'text': f'msg{i}'})
            await communicator.receive_json_from(timeout=10)

        await communicator.send_json_to({'text': 'one too many'})
        response = await communicator.receive_json_from(timeout=10)

        self.assertEqual(response['kind'], 'error')

        await communicator.disconnect()

    async def test_sending_valid_file_key_broadcasts_and_persists(self):
        from django.core.files.storage import default_storage
        from django.core.files.uploadedfile import SimpleUploadedFile

        key = 'chat_files/note.txt'
        await sync_to_async(default_storage.save)(key, SimpleUploadedFile('note.txt', b'content'))

        communicator = self._make_communicator(self.student_user)
        connected, _ = await self._connect(communicator)
        self.assertTrue(connected)

        await communicator.send_json_to({'text': '', 'file_key': key})
        response = await communicator.receive_json_from(timeout=10)

        self.assertTrue(response['has_file'])

        message = await self._aget_last_message()
        self.assertEqual(message.file.name, key)

        await communicator.disconnect()

    async def test_sending_nonexistent_file_key_returns_error_and_does_not_persist(self):
        communicator = self._make_communicator(self.student_user)
        connected, _ = await self._connect(communicator)
        self.assertTrue(connected)

        await communicator.send_json_to({'text': '', 'file_key': 'chat_files/does-not-exist.txt'})
        response = await communicator.receive_json_from(timeout=10)

        self.assertEqual(response['kind'], 'error')

        message_count = await self._acount_messages()
        self.assertEqual(message_count, 0)

        await communicator.disconnect()

    async def test_homework_from_conversation_group_is_attached(self):
        homework = await self._acreate_homework(self.teacher, self.student)

        communicator = self._make_communicator(self.student_user)
        connected, _ = await self._connect(communicator)
        self.assertTrue(connected)

        await communicator.send_json_to({'text': 'Ось моя робота', 'homework_id': homework.id})
        response = await communicator.receive_json_from(timeout=10)

        self.assertEqual(response['homework_id'], homework.id)
        self.assertEqual(response['homework_title'], homework.title)

        message = await self._aget_last_message()
        self.assertEqual(message.homework_id, homework.id)

        await communicator.disconnect()

    async def test_homework_from_unrelated_group_is_ignored(self):
        other_teacher_user = await self._acreate_user('teacher2')
        other_teacher = await self._acreate_teacher(other_teacher_user)
        other_student_user = await self._acreate_user('student2')
        other_student = await self._acreate_student(other_student_user)
        foreign_homework = await self._acreate_homework(other_teacher, other_student)

        communicator = self._make_communicator(self.student_user)
        connected, _ = await self._connect(communicator)
        self.assertTrue(connected)

        await communicator.send_json_to({'text': 'Ось моя робота', 'homework_id': foreign_homework.id})
        response = await communicator.receive_json_from(timeout=10)

        self.assertIsNone(response['homework_id'])
        self.assertIsNone(response['homework_title'])

        message = await self._aget_last_message()
        self.assertIsNone(message.homework_id)

        await communicator.disconnect()

    async def test_ping_gets_pong_and_does_not_create_message(self):
        communicator = self._make_communicator(self.student_user)
        connected, _ = await self._connect(communicator)
        self.assertTrue(connected)

        await communicator.send_json_to({'type': 'ping'})
        response = await communicator.receive_json_from(timeout=10)

        self.assertEqual(response['kind'], 'pong')
        message_count = await self._acount_messages()
        self.assertEqual(message_count, 0)

        await communicator.disconnect()

    @sync_to_async
    def _acreate_user(self, username):
        return User.objects.create_user(username=username, password='pass12345')

    @sync_to_async
    def _acount_messages(self):
        return Message.objects.count()

    @sync_to_async
    def _aget_last_message(self):
        return Message.objects.select_related().latest('id')

    @sync_to_async
    def _acreate_teacher(self, user):
        return Teacher.objects.create(user=user)

    @sync_to_async
    def _acreate_student(self, user):
        return Student.objects.create(user=user)

    @sync_to_async
    def _acreate_homework(self, teacher, student):
        subject = Subject.objects.create(name='Математика')
        group = Group.objects.create(name='Group A', subject=subject, teacher=teacher)
        group.students.add(student)
        return Homework.objects.create(
            group=group, title='ДЗ 1', description='Опис', deadline=timezone.now() + timedelta(days=3),
        )   