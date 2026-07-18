from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase

from chat.models import Conversation, Message
from courses.models import Group, Homework, Subject
from users.models import Student, Teacher
from django.utils import timezone
from datetime import timedelta

User = get_user_model()


class ConversationModelTests(TestCase):
    def setUp(self):
        teacher_user = User.objects.create_user(username='teacher1', password='pass12345')
        self.teacher = Teacher.objects.create(user=teacher_user)
        student_user = User.objects.create_user(username='student1', password='pass12345')
        self.student = Student.objects.create(user=student_user)

    def test_create_conversation(self):
        conversation = Conversation.objects.create(teacher=self.teacher, student=self.student)
        self.assertIsNotNone(conversation.created_at)

    def test_unique_together_teacher_student(self):
        Conversation.objects.create(teacher=self.teacher, student=self.student)
        with transaction.atomic():
            with self.assertRaises(IntegrityError):
                Conversation.objects.create(teacher=self.teacher, student=self.student)

    def test_conversation_deleted_when_teacher_deleted(self):
        conversation = Conversation.objects.create(teacher=self.teacher, student=self.student)
        conversation_id = conversation.id

        self.teacher.delete()

        self.assertFalse(Conversation.objects.filter(id=conversation_id).exists())


class MessageModelTests(TestCase):
    def setUp(self):
        teacher_user = User.objects.create_user(username='teacher1', password='pass12345')
        self.teacher = Teacher.objects.create(user=teacher_user)
        student_user = User.objects.create_user(username='student1', password='pass12345')
        self.student = Student.objects.create(user=student_user)
        self.conversation = Conversation.objects.create(teacher=self.teacher, student=self.student)

    def test_create_text_message(self):
        message = Message.objects.create(
            conversation=self.conversation, sender=self.student.user, text='Привіт',
        )
        self.assertEqual(message.text, 'Привіт')
        self.assertFalse(message.is_read)

    def test_message_related_to_homework(self):
        subject = Subject.objects.create(name='Математика')
        group = Group.objects.create(name='Group A', subject=subject)
        homework = Homework.objects.create(
            group=group, title='ДЗ', description='Опис', deadline=timezone.now() + timedelta(days=1),
        )
        message = Message.objects.create(
            conversation=self.conversation,
            sender=self.teacher.user,
            text='Дивись ДЗ',
            homework=homework,
        )
        self.assertEqual(message.homework, homework)

    def test_message_homework_set_null_when_homework_deleted(self):
        subject = Subject.objects.create(name='Математика')
        group = Group.objects.create(name='Group A', subject=subject)
        homework = Homework.objects.create(
            group=group, title='ДЗ', description='Опис', deadline=timezone.now() + timedelta(days=1),
        )
        message = Message.objects.create(
            conversation=self.conversation, sender=self.teacher.user, text='Дивись ДЗ', homework=homework,
        )

        homework.delete()
        message.refresh_from_db()

        self.assertIsNone(message.homework)

    def test_message_deleted_when_conversation_deleted(self):
        message = Message.objects.create(
            conversation=self.conversation, sender=self.student.user, text='Привіт',
        )
        message_id = message.id

        self.conversation.delete()

        self.assertFalse(Message.objects.filter(id=message_id).exists())
